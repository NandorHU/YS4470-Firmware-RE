"""Replay native Buzzer mode transitions and bound Fast CONT history writers."""

import argparse
import json
import struct
import sys
from itertools import product
from pathlib import Path

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT / "contributions/COORD-ADC-CADENCE/synchronous"))
from trace_deferred_producers import BASE, CTRL, FSM, SERVICE
from trace_deferred_measurement import FRAMES, LISTS
from trace_dynamic_type2 import TIMER, UI
from trace_refresh_publication import HANDLE, TIMER_STATE, RefreshReplay
from trace_refresh_rendering import PWM, RenderingReplay
from trace_uart_correlation import RESULT, RET, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R4, UC_ARM_REG_R6, UC_ARM_REG_R7

ENTRY = 0x8000CFD0
HISTORY = 0x805AC7B8
ACTIVE = 0x805AB924
SETTING = 0x805AC788
STORED = (14023, 3)
HISTORY_BYTES = struct.pack("<3I", 5, 6, 7)
FILTER_BYTES = struct.pack("<3I", 2, 3, 5)
WINDOWS = (
    (0x800028FC, 0x80002990), (0x8000299C, 0x800029D4),
    (ENTRY, 0x8000D1A0), (0x80024CA4, 0x80024CD8),
    (0x8005E9B0, 0x8005E9EC), (0x8005F254, 0x8005F274),
)
LEAVES = (0x800339BC, 0x8003A718, 0x80032038)


class ModeReplay(RefreshReplay):
    def code(self, u, pc, size, data):
        if pc in LEAVES:
            self.ui_models.append(hex(pc))
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and address in (UI, UI + 6, UI + 10):
            assert size == 1
            return
        super().memory(u, access, address, size, value, data)

    def snapshot(self):
        return (
            self.result(),
            bytes(self.u.mem_read(HISTORY, 12)).hex(),
            bytes(self.u.mem_read(ACTIVE + 4, 12)).hex(),
        )

    def run_case(self, old_mode, fast, discard):
        self.prepare()
        self.ui_models, self.measurement_starts = [], []
        self.u.mem_write(TIMER_STATE, b"\1" + bytes(0x13))
        self.u.reg_write(UC_ARM_REG_R6, UI)
        self.u.reg_write(UC_ARM_REG_R7, HANDLE)
        self.invoke(0x800518BC)
        self.u.mem_write(UI, bytes((old_mode, 1, 1, 0, 0, 0, 0, 9, 0x19, 9, 1)))
        self.put(SETTING, fast)
        self.put(RESULT + 0x1C, STORED[0])
        self.put(RESULT + 0x20, STORED[1])
        self.u.mem_write(CTRL + 1, bytes((discard,)))
        self.u.mem_write(HISTORY, HISTORY_BYTES)
        self.u.mem_write(ACTIVE + 4, FILTER_BYTES)
        before = self.snapshot()
        self.invoke(ENTRY)
        mode = 3 if old_mode == 4 else 4
        kind = 5 if mode == 4 and fast == 1 else 2
        record = (5, 0x22, 0x13) if kind == 5 else (2, 0x0E, 0x19)
        assert self.byte(UI) == mode and self.byte(UI + 9) == 1
        assert self.byte(UI + 1) == self.byte(UI + 10) == 0
        assert self.rd(TIMER) == 100 and self.enqueued[0][:6] == struct.pack("<IBB", *record)
        assert self.snapshot() == before and self.byte(CTRL + 1) == discard
        self.invoke(SERVICE)
        sequence = LISTS[kind]
        assert self.builder_calls == [(3, sequence, 0x80004414 if kind == 5 else 0x80004480)]
        assert self.snapshot() == before and self.byte(CTRL + 1) == 2
        delivered = 0
        for tick in range(1, 180):
            self.set_tick(tick)
            if delivered < len(self.sent):
                command = self.sent[-1]
                packet = b"\x60\x32\x00\x00\x03" if command == 0x1D else FRAMES[command][:1]
                for value in packet:
                    self.receive(value)
                delivered += 1
            self.step(tick)
            if self.byte(FSM + 0x34) == 0:
                break
        assert self.byte(FSM + 0x34) == 0 and tuple(self.sent) == sequence
        assert bytes(self.wire) == b"".join(FRAMES[command] for command in sequence)
        assert self.snapshot() == before and self.byte(CTRL + 1) == 1
        assert [e["frame"] for e in self.events if e["kind"] == "parse"] == ["6032000003"]
        assert not any(e["kind"] == "publish" for e in self.events)
        return dict(old_mode=old_mode, new_mode=mode, fast_cont=fast, record_prefix=self.enqueued[0][:6].hex(),
                    commands=[hex(cmd) for cmd in sequence], wire_hex=bytes(self.wire).hex(),
                    discard=[discard, discard, 2, 1], retained_snapshot=before)


class SoundCountdown(RenderingReplay):
    def code(self, u, pc, size, data):
        if pc == 0x80005578:
            u.reg_write(UC_ARM_REG_PC, RET)
            return
        if 0x8000553C <= pc < 0x80005578:
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and address == RESULT + 0x18:
            assert size == 4
            return
        super().memory(u, access, address, size, value, data)

    def run_suffix(self, countdown, active):
        self.audio_enabled = True
        self.audio = []
        self.prepare()
        self.put(SETTING - 8, 1)
        self.put(SETTING - 12, 90)
        self.put(RESULT + 0x50, countdown)
        self.put(ACTIVE, active)
        self.put(RESULT + 0x1C, STORED[0])
        self.put(RESULT + 0x20, STORED[1])
        self.u.mem_write(HISTORY, HISTORY_BYTES)
        self.u.mem_write(ACTIVE + 4, FILTER_BYTES)
        self.put(PWM, 0x7F if active else 0)
        self.put(PWM + 4, 0x176F0A8C if active else 0)
        self.u.reg_write(UC_ARM_REG_R4, RESULT)
        self.u.reg_write(UC_ARM_REG_R6, ACTIVE)
        self.invoke(0x8000553C)
        expires = active == 1 and countdown <= 1
        assert self.rd(ACTIVE) == (0 if expires else active)
        assert self.rd(RESULT + 0x50) == max(countdown - 1, 0)
        assert self.rd(RESULT + 0x18) == 1
        assert self.result() == STORED
        assert bytes(self.u.mem_read(HISTORY, 12)) == HISTORY_BYTES
        assert bytes(self.u.mem_read(ACTIVE + 4, 12)) == FILTER_BYTES
        assert self.audio == ([["0x80005568", 5, 0]] if expires else [])
        assert not expires or self.rd(PWM + 4) & 0xFFFF == 0
        return dict(initial_countdown=countdown, initial_active=active, expired=expires,
                    active_after=self.rd(ACTIVE), countdown_after=self.rd(RESULT + 0x50),
                    pwm_period_after=hex(self.rd(PWM + 4)), retained_raw=self.result())


def index(raw):
    result = []
    targets = set(range(ACTIVE, ACTIVE + 16, 4)) | set(range(HISTORY, HISTORY + 12, 4))
    for index, (word,) in enumerate(struct.iter_unpack("<I", raw)):
        if word & 0x0F7F0000 != 0x051F0000:
            continue
        address = BASE + 4 * index
        literal = address + 8 + (word & 0xFFF) * (1 if word & 0x800000 else -1)
        if not 0 <= literal - BASE <= len(raw) - 4:
            continue
        value, = struct.unpack_from("<I", raw, literal - BASE)
        if value in targets:
            result.append(dict(pc=hex(address), literal=hex(literal), pointer=hex(value),
                               bytes=raw[index*4:index*4+4].hex()))
    assert [x["pc"] for x in result] == ["0x80005520", "0x80006e84", "0x80007c8c", "0x80007c90"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="-", help="JSON path, or - for standard output")
    args = parser.parse_args()
    manifest = json.loads((ROOT / "original-firmware/manifest.json").read_text())
    rows, versions = [], []
    for item in manifest["images"]:
        raw = (ROOT / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        assert struct.unpack_from("<I", raw, 0x800519B4 - BASE)[0] == ENTRY
        replay = ModeReplay(raw)
        cases = [replay.run_case(*args) for args in product((1, 4), (0, 1), (0, 1))]
        countdown = SoundCountdown(raw)
        expiries = [countdown.run_suffix(*args) for args in product((0, 1, 2), (0, 1))]
        rows.append((cases, index(raw), {hex(pc): val for pc, val in sorted(replay.coverage.items())},
                     expiries, {hex(pc): val for pc, val in sorted(countdown.coverage.items())}))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"],
                             mode_cases=len(cases), countdown_cases=len(expiries)))
    assert rows[0] == rows[1]
    output = json.dumps(dict(schema="ys4470.native-fast-cont-transition.v1", versions=versions,
        entry=hex(ENTRY), binding_literal="0x800519b4", cases=rows[0][0], literal_hits=rows[0][1],
        instruction_bytes=rows[0][2], countdown_cases=rows[0][3], countdown_instruction_bytes=rows[0][4],
        limits=["Original mode callback, timer state update, queue, dispatcher and FSM execute.",
                "Graphical leaves, entry feedback, heap, counters and UART arrivals are controlled fixtures.",
                "Countdown replay starts at 0x8000553c and stops before the next outer-loop iteration.",
                "Aligned ARM PC-relative load scan covers the named literal values, excluding synthesized aliases."]),
        indent=2) + "\n"
    if args.out == "-":
        print(output, end="")
    else:
        Path(args.out).write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
