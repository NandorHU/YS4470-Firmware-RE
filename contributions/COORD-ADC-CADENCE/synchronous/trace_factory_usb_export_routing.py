"""Verify original USB export text/category routing beyond the regular AC modes."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_renderer import BASE, DISPLAY, INIT_BASE, SETTINGS, restore_globals
from trace_ac_usb_export import CACHE, CACHE_LENGTH, EXPORT, EXPORT_WINDOWS, REPORT_FORMATTER
from trace_control_gui_events import MODE
from trace_secondary_usb_irq import MODE as USB_MODE
from trace_timer0_uart2_irq import RESULT
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_SP, UC_CPU_ARM_926,
)

STACK, INPUT, RETURN = 0x10014000, 0x10011000, 0x10010000
CATEGORIES = {9: 1, 10: 1, 11: 1, 12: 2, 13: 0, 14: 4, 15: 3, 16: 0, 17: 0, 18: 0, 34: 2, 48: 0, 255: 0}
UNITS = {
    9: ("V",) * 7, 10: ("V",) * 7, 12: ("R", "K", "K", "K", "M", "M", "M"),
    13: ("V",) * 7, 14: ("V",) * 7, 15: ("nF", "uF", "uF", "mF", "mF", "mF", "mF"),
}
STRIP_CHARACTERS = str.maketrans("", "", " \t\r\n")


def expected_route(ui_mode, configuration, secondary, fast, signed_raw, selector, text, strip):
    category = 4 if ui_mode == 4 else CATEGORIES[configuration]
    if ".OL" in text or "OPEN" in text:
        return category, text[:23], "%s"
    if strip:
        return category, text.translate(STRIP_CHARACTERS)[:23], None
    unit_selector = selector if selector < 7 else 0
    if ui_mode == 4:
        suffix = "R" if configuration == 34 and fast == 1 else "V"
    elif configuration >= 48:
        suffix = ""
    else:
        effective = 12 if configuration == 34 else configuration
        if effective == 12 and secondary == 0x15 and signed_raw < 100:
            unit_selector = 0
        suffix = UNITS[effective][unit_selector]
    return category, (text + suffix)[:23], "%s%s"


def scenarios():
    # Ordinary unit selection, direct selector fallback and a mode-4 override.
    for ui_mode, configuration, selector in product((1, 4), (9, 10, 12, 13, 14, 15, 34, 48, 255),
                                                   (0, 1, 2, 3, 4, 5, 6, 7, 255)):
        yield ui_mode, configuration, 0x19, 0, 100, selector, "12.345", 0
    for configuration, secondary, raw, selector in product((12, 34), (0x15, 0x19), (-1, 99, 100, 101), (1, 6)):
        yield 0, configuration, secondary, 0, raw, selector, "12.345", 0
    for fast, selector in product((0, 1, 2, 0xFFFFFFFF), (0, 3, 6, 255)):
        yield 4, 34, 0x15, fast, 99, selector, "0.050", 0
    for configuration, text, strip in product((12, 13, 15), (
        ".OL", "OPEN", "x.OL y", "xOPEN\t y", "open", " 1\t2\r.3\n4 5 ",
        "123456789012345678901234567890", " ", "",
    ), (0, 1)):
        yield 1, configuration, 0x19, 0, 100, 1, text, strip
    for configuration in (11, 16, 17, 18):
        # These entries have no unit pointers, but the original status-text
        # and whitespace paths reach category routing without reading one.
        yield 1, configuration, 0x19, 0, 100, 1, ".OL", 0
        yield 1, configuration, 0x19, 0, 100, 1, " 12.345 ", 1
    yield 1, 12, 0x19, 0, 100, 1, None, 0


class Exporter:
    def __init__(self, raw):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        low, high = BASE & ~0xFFF, 0x805B0000
        u.mem_map(low, high - low)
        u.mem_write(BASE, raw)
        u.mem_write(INIT_BASE, restore_globals(raw))
        u.mem_map(RETURN, 0x5000)
        self.put(USB_MODE, 0)
        self.coverage = {}
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def put(self, address, value):
        self.u.mem_write(address, (value & 0xFFFFFFFF).to_bytes(4, "little"))

    def text(self, address, limit):
        value = bytes(self.u.mem_read(address, limit))
        assert b"\0" in value
        return value.split(b"\0", 1)[0].decode("ascii")

    def code(self, u, pc, size, data):
        if pc == REPORT_FORMATTER:
            assert u.reg_read(UC_ARM_REG_R1) == 24
            spec = self.text(u.reg_read(UC_ARM_REG_R2), 8)
            assert (u.reg_read(UC_ARM_REG_LR), spec) in ((0x80045208, "%s"), (0x80045310, "%s%s"))
            self.formats.append(spec)
        if pc == EXPORT:
            assert u.reg_read(UC_ARM_REG_LR) == 0x8004537C
            self.exports.append([u.reg_read(UC_ARM_REG_R0), self.text(u.reg_read(UC_ARM_REG_R1), 24)])
        assert size in (2, 4) and any(lo <= pc < hi for lo, hi in EXPORT_WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        assert STACK - 0x400 <= address and address + size <= STACK or (
            CACHE <= address and address + size <= CACHE + CACHE_LENGTH), (hex(u.reg_read(UC_ARM_REG_PC)), hex(address))

    def run(self, ui_mode, configuration, secondary, fast, signed_raw, selector, text, strip):
        u = self.u
        u.mem_write(MODE, bytes((ui_mode, 0, 0, 0, 0, 0, 0, configuration, secondary)))
        self.put(SETTINGS + 0x18, fast)
        self.put(RESULT + 0x1C, signed_raw)
        self.put(RESULT + 0x20, selector)
        u.mem_write(CACHE, b"\xA5" * CACHE_LENGTH)
        u.mem_write(INPUT, (text or "").encode("ascii") + b"\0")
        self.formats, self.exports = [], []
        for reg, value in ((UC_ARM_REG_R0, INPUT if text is not None else 0), (UC_ARM_REG_R1, strip),
                           (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_CPSR, 0x13)):
            u.reg_write(reg, value)
        u.emu_start(DISPLAY, RETURN, count=10_000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == STACK
        mirror = bytes(u.mem_read(CACHE, CACHE_LENGTH))
        expected = None
        if text:
            category, formatted, spec = expected_route(ui_mode, configuration, secondary, fast, signed_raw, selector, text, strip)
            expected = (category, formatted)
            assert self.exports == [[category, formatted]] and self.formats == ([spec] if spec else [])
            assert mirror == bytes((category,)) + formatted[:19].encode("ascii").ljust(20, b"\0")
        else:
            assert self.exports == self.formats == [] and mirror == b"\xA5" * CACHE_LENGTH
        assert self.u.mem_read(RESULT + 0x20, 1)[0] == selector
        return [ui_mode, configuration, secondary, fast, signed_raw, selector, text, strip, expected, mirror.hex()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    images, observations = {}, []
    for entry in manifest["images"]:
        raw = Path(entry["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry["sha256"] and len(raw) == entry["size_bytes"]
        images[entry["version"]] = digest
        replay = Exporter(raw)
        cases = [replay.run(*scenario) for scenario in scenarios()]
        observations.append((cases, replay.coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.factory-usb-export-routing.v1", images=images, cases_per_image=len(cases),
                  columns=["ui_mode", "configuration", "secondary", "fast_cont", "stored_signed_raw",
                           "stored_selector", "input_text", "strip_whitespace", "category_and_text", "mirror_hex"],
                  cases=cases, instruction_bytes={hex(pc): code for pc, code in sorted(coverage.items())},
                  limits=["Direct CPU invocation uses synthetic text and caller mode/selector fields.",
                          "Original runtime text formatting and cache update execute with USB disabled.",
                          "Direct selector values outside 0..6 are fixtures. The normal UART parser instead clamps them before storage.",
                          "Unit strings are exported tokens. Physical values and device transfers remain outside the test."])
    args.out.write_bytes((json.dumps(report, separators=(",", ":")) + "\n").encode())
    print(f"PASS {len(cases)} factory USB export-routing cases per image, {2*len(cases)} total")


if __name__ == "__main__":
    main()
