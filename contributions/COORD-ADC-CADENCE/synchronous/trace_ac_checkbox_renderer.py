"""Execute the original AC result dispatcher and renderer on native refresh schedules."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_ac_checkbox_refresh import DISPATCH_RESULT, RENDER, RefreshAcReplay
from trace_control_gui_events import MODE
from trace_refresh_rendering import (
    DISPLAY, INIT_BASE, SETTINGS, TABLE_SIZE, UNIT_TABLE, WINDOWS as RENDER_WINDOWS,
    WIDGET_TEXT, RenderingReplay, f32, restore_globals,
)
from trace_scheduler_delay_wake import BASE
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
)

PRIMARY_WIDGET, UNIT_WIDGET = 0x10017700, 0x10017740
VIEW_END = 0x8005D1AC
FORMATTING_CALLERS = (0x80003BC4, 0x80003C40, 0x80003958)
VIEW_LEAVES = (0x8000406C, 0x80004114, 0x80004314, 0x80002E44, WIDGET_TEXT, DISPLAY)


class NativeViewReplay(RefreshAcReplay):
    string = RenderingReplay.string
    primary_widget, unit_widget = PRIMARY_WIDGET, UNIT_WIDGET

    def __init__(self, raw, table):
        super().__init__(raw)
        self.raw, self.table = raw, table
        self.in_view = False
        self.native_records, self.emitted = [], []

    def code(self, u, pc, size, data):
        if self.phase == "refresh" and pc == DISPATCH_RESULT:
            assert not self.in_view and u.reg_read(UC_ARM_REG_LR) == 0x8005D1A4
            self.in_view = True
            self.numeric_format = None
            self.view_entries.append([hex(pc), list(self.result_words())])
        if self.in_view and pc == VIEW_END:
            self.in_view = False
        if not self.in_view or pc in (0x8005D1A4, 0x8005D1A8):
            return super().code(u, pc, size, data)
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc == 0x80000544:
            fmt = self.string(r1, 8)
            assert size == 2
            if fmt == "%s":
                assert lr in (0x800037FC, 0x80003838)
                formatted = self.string(r2, 32).encode("ascii")
            else:
                assert (lr in FORMATTING_CALLERS and fmt == "%.3f") or (lr, fmt) == (0x80003B78, "%+.3f"), (hex(lr), fmt)
                value, = struct.unpack("<d", struct.pack("<II", r2, r3))
                self.numeric_format = "+.3f" if fmt == "%+.3f" else ".3f"
                formatted = format(value, self.numeric_format).encode("ascii")
            assert len(formatted) < 0x32
            u.mem_write(r0, formatted + b"\0")
            u.reg_write(UC_ARM_REG_CPSR, u.reg_read(UC_ARM_REG_CPSR) & ~0x20)
            self.return_leaf(u, lr, len(formatted))
            return
        if pc == RENDER:
            assert lr == VIEW_END
            raw, selector = self.result_words()
            self.view_entries.append([hex(pc), [raw, selector]])
            self.native_records.append(dict(
                raw=raw, selector=selector, configuration=u.mem_read(MODE + 7, 1)[0],
                text=self.string(r0, 0x32), unit=self.string(r0 + 0x32, 10), format=self.numeric_format,
                scale_bits=hex(self.read(r0 + 0x3C)), flags=bytes(u.mem_read(r0 + 0x40, 2)).hex(),
            ))
        if pc in VIEW_LEAVES:
            if pc == WIDGET_TEXT:
                assert r0 in (self.primary_widget, self.unit_widget)
                self.emitted.append([hex(r0), self.string(r1)])
            if pc == DISPLAY:
                assert r1 == 0
                self.emitted.append(["display_text", self.string(r0)])
            self.return_leaf(u, lr, r0)
            return
        assert size in (2, 4) and any(lo <= pc < hi for lo, hi in RENDER_WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        if self.in_view and MODE <= address and address + size <= MODE + 0x38:
            return
        super().write(u, access, address, size, value, data)

    def prepare_refresh_state(self, initial, warmup):
        configured = super().prepare_refresh_state(initial, warmup)
        self.u.mem_write(UNIT_TABLE, self.table)
        self.put(0x805AC38C, self.primary_widget)
        self.put(0x805AC390, self.unit_widget)
        self.put(SETTINGS + 0x14, 0)
        return configured

    def timer_refresh(self, expected_warmup):
        start, leaves = len(self.native_records), len(self.emitted)
        row = super().timer_refresh(expected_warmup)
        new = self.native_records[start:]
        outputs = self.emitted[leaves:]
        if expected_warmup == 2:
            record, = new
            assert record["configuration"] in (9, 10)
            assert (record["raw"], record["selector"]) == row["result_at_refresh"]
            self.check_record(record)
            assert outputs == [[hex(self.primary_widget), record["text"]], [hex(self.unit_widget), record["unit"]],
                               ["display_text", record["text"]]]
        else:
            assert not new and not outputs
        row["native_render_record"] = new
        row["render_output"] = outputs
        return row


    def check_record(self, record):
        configuration = record["configuration"]
        raw, selector = record["raw"], record["selector"]
        if raw == 0x7FFFFF:
            assert (record["text"], record["unit"], record["format"], record["scale_bits"], record["flags"]) == (
                ".OL", "", None, "0x0", "0101",
            )
            return
        signed = raw if raw < 0x80000000 else raw - 0x100000000
        offset = 0x80063817 - BASE + 7 * configuration + selector
        expected = f32(f32(signed) / 10 ** self.raw[offset])
        if configuration == 10:
            cutoff = 5.5 if self.read(SETTINGS + 0x14) == 1 else 2.5
            if expected < cutoff:
                expected = 0.0
        assert record["scale_bits"] == hex(struct.unpack("<I", struct.pack("<f", expected))[0])
        assert record["unit"] == "V"
        assert record["format"] == ("+.3f" if configuration == 9 else ".3f")
        assert record["text"] == format(expected, record["format"])
        assert record["flags"] == "0001"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, originals = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        originals.append((item["version"], raw))
    tables = {}
    observations = []
    for version, raw in originals:
        init = restore_globals(raw)
        offset = UNIT_TABLE - INIT_BASE
        table = init[offset:offset + TABLE_SIZE]
        assert len(table) == TABLE_SIZE
        tables[version] = hashlib.sha256(table).hexdigest()
        coverage, cases = {}, []
        for case in product((0, 1), (0, 2), (False, True)):
            replay = NativeViewReplay(raw, table)
            case_row = replay.run_refreshes(*case)
            for refresh in case_row["refreshes"]:
                refresh["native_view_reads"] = refresh.pop("modeled_view_reads")
            cases.append(case_row)
            coverage.update(replay.coverage)
        observations.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    assert len(set(tables.values())) == 1
    report = dict(schema="ys4470.ac-checkbox-native-renderer.v1", images=images,
                  factory_unit_table_sha256=tables["V3.8"], **observations[0],
                  factory_initialization=dict(
                      scatter_descriptors={"0x805aaa68": "0x80000124", "0x805aaa78": "0x800000c8"},
                      unit_table_address=hex(UNIT_TABLE), unit_table_size=TABLE_SIZE,
                      unit_table_sha256_by_image=tables),
                  limits=[
        "The original mode-0 result dispatcher, floating-point scale and renderer execute after the native checkbox and UART path.",
        "Each image initializes its own unit table through its original scatter descriptors and code. The numeric formatter, selected GUI calls and display sink are modeled.",
        "The test checks CPU-visible text and labels against the original scale table and stored result. Physical input, conversion units and screen pixels remain outside the model.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 original AC renderer schedules per factory image, 16 total")


if __name__ == "__main__":
    main()
