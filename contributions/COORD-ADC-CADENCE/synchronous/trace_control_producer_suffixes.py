"""Replay indexed native ARM caller suffixes through the original control queue."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from trace_gauge_scheduled_service import CTRL, PRODUCER, QUEUE, RECORD_SIZE, SELECTION, GaugeReplay
from trace_scheduler_delay_wake import BASE, RET, SCHED, STACK, TASK
from trace_timer0_uart2_irq import RESULT
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
)

INIT = 0x800029DC
SEND = 0x80061ACC
DATA4, DATA5 = 0x10016020, 0x10016040
START = {
    0x8000CE54: 0x8000CE40, 0x8000D350: 0x8000D33C, 0x8000D39C: 0x8000D378,
    0x8000E2DC: 0x8000E2C4, 0x8000E36C: 0x8000E354, 0x8000E3F4: 0x8000E3DC,
    0x8000E480: 0x8000E468, 0x8000E50C: 0x8000E4F4, 0x8000E5A0: 0x8000E588,
    0x8000E634: 0x8000E61C, 0x8000E6C4: 0x8000E6AC, 0x8000E750: 0x8000E738,
    0x8000E7E0: 0x8000E7C4, 0x8005D130: 0x8005D118,
}
R1, R2, R6 = 0x112233A1, 0x223344B2, 0x334455C6
ARG_REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
# Expected incoming args for suffixes that replace r1 or r2. The 0x8000d6d0 first argument passes through.
ARGS = {
    0x8000CE54: (0x57, 0x19), 0x8000CF00: (0xF, 0x19),
    0x8000D0A0: (0x22, 0x13), 0x8000D0C8: (0xE, 0x19),
    0x8000D350: (0x22, R6), 0x8000D39C: (0xC, 0x19),
    0x8000D5C0: (0xC, 0x19), 0x8000D6D0: (R1, 0x13),
    0x8000D718: (0x47, 0x15), 0x8000D7C8: (9, 0x19),
    0x8000E2DC: (9, 0x19), 0x8000E36C: (0xC, 0x19), 0x8000E3F4: (0xF, 0x19),
    0x8000E480: (0xF, 0x19), 0x8000E50C: (0x28, 0), 0x8000E5A0: (0x29, 0),
    0x8000E634: (9, 0x13), 0x8000E6C4: (0x2B, 0), 0x8000E750: (0x2A, 0),
    0x8000E7E0: (0x27, 0x13), 0x8000F414: (0xA, 0x19),
    0x8000F49C: (9, 0x19), 0x80044F2C: (9, 0x19),
    0x80044F80: (0xC, 0x19), 0x80044FDC: (0xF, 0x19),
    0x80045050: (0xE, 0x19), 0x800450D0: (0xE, 0x19),
    0x8004513C: (0x22, 0x13), 0x800519E0: (9, 0x19),
    0x8005D130: (0, 0), 0x8005DC38: (0, 0),
}


class CallerReplay(GaugeReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.site = self.start = 0
        self.caller_stores = []
        self.handle_writes = []
        self.entries = []
        self.sends = []
        self.probe_start = self.probe_stop = 0
        self.result_stores = []

    def code(self, u, pc, size, data):
        if self.probe_start:
            if pc == self.probe_stop:
                u.emu_stop()
                return
            assert self.probe_start <= pc < self.probe_stop and size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        if self.site and pc == self.site + 4:
            u.emu_stop()
            return
        if self.site and self.start <= pc <= self.site:
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        if pc == PRODUCER:
            regs = [u.reg_read(reg) for reg in ARG_REGS[:3]]
            self.entries.append([hex(u.reg_read(UC_ARM_REG_LR)), regs])
        elif pc == SEND:
            queue, src, wait, mode = (u.reg_read(reg) for reg in ARG_REGS)
            assert queue == QUEUE and mode == 0
            assert u.reg_read(UC_ARM_REG_LR) == 0x800067BC
            self.sends.append((wait, bytes(u.mem_read(src, RECORD_SIZE))))
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if self.probe_start:
            assert 0x8005D35C <= pc < 0x8005D374 and RESULT + 0x28 <= address <= RESULT + 0x3C
            assert size == 4 and value == 0
            self.result_stores.append([hex(pc), hex(address)])
            return
        if CTRL + 4 <= address < CTRL + 8:
            self.handle_writes.append([hex(pc), hex(address), size, hex(value)])
        if address in (SELECTION, SELECTION + 1, DATA4 + 7, DATA4 + 8, DATA5 + 8):
            assert self.start <= pc < self.site and size == 1
            self.caller_stores.append([hex(pc), hex(address), value])
            return
        super().write(u, access, address, size, value, data)

    def run(self, row, kind, state):
        self.site = 0
        self.seed("idle")
        u = self.u
        u.mem_write(CTRL, bytes(16))
        u.mem_write(QUEUE, b"\xA5" * 760)
        u.mem_write(DATA4, bytes(16))
        u.mem_write(DATA4 + 7, bytes((state if int(row["address"], 16) == 0x8005D130 else 0x47, 0x48)))
        u.mem_write(DATA4 + 1, bytes((state,)))
        u.mem_write(SELECTION, b"\xA5\xA5")
        u.mem_write(DATA5 + 7, b"\x57")
        self.handle_writes.clear()
        self.invoke_transport(INIT)
        initial_handle_write, = self.handle_writes
        assert initial_handle_write == ["0x800029f4", hex(CTRL + 4), 4, hex(QUEUE)]
        assert self.read(CTRL + 4) == QUEUE
        assert tuple(self.read(QUEUE + offset) for offset in (0x38, 0x3C, 0x40)) == (0, 10, RECORD_SIZE)
        buffer = self.read(QUEUE)
        assert bytes(u.mem_read(buffer, 10 * RECORD_SIZE)) == b"\xA5" * (10 * RECORD_SIZE)
        self.entries.clear()
        self.sends.clear()
        self.caller_stores.clear()
        self.events.clear()
        self.site = int(row["address"], 16)
        self.start = START.get(self.site, self.site - 12)
        stop = self.site + 4
        for pc, word in ((int(i["pc"], 16), i["bytes"]) for i in row["instructions"]):
            assert bytes(u.mem_read(pc, 4)).hex() == word
        u.reg_write(UC_ARM_REG_CPSR, 0x13)
        u.reg_write(UC_ARM_REG_SP, STACK)
        u.reg_write(UC_ARM_REG_LR, RET)
        for reg, value in zip(
            (*ARG_REGS, UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6),
            (0x13, R1, R2, 0, DATA4, DATA5, R6),
        ):
            u.reg_write(reg, value)
        self.transport_active = True
        try:
            u.emu_start(self.start, 0, count=10000)
        finally:
            self.transport_active = False

        r1, r2 = ARGS[self.site]
        if self.site == 0x8000D39C and state == 1:
            r2 = R6 & 255
        expected = struct.pack("<IBB", kind, r1 & 255, r2 & 255)
        assert self.entries == [[hex(stop), [kind, r1, r2]]]
        (wait, record), = self.sends
        assert wait == (0 if kind == 3 else 10) and record[:6] == expected
        assert bytes(u.mem_read(buffer, RECORD_SIZE)) == record
        assert bytes(u.mem_read(buffer + RECORD_SIZE, 9 * RECORD_SIZE)) == b"\xA5" * (9 * RECORD_SIZE)
        assert self.read(QUEUE + 8) == buffer + RECORD_SIZE and self.read(QUEUE + 0x38) == 1
        assert self.handle_writes == [initial_handle_write] and self.read(CTRL + 4) == QUEUE
        assert self.read(SCHED) == TASK and self.read(SCHED + 0xC) == 100 and self.read(SCHED + 0x3C) == 0
        assert not any(event[:1] in (["delay"], ["yield"], ["svc"]) for event in self.events)
        assert u.reg_read(UC_ARM_REG_PC) == stop and u.reg_read(UC_ARM_REG_SP) == STACK
        assert u.reg_read(UC_ARM_REG_R0) == 1 and not u.reg_read(UC_ARM_REG_CPSR) & 0x80
        if self.site == 0x8000D39C:
            assert bytes(u.mem_read(DATA4 + 8, 1)) == bytes((r2,))
            assert len(self.caller_stores) == 2 + int(state == 1)
        if 0x8000E2DC <= self.site <= 0x8000E7E0:
            selection_r1 = 9 if self.site == 0x8000E7E0 else r1
            assert bytes(u.mem_read(SELECTION, 2)) == bytes((selection_r1, r2))
        return dict(site=hex(self.site), start=hex(self.start), return_pc=hex(stop),
                    fixture_state=state, producer_r0_r1_r2=[hex(v) for v in (kind, r1, r2)],
                    record_prefix=expected.hex(), send_wait=wait, copied_bytes=RECORD_SIZE,
                    local_stores=self.caller_stores[:], constructor_handle_store=initial_handle_write)


    def run_result_clear(self, raw, state, clears):
        # Carry the original PC-relative r5 load into the bounded writer.
        u = self.u
        self.site = 0
        self.result_stores.clear()
        previous_queue = bytes(u.mem_read(QUEUE, 760))
        previous_handle = self.read(CTRL + 4)
        u.mem_write(RESULT + 0x20, b"\xA5" * 0x24)
        self.put(RESULT + 0x24, state)
        literal_pc = 0x8005D518
        literal = raw[literal_pc - BASE:literal_pc - BASE + 4]
        assert struct.unpack("<I", literal) == (RESULT,)
        try:
            for self.probe_start, self.probe_stop in ((0x8005D27C, 0x8005D280), (0x8005D34C, 0x8005D374)):
                u.reg_write(UC_ARM_REG_CPSR, 0x13)
                u.emu_start(self.probe_start, 0, count=20)
                assert u.reg_read(UC_ARM_REG_PC) == self.probe_stop
                assert u.reg_read(UC_ARM_REG_R5) == RESULT
        finally:
            self.probe_start = self.probe_stop = 0
        offsets = (0x38, 0x3C, 0x30, 0x34, 0x2C, 0x28)
        expected_stores = [[hex(0x8005D35C + 4 * i), hex(RESULT + offset)]
                           for i, offset in enumerate(offsets)] if clears else []
        assert self.result_stores == expected_stores
        assert all(self.read(RESULT + offset) == (0 if clears else 0xA5A5A5A5) for offset in offsets)
        assert self.read(RESULT + 0x24) == state
        assert self.read(RESULT + 0x20) == self.read(RESULT + 0x40) == 0xA5A5A5A5
        assert bytes(u.mem_read(QUEUE, 760)) == previous_queue and self.read(CTRL + 4) == previous_handle
        return dict(result_base=hex(RESULT), input_word=hex(state), literal_address=hex(literal_pc), literal_bytes=literal.hex(),
                    stores=self.result_stores[:], control_queue_unchanged=True)


def scenarios(row):
    site = int(row["address"], 16)
    if site == 0x8005D130:
        return [(3, 0x21), (4, 0x22)]
    kind, = row["local_r0_values"]
    return [(kind, state) for state in ((0, 1) if site == 0x8000D39C else (0,))]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    index_path = root / "contributions/COORD-ADC-CADENCE/synchronous/control-producer-index.json"
    index_raw = index_path.read_bytes()
    index = json.loads(index_raw)
    sites = index["identical_observations"]["calls"]
    assert len(sites) == 31
    versions, observations = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert len(raw) == item["size_bytes"] and digest == item["sha256"]
        replay = CallerReplay(raw)
        cases = [replay.run(row, *scenario) for row in sites for scenario in scenarios(row)]
        kinds = dict(sorted(Counter(int(case["producer_r0_r1_r2"][0], 16) for case in cases).items()))
        assert kinds == {0: 1, 1: 9, 2: 18, 3: 2, 4: 1, 5: 2}
        versions.append(dict(version=item["version"], input_sha256=digest, cases=len(cases)))
        clears = [replay.run_result_clear(raw, state, enabled) for state, enabled in
                  ((0, True), (0x3FFFFFFF, True), (0x40000000, False), (0x80000000, True))]
        versions[-1]["result_clear_cases"] = len(clears)
        observations.append(dict(cases=cases, cases_by_kind=kinds, result_clear_cases=clears,
                                 instruction_bytes={hex(pc): word for pc, word in sorted(replay.coverage.items())}))
    assert len(versions) == 2 and observations[0] == observations[1]
    report = dict(
        schema="ys4470.direct-control-producer-replay.v1", versions=versions,
        producer_index_sha256=hashlib.sha256(index_raw).hexdigest(), **observations[0],
        limits=[
            "Runs start at the local argument and type setup for each indexed BL. Earlier control flow and whole-caller reachability are outside scope.",
            "The original constructor runs with a modeled allocator. Each send starts with an empty queue, an idle scheduler fixture, and supplied incoming registers and local bytes.",
            "The test checks the complete original copy and interprets only the six-byte prefix. No hardware, wait duration or scheduler handoff is measured.",
            "The result-writer probe joins the original r5 literal load and store suffix. Intermediate GUI calls and task reachability are outside scope.",
            "Indirect, synthesized, alternate writers and native type-6 provenance remain unresolved.",
        ],
    )
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {len(sites)} direct sites, {sum(v['cases'] for v in versions)} original ARM926 sends, "
          f"{sum(v['result_clear_cases'] for v in versions)} original result-writer cases")


if __name__ == "__main__":
    main()
