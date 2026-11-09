"""Execute original ResultDispatch, text formatting and renderer in refresh schedules."""

import argparse
import json
import struct
import sys
from pathlib import Path

from trace_deferred_producers import BASE
from trace_dynamic_type2 import UI
from trace_refresh_publication import RefreshReplay
from trace_type6_queue import QUEUE
from trace_uart_correlation import RET, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trace_profiles import restore_globals

WIDGET_TEXT = 0x80032038
DISPLAY = 0x80045184
SETTINGS = 0x805AC770
PRIMARY_WIDGET = 0x10017800
UNIT_WIDGET = 0x10017900
INIT_BASE = 0x805AAAB4
UNIT_TABLE = 0x805AAE98
TABLE_SIZE = 0x30 * 7 * 4
ACTIVE = 0x805AB924
HISTORY = 0x805AC7B8
PWM = 0x01C21000
WINDOWS = (
    (0x80000000, 0x80002900), (0x8000326C, 0x8000378C),
    (0x800037C0, 0x80003AD0), (0x80003B18, 0x80003C48), (0x80003C5C, 0x80003D40),
    (0x80008624, 0x80008F7E), (0x800427EC, 0x8004283C), (0x80062000, 0x80063600),
    (0x8000302C, 0x800030C4), (0x800060D0, 0x80006174), (0x80006E4C, 0x80006EF4),
    (0x80007C88, 0x80007DD0), (0x80042D40, 0x80042F10),
)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


class RenderingReplay(RefreshReplay):
    def string(self, ptr, limit=64):
        data = bytes(self.u.mem_read(ptr, limit))
        assert b"\0" in data
        return data.split(b"\0", 1)[0].decode("ascii")

    def setup_run(self, event_type):
        self.rendered, self.boundary, self.audio, self.filter_inputs = [], [], [], []
        self.audio_enabled = False
        result = super().setup_run(event_type)
        table_offset = UNIT_TABLE - INIT_BASE
        self.u.mem_write(UNIT_TABLE, self.initialized_globals[table_offset:table_offset + TABLE_SIZE])
        self.put(0x805AC38C, PRIMARY_WIDGET)
        self.put(0x805AC390, UNIT_WIDGET)
        self.put(SETTINGS + 0x14, 0)
        return result

    def code(self, u, pc, size, data):
        r0, r1, lr = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
        if pc == 0x80000544 and lr in (0x80003C40, 0x80003958):
            assert self.string(r1, 8) == "%.3f"
            lo, hi = (u.reg_read(reg) for reg in (UC_ARM_REG_R2, UC_ARM_REG_R3))
            value, = struct.unpack("<d", struct.pack("<II", lo, hi))
            output = f"{value:.3f}".encode("ascii")
            assert len(output) < 0x32
            u.mem_write(r0, output + b"\0")
            u.reg_write(UC_ARM_REG_R0, len(output))
            u.reg_write(UC_ARM_REG_CPSR, u.reg_read(UC_ARM_REG_CPSR) & ~0x20)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc == 0x800037C0:
            self.presented.append(self.result())
        if pc == 0x8000326C:
            self.boundary.append(dict(raw=self.result(), mode=self.byte(UI), configuration=self.byte(UI + 7),
                                      text=self.string(r0, 0x32), unit=self.string(r0 + 0x32, 10),
                                      scale_bits=hex(self.rd(r0 + 0x3C)), flags=bytes(u.mem_read(r0 + 0x40, 2)).hex()))
        if pc == 0x80007C88:
            self.filter_inputs.append(r0)
        if pc == 0x80006E4C:
            if lr == RET:
                return super().code(u, pc, size, data)
            self.audio.append([hex(lr - 4), r0, r1])
            assert self.audio_enabled
        if pc in (0x8000406C, 0x80004114, 0x80004314, 0x80002E44, WIDGET_TEXT, DISPLAY):
            if pc == WIDGET_TEXT:
                assert r0 in (PRIMARY_WIDGET, UNIT_WIDGET)
                self.rendered.append((hex(r0), self.string(r1)))
            if pc == DISPLAY:
                assert r1 == 0
                self.rendered.append(("display_text", self.string(r0)))
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size in (2, 4)
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and UI <= address and address + size <= UI + 0x38:
            return
        if self.audio_enabled:
            if address in (0x01C20800, 0x01C2081C, PWM, PWM + 4):
                assert size == 4
                return
            if access == UC_MEM_WRITE and size == 4 and address in (
                ACTIVE, ACTIVE + 4, ACTIVE + 8, ACTIVE + 12, HISTORY, HISTORY + 4, HISTORY + 8,
                0x805AC764,
            ):
                return
        super().memory(u, access, address, size, value, data)

    def refresh_at(self, tick, event_type):
        before = len(self.boundary)
        labels = len(self.rendered)
        row = super().refresh_at(tick, event_type)
        records = self.boundary[before:]
        emitted = self.rendered[labels:]
        assert len(records) == len(row["dispatch_read"])
        if records:
            entry, = records
            assert entry["raw"] == row["result_at_refresh"]
            raw, selector = entry["raw"]
            if entry["mode"] == 4:
                assert self.audio_enabled and entry["configuration"] == 0x22
                divisor = struct.unpack("<f", struct.pack("<I", 0x452F499A))[0]
            elif entry["configuration"] == 0x22:
                divisor = struct.unpack("<f", struct.pack("<I", 0x41DFD1B7))[0]
            else:
                assert entry["configuration"] == 0x0C
                offset = 0x80063817 - BASE + 7 * 0x0C + selector
                divisor = 10 ** self.raw[offset]
            scaled = f32(f32(raw) / divisor)
            bits = struct.unpack("<I", struct.pack("<f", scaled))[0]
            assert int(entry["scale_bits"], 16) == bits
            assert entry["text"] == f"{scaled:.3f}"
            assert emitted == [(hex(PRIMARY_WIDGET), entry["text"]), (hex(UNIT_WIDGET), entry["unit"]),
                               ("display_text", entry["text"])]
        else:
            assert not emitted
        row["original_record"] = records
        row["original_renderer_leaves"] = emitted
        return row

    def run_audio(self):
        self.setup_run(4)
        self.u.mem_write(UI, b"\4")
        self.put(SETTINGS + 0x18, 1)
        self.put(SETTINGS + 0x10, 1)
        self.put(SETTINGS + 0x0C, 90)
        self.put(ACTIVE + 12, 0xFFFFFFFF)
        for offset in (0, 4, 8):
            self.put(HISTORY + offset, 1000)
        self.put(PWM, 0)
        self.put(PWM + 4, 0)
        self.audio_enabled = True
        for tick, raw in ((100, 101), (200, 14023)):
            self.refresh_at(tick, 4)
            self.finish_request(tick, 4, raw, 0, "none")
        assert self.result() == (14023, 0)
        parser_count = sum(event["kind"] == "parse" for event in self.events)
        publication_count = sum(event["kind"] == "publish" for event in self.events)
        assert publication_count == 1
        samples = []
        for count, tick in enumerate((300, 325, 350), 1):
            row = self.refresh_at(tick, 4)
            assert self.rd(ACTIVE + 8) == count
            assert self.rd(ACTIVE + 12) == (5 if count == 3 else 0xFFFFFFFF)
            assert self.rd(ACTIVE) == int(count == 3)
            assert bool(self.rd(PWM) & 0x10) == (count == 3)
            samples.append(dict(refresh=row, filter_count=count, median_word=self.rd(ACTIVE + 12),
                                pwm_control=hex(self.rd(PWM)), pwm_period=hex(self.rd(PWM + 4))))
        assert self.filter_inputs == [5, 5, 5] and self.result() == (14023, 0)
        assert sum(event["kind"] == "parse" for event in self.events) == parser_count
        assert sum(event["kind"] == "publish" for event in self.events) == publication_count
        assert self.rd(QUEUE + 0x38) == 3
        assert self.rd(PWM) == 0x7F and self.rd(PWM + 4) == 0x176F0A8C
        assert [args[1:] for args in self.audio] == [[0, 0], [0, 0], [10, 1]]
        return dict(one_publication_reused=samples, filter_inputs=self.filter_inputs, queued_requests=3,
                    original_sound_gate_calls=self.audio)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    originals = [(item, (root / item["path"]).read_bytes()) for item in manifest["images"]]
    assert all(sha(raw) == item["sha256"] and len(raw) == item["size_bytes"] for item, raw in originals)
    init = restore_globals(next(raw for item, raw in originals if item["version"] == "V3.8"))
    all_results, versions = [], []
    for item, raw in originals:
        m = RenderingReplay(raw)
        m.initialized_globals = init
        sequences = [m.run_sequence(kind, fault) for kind in (3, 4) for fault in ("none", "missing", "wrong")]
        overlap = m.run_overlap()
        reconfigured = [m.run_reconfigure(kind) for kind in (3, 4)]
        audio = m.run_audio()
        all_results.append((sequences, overlap, reconfigured, audio,
                            {hex(pc): val for pc, val in sorted(m.coverage.items())}))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=10))
    assert all_results[0] == all_results[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.refresh-rendering.v1", versions=versions, init_globals_sha256=sha(init),
        source_sha256=sha(Path(__file__).read_text(encoding="utf-8").encode("utf-8")),
        reused_refresh_source_sha256=sha(Path(__file__).with_name("trace_refresh_publication.py")
                                        .read_text(encoding="utf-8").encode("utf-8")),
        sequences=all_results[0][0], overlap=all_results[0][1], reconfigured=all_results[0][2],
        audio=all_results[0][3], instruction_bytes=all_results[0][4],
        limits=["Original dispatcher, float arithmetic, string copy and renderer execute in UI mode 1 with display flag 0.",
                "Mode 4, sound enable and initial filter state are fixtures for the integrated original Fast CONT/PWM trace.",
                "The numeric %.3f formatter, widget/display updates and UI feedback are modeled leaves.",
                "The original numeric formatter exceeded the instruction budget. Text values use a controlled formatting model."],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS 18 original refresh-to-renderer and 2 integrated Fast CONT/PWM schedules")


if __name__ == "__main__":
    main()
