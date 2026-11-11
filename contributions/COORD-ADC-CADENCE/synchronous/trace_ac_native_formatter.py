"""Execute the original C runtime locale and AC numeric formatter on both display paths."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_renderer import BASE, INIT_BASE, TABLE_SIZE, UNIT_TABLE, NativeViewReplay, restore_globals
from trace_ac_highspeed_result import HighspeedReplay
from trace_ac_result_boundaries import replay_path
from trace_scheduler_delay_wake import STACK
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
)

LOCALE_INIT, LOCALE_STORE = 0x800001D0, 0x800001E0
LOCALE_SLOT, C_LOCALE, FORMATTER = 0x80D5B894, 0x805AAAA4, 0x80000544
LOCALE_WINDOWS = ((LOCALE_INIT, 0x800001E4), (0x800017B0, 0x800017B8), (0x80062388, 0x800623C8))
FORMAT_WINDOWS = ((0x80000178, 0x80002900), (0x80008624, 0x80008F7E), (0x80062388, 0x80063600))
NORMAL_CALLS = {0x800037FC: "%s", 0x80003838: "%s", 0x80003B78: "%+.3f", 0x80003BC4: "%.3f"}
HIGHSPEED_CALLS = {
    0x8005DC78: "%s", 0x8005DC98: "%s", 0x8005DCF0: "%.3f", 0x8005DD30: "%+.3f", 0x8005DD5C: "%.3f",
}


class FirmwareFormatter:
    def __init__(self, *args):
        super().__init__(*args)
        self.format_pending = None
        self.format_count = 0
        self.format_instructions = {}
        self.locale_writes = []

    def prepare_refresh_state(self, initial, warmup):
        setup = super().prepare_refresh_state(initial, warmup)
        self.u.mem_map(LOCALE_SLOT & ~0xFFF, 0x1000)
        self.phase = "locale"
        try:
            self.invoke(LOCALE_INIT | 1)
        finally:
            self.phase = None
        assert self.locale_writes == [C_LOCALE] and self.read(LOCALE_SLOT) == C_LOCALE
        decimal_offset = self.read(C_LOCALE)
        assert decimal_offset == 12 and bytes(self.u.mem_read(C_LOCALE + decimal_offset, 2)) == b".\0"
        return setup

    def code(self, u, pc, size, data):
        if self.phase == "locale" and any(lo <= pc < hi for lo, hi in LOCALE_WINDOWS):
            assert size in (2, 4)
            self.format_instructions[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        if self.format_pending is not None:
            destination, spec, return_pc = self.format_pending
            if pc == return_pc:
                text = self.string(destination, 0x32)
                assert u.reg_read(UC_ARM_REG_R0) == len(text)
                if self.phase == "highspeed":
                    self.formats.append([hex(return_pc), spec, text])
                self.format_pending = None
            else:
                assert size in (2, 4) and any(lo <= pc < hi for lo, hi in FORMAT_WINDOWS), hex(pc)
                self.format_instructions[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        if pc == FORMATTER and (self.phase == "highspeed" or getattr(self, "in_view", False)):
            destination = u.reg_read(UC_ARM_REG_R0)
            spec = self.string(u.reg_read(UC_ARM_REG_R1), 8)
            return_pc = u.reg_read(UC_ARM_REG_LR)
            calls = HIGHSPEED_CALLS if self.phase == "highspeed" else NORMAL_CALLS
            assert size == 2 and u.reg_read(UC_ARM_REG_CPSR) & 0x20 and calls[return_pc] == spec
            assert STACK - 0x300 <= destination < STACK
            if self.phase == "refresh" and spec != "%s":
                self.numeric_format = spec[1:]
            self.format_pending = (destination, spec, return_pc)
            self.format_count += 1
            self.format_instructions[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "locale" and address == LOCALE_SLOT:
            assert (u.reg_read(UC_ARM_REG_PC), size, value) == (LOCALE_STORE, 4, C_LOCALE)
            self.locale_writes.append(value)
            return
        if self.format_pending is not None:
            destination, _, _ = self.format_pending
            if destination <= address < destination + 0x32:
                assert size == 1
                return
        super().write(u, access, address, size, value, data)


class NativeNormal(FirmwareFormatter, NativeViewReplay):
    pass


class NativeHighspeed(FirmwareFormatter, HighspeedReplay):
    pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    references = {}
    for name in ("ac-result-boundaries-validation.json", "ac-highspeed-result-validation.json"):
        data = Path(__file__).with_name(name).read_bytes()
        references[name] = (json.loads(data), hashlib.sha256(data).hexdigest())
    regular, highspeed = (data for data, _ in references.values())
    previous_highspeed = {(p["configuration"], p["filter_word"]): p for p in highspeed["paths"]}
    images, observations = {}, []
    for entry in manifest["images"]:
        raw = Path(entry["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry["sha256"] and len(raw) == entry["size_bytes"]
        images[entry["version"]] = digest
        offset = UNIT_TABLE - INIT_BASE
        table = restore_globals(raw)[offset:offset + TABLE_SIZE]
        assert len(table) == TABLE_SIZE
        paths, coverage = [], {}
        for initial, setting in product((0, 1), repeat=2):
            prior = next(p for p in regular["paths"] if p["configuration"] == (9 if initial else 10)
                         and p["cutoff_setting"] == setting)
            normal = NativeNormal(raw, table)
            path = replay_path(normal, initial, setting)
            assert path == prior and normal.format_pending is None
            configuration = prior["configuration"]
            speed = NativeHighspeed(raw)
            labels = {(row[0], row[1]): row[6] for row in prior["cases"]}
            result = speed.run(configuration, setting, table, labels)
            assert result == previous_highspeed[configuration, setting] and speed.format_pending is None
            paths.append(dict(configuration=configuration, filter_word=setting,
                              regular_samples=len(path["cases"]), highspeed_samples=len(result["cases"]),
                              regular_format_calls=normal.format_count, highspeed_format_calls=speed.format_count))
            coverage.update(normal.format_instructions)
            coverage.update(speed.format_instructions)
        observations.append((paths, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and images == regular["images"] == highspeed["images"]
    assert observations[0] == observations[1]
    paths, coverage = observations[0]
    report = dict(schema="ys4470.ac-native-formatter.v1", images=images, paths=paths,
                  locale_init=hex(LOCALE_INIT), locale_pointer_store=hex(LOCALE_STORE),
                  locale_slot=hex(LOCALE_SLOT), locale_table=hex(C_LOCALE),
                  matched_reports_sha256={name: digest for name, (_, digest) in references.items()},
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["The original locale initialization and all string and numeric formatting calls execute.",
                          "Normal and highspeed labels match the earlier modeled-format outputs for these specific samples.",
                          "GUI label/widget sinks, hardware peers and timer-list traversal remain modeled."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    count = sum(p["regular_samples"] + p["highspeed_samples"] for p in paths)
    print(f"PASS {count} original formatter cases per factory image, {2*count} total")


if __name__ == "__main__":
    main()
