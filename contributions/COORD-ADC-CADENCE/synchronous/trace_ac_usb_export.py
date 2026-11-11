"""Follow the regular AC renderer into the original secondary USB report builder."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_renderer import BASE, DISPLAY, INIT_BASE, SETTINGS, TABLE_SIZE, UNIT_TABLE, restore_globals
from trace_ac_native_formatter import FORMAT_WINDOWS, NativeNormal
from trace_secondary_channel1 import ChannelRegisters, INDEX, INITIAL_INDEX, LOG, USB, reference_events
from trace_secondary_usb_irq import MODE as USB_MODE, WINDOWS as USB_WINDOWS
from trace_secondary_usb_lifecycle import BUSY, CHUNK, READY_A, READY_B, SENDER_WINDOWS, SUBMIT
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

EXPORT_UNIT_TABLE = 0x805AB3D8
EXPORT, CACHE, CACHE_LENGTH = 0x8005F1A8, 0x805AC67D, 21
REPORT_FORMATTER, EXPORT_RETURN = 0x80000578, 0x80003418
EXPORT_WINDOWS = ((DISPLAY, 0x8004539C), (EXPORT, 0x8005F250), *SENDER_WINDOWS, *USB_WINDOWS, *FORMAT_WINDOWS)
GATES = {
    "ready": (1, 1, 1, 0),
    "mode-off": (0, 1, 1, 0),
    "other-mode": (2, 1, 1, 0),
    "ready-a-off": (1, 0, 1, 0),
    "ready-b-off": (1, 1, 0, 0),
    "busy": (1, 1, 1, 1),
    "nonzero-ready": (1, 2, 7, 0),
}
SAMPLES = ((-12345, 0), (2500, 0), (550, 1), (8388606, 7), (8388607, 255))


class UsbExportReplay(NativeNormal):
    def __init__(self, raw, initialized):
        widget_offset = UNIT_TABLE - INIT_BASE
        export_offset = EXPORT_UNIT_TABLE - INIT_BASE
        table = initialized[widget_offset:widget_offset + TABLE_SIZE]
        super().__init__(raw, table)
        self.export_unit_table = initialized[export_offset:export_offset + TABLE_SIZE]
        assert len(table) == len(self.export_unit_table) == TABLE_SIZE
        self.hardware = ChannelRegisters(self.u, [0])
        self.exporting = False
        self.export_records, self.report_formats, self.exports, self.busy_writes = [], [], [], []
        self.export_instructions = {}

    def code(self, u, pc, size, data):
        if self.exporting and pc == EXPORT_RETURN:
            self.exporting = False
        if self.in_view and pc == DISPLAY:
            assert not self.exporting
            r0, r1, lr = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
            assert (r1, lr) == (0, EXPORT_RETURN)
            # This marker is the argument of the legacy modeled sink. It
            # precedes USB-specific unit and category formatting.
            self.emitted.append(["display_text", self.string(r0)])
            self.exporting = True
        if not self.exporting:
            return super().code(u, pc, size, data)
        r0, r1, r2, lr = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR))
        if pc == REPORT_FORMATTER:
            assert size == 2 and u.reg_read(UC_ARM_REG_CPSR) & 0x20
            spec = self.string(r2, 8)
            assert r1 == 24 and (lr, spec) in ((0x80045208, "%s"), (0x80045310, "%s%s"))
            self.report_formats.append(spec)
        if pc == EXPORT:
            assert r0 == 1 and lr == 0x8004537C
            self.exports.append([r0, self.string(r1, 24)])
        if pc == SUBMIT:
            assert r1 == 64 and lr == 0x8005F244
            self.export_records.append(bytes(u.mem_read(r0, r1)))
        if pc == LOG:
            assert lr == 0x8005FC48
            self.return_leaf(u, lr, 0)
            return
        assert size in (2, 4) and any(lo <= pc < hi for lo, hi in EXPORT_WINDOWS), hex(pc)
        self.export_instructions[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        if self.exporting:
            if USB <= address < USB + 0x1000:
                return  # ChannelRegisters validates each peripheral access.
            if CACHE <= address and address + size <= CACHE + CACHE_LENGTH:
                return
            if address == BUSY:
                assert (u.reg_read(UC_ARM_REG_PC), size, value) == (0x80060D48, 1, 1)
                self.busy_writes.append(value)
                return
        super().write(u, access, address, size, value, data)

    def run(self, initial, gate, sample, selector):
        self.prepare_refresh_state(initial, 2)
        self.u.mem_write(EXPORT_UNIT_TABLE, self.export_unit_table)
        self.put(SETTINGS + 0x14, 1)
        self.put(USB_MODE, 0)
        self.put(CHUNK, 64)
        self.timer_refresh(2)
        assert not self.measurement(100, 0, True)["published"]
        self.timer_refresh(2)
        packet = self.measurement(sample & 0xFFFFFF, selector, True)
        assert packet["published"]
        mode, ready_a, ready_b, busy = GATES[gate]
        for address, value in ((USB_MODE, mode), (READY_A, ready_a), (READY_B, ready_b), (BUSY, busy)):
            self.put(address, value)
        self.report_formats.clear()
        self.exports.clear()
        self.export_records.clear()
        row = self.timer_refresh(2)
        assert not self.exporting
        rendered, = row["native_render_record"]
        text = rendered["text"] + rendered["unit"]
        assert self.report_formats == (["%s"] if rendered["text"] == ".OL" else ["%s%s"])
        assert self.exports == [[1, text]]
        padded = text.encode("ascii").ljust(20, b"\0")
        assert len(padded) == 20 and bytes(self.u.mem_read(CACHE, CACHE_LENGTH)) == b"\x01" + padded
        built = mode == 1 and bool(ready_a and ready_b)
        submitted = built and not busy
        expected = b"\x00\x04\x3f\x01" + padded + bytes(40)
        assert self.export_records == ([expected] if built else [])
        assert self.hardware.events == (reference_events(expected, [64]) if submitted else [])
        assert self.hardware.polls == ([0] if submitted else [])
        assert self.busy_writes == ([1] if submitted else [])
        assert bytes(self.u.mem_read(INDEX, 1)) == bytes((INITIAL_INDEX,))
        return dict(configuration=rendered["configuration"], usb_gate=gate, uart_sample=sample, uart_selector=selector,
                    widget_value=rendered["text"], widget_unit=rendered["unit"], report_text=text,
                    mirror_hex=(b"\x01" + padded).hex(), format=self.report_formats[0],
                    frame_built=built, frame=expected.hex() if built else None,
                    channel1_fifo=submitted, busy_after=bool(self.read(BUSY)))


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
        initialized = restore_globals(raw)
        cases, coverage = [], {}
        for initial, gate, (sample, selector) in product((0, 1), GATES, SAMPLES):
            replay = UsbExportReplay(raw, initialized)
            cases.append(replay.run(initial, gate, sample, selector))
            coverage.update(replay.export_instructions)
        observations.append((cases, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.ac-usb-export.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["The original AC result path, locale and formatters, export, report builder and USB sender execute.",
                          "USB mode, readiness, busy state and UART replies are seeded. USB registers and GUI label sinks are modeled.",
                          "Only the tested regular mode-0 AC configurations 9 and 10 are covered. No physical enumeration, transfer, pixels or timing is observed."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {len(cases)} original AC USB export cases per image, {2*len(cases)} total")


if __name__ == "__main__":
    main()
