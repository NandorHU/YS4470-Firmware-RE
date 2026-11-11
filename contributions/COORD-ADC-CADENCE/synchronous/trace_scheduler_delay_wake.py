"""Run the original delay, list and yield-request paths on ARM926."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_INTR, UC_HOOK_MEM_WRITE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP,
    UC_CPU_ARM_926,
)

BASE = 0x7FFFFFE0
SCHED = 0x805ABBBC
PENDING = 0x805B5294
READY_PRIO_0 = 0x805B521C
READY_PRIO_1 = READY_PRIO_0 + 0x14
TICK = 0x80061FA4
TASK = 0x10018100
OTHER = 0x10018200
READY = 0x10018300
CURRENT = 0x10018400
OVERFLOW = 0x10018500
RET = 0x10000000
STACK = 0x10014000
DELAY = 0x80060FBC
SVC = 0x8000222C
MAX = 0xFFFFFFFF
WINDOWS = (
    (0x8000222C, 0x80002234), (0x80005530, 0x80005538), (0x80005D10, 0x80005D18),
    (0x80042840, 0x800428C4), (0x80060DE0, 0x80060E20), (0x80060E48, 0x80060E68),
    (0x80060E74, 0x80060EFC), (0x80060EFC, 0x80060F1C), (0x80060F20, 0x80060F58),
    (DELAY, 0x80060FF4), (TICK, 0x800620E4), (0x80062204, 0x8006231C),
)


class DelayReplay:
    invoke_instruction_limit = 10_000

    def __init__(self, raw):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        low, high = BASE & ~0xFFF, (BASE + len(raw) + 0xFFF) & ~0xFFF
        u.mem_map(low, high - low)
        u.mem_write(BASE, raw)
        for address, size in ((0x805AB000, 0x1000), (0x805B5000, 0x1000),
                              (RET, 0x1000), (0x10010000, 0x10000)):
            u.mem_map(address, size)
        self.coverage = {}
        self.events = []
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_INTR, self.interrupt)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def read(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def put(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value & MAX))

    def code(self, u, pc, size, _):
        if pc in (RET, 0x80005538):
            u.emu_stop()
            return
        assert size == 4 and any(a <= pc < b for a, b in WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
        if pc == DELAY:
            self.events.append(["delay", u.reg_read(UC_ARM_REG_R0)])
        if pc == 0x80060E74:
            self.events.append(["ordered_insert", hex(u.reg_read(UC_ARM_REG_R0))])
        if pc == SVC:
            self.events.append(["yield", hex(u.reg_read(UC_ARM_REG_LR)),
                                bool(u.reg_read(UC_ARM_REG_CPSR) & 0x80)])

    def interrupt(self, u, number, _):
        assert number == 2 and u.reg_read(UC_ARM_REG_PC) == SVC + 4
        self.events.append(["svc", number])

    def write(self, u, access, address, size, value, _):
        if address in (SCHED + 0x30, SCHED + 0x28, TASK + 4):
            assert size == 4
            self.events.append(["store", hex(address), value])
        assert (
            0x10013F00 <= address < STACK or TASK <= address < OVERFLOW + 0x20
            or SCHED <= address < SCHED + 0x40 or PENDING <= address < PENDING + 0x14
            or READY_PRIO_0 <= address < READY_PRIO_1 + 0x14
        ), (hex(u.reg_read(UC_ARM_REG_PC)), hex(address))

    def invoke(self, entry, *args, stop=RET):
        u = self.u
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1), args):
            u.reg_write(reg, value)
        u.reg_write(UC_ARM_REG_CPSR, 0x13)
        u.reg_write(UC_ARM_REG_SP, STACK)
        u.reg_write(UC_ARM_REG_LR, RET)
        u.emu_start(entry, 0, count=self.invoke_instruction_limit)
        assert u.reg_read(UC_ARM_REG_PC) == stop
        assert u.reg_read(UC_ARM_REG_SP) == STACK and self.read(SCHED + 0x3C) == 0
        assert not u.reg_read(UC_ARM_REG_CPSR) & 0x80
        return u.reg_read(UC_ARM_REG_R0)

    def members(self, head):
        sentinel = head + 8
        count = self.read(head)
        nodes = []
        previous, node = sentinel, self.read(sentinel + 4)
        while node != sentinel:
            assert len(nodes) < count
            assert self.read(node + 8) == previous and self.read(node + 0x10) == head
            nodes.append([hex(node), self.read(node)])
            previous, node = node, self.read(node + 4)
        assert len(nodes) == count and self.read(sentinel + 8) == previous
        return nodes

    def run_wake(self, delay, clock, deferred):
        u = self.u
        u.mem_write(SCHED, bytes(0x40))
        u.mem_write(PENDING, bytes(0x14))
        u.mem_write(TASK, bytes(0x500))
        for head in (READY_PRIO_0, READY_PRIO_1, CURRENT, OVERFLOW, PENDING):
            self.invoke(0x80060E48, head)
        self.put(TASK + 0x10, TASK)
        self.put(TASK + 0x2C, 1)
        self.put(OTHER + 0x10, OTHER)
        self.invoke(0x80060ECC, READY_PRIO_1, TASK + 4)
        self.invoke(0x80060ECC, READY_PRIO_0, OTHER + 4)
        now = {"normal": 100, "max-deadline": MAX - delay, "overflow": MAX - delay + 1}[clock]
        for offset, value in ((0, TASK), (8, 1), (0xC, now), (0x28, MAX),
                              (0x34, CURRENT), (0x38, OVERFLOW)):
            self.put(SCHED + offset, value)
        caller, stop = (0x80005D10, RET) if delay == 1 else (0x80005530, 0x80005538)
        self.events = []
        self.invoke(caller, 0, stop=stop)
        assert not self.members(READY_PRIO_1)
        deadline = (now + delay) & MAX
        assert self.members(OVERFLOW if deadline < now else CURRENT) == [[hex(TASK + 4), deadline]]

        # Stand in for the scheduler selecting the only other ready task at the SVC boundary.
        self.put(SCHED, OTHER)
        rows = []
        for step in range(1, delay + 1):
            if deferred:
                self.put(SCHED + 0x30, 1)
                previous_count = self.read(SCHED + 0xC)
                assert self.invoke(TICK) == 0
                assert self.read(SCHED + 0xC) == previous_count and self.read(SCHED + 0x18) == 1
                flag = self.invoke(0x80062204)
                assert self.read(SCHED + 0x18) == self.read(SCHED + 0x30) == 0
            else:
                flag = self.invoke(TICK)
            raw_count = (now + step) & MAX
            assert self.read(SCHED + 0xC) == raw_count
            wrap_count = self.read(SCHED + 0x20)
            assert wrap_count == int(raw_count < now)
            current, overflow = self.read(SCHED + 0x34), self.read(SCHED + 0x38)
            assert (current, overflow) == ((OVERFLOW, CURRENT) if wrap_count else (CURRENT, OVERFLOW))
            ready = self.members(READY_PRIO_1)
            assert self.members(READY_PRIO_0) == [[hex(OTHER + 4), 0]]
            if step < delay:
                assert flag == 0 and not ready
                assert self.members(OVERFLOW if deadline < now else CURRENT) == [[hex(TASK + 4), deadline]]
            else:
                assert flag == 1 and ready == [[hex(TASK + 4), deadline]]
                assert not self.members(CURRENT) and not self.members(OVERFLOW)
                assert self.read(SCHED + 0x28) == MAX
            if step in (1, delay - 1, delay):
                rows.append(dict(tick_call=step, raw_count=raw_count, wrap_count=wrap_count,
                                 current_list=hex(current), yield_requested=bool(flag), ready=ready))
        assert sum(event[0] == "svc" for event in self.events) == (2 if deferred else 1)
        return dict(delay=delay, clock=clock, deferred_ticks=deferred, start=now, deadline=deadline,
                    applied_ticks=delay, samples=rows)

    def run(self, delay, clock, yield_pending):
        u = self.u
        u.mem_write(SCHED, bytes(0x40))
        u.mem_write(PENDING, bytes(0x14))
        u.mem_write(TASK, bytes(0x500))
        for head in (READY, CURRENT, OVERFLOW, PENDING):
            self.invoke(0x80060E48, head)
        self.invoke(0x80060ECC, READY, TASK + 4)
        now = {"normal": 100, "max-deadline": MAX - delay, "overflow": MAX - delay + 1}[clock]
        other_deadline = min(now + 5, MAX)
        self.put(OTHER + 4, other_deadline)
        self.invoke(0x80060E74, CURRENT, OTHER + 4)
        for offset, value in ((0, TASK), (8, 1), (0xC, now), (0x1C, int(yield_pending)),
                              (0x28, other_deadline), (0x34, CURRENT), (0x38, OVERFLOW)):
            self.put(SCHED + offset, value)
        self.events = []
        caller, stop = {0: (DELAY, RET), 1: (0x80005D10, RET), 50: (0x80005530, 0x80005538)}[delay]
        self.invoke(caller, 0, stop=stop)
        yields = [e for e in self.events if e[0] == "yield"]
        assert len(yields) == 1 and sum(e[0] == "svc" for e in self.events) == 1
        assert [e for e in self.events if e[0] == "delay"] == [["delay", delay]]
        assert self.read(SCHED + 0x30) == 0
        deadline = (now + delay) & MAX
        wrapped = deadline < now
        inserts = [e for e in self.events if e[0] == "ordered_insert"]
        stores = [e for e in self.events if e[:2] == ["store", hex(SCHED + 0x30)]]
        if delay == 0:
            assert not inserts and not stores
            assert self.members(READY) == [[hex(TASK + 4), 0]]
            assert self.members(CURRENT) == [[hex(OTHER + 4), other_deadline]]
            assert not self.members(OVERFLOW)
        else:
            assert not self.members(READY)
            assert self.read(TASK + 4) == deadline
            assert inserts == [["ordered_insert", hex(OVERFLOW if wrapped else CURRENT)]]
            assert stores == [["store", hex(SCHED + 0x30), 1], ["store", hex(SCHED + 0x30), 0]]
            expected = [[hex(OTHER + 4), other_deadline]]
            if not wrapped:
                expected.append([hex(TASK + 4), deadline])
                expected.sort(key=lambda row: row[1])
            assert self.members(CURRENT) == expected
            assert self.members(OVERFLOW) == ([[hex(TASK + 4), deadline]] if wrapped else [])
        inside = bool(delay and yield_pending)
        outer_lr = RET if delay != 50 else 0x80005538
        assert yields == [["yield", hex(0x80062310 if inside else outer_lr), inside]]
        expected_head = min(other_deadline, deadline) if delay and not wrapped else other_deadline
        assert self.read(SCHED + 0x28) == expected_head
        return dict(delay=delay, caller=hex(caller), clock=clock, counter=now, yield_pending=yield_pending,
                    deadline=deadline if delay else None, next_current_deadline=expected_head,
                    ready=self.members(READY), current=self.members(CURRENT), overflow=self.members(OVERFLOW),
                    events=self.events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    cases = [(0, "normal", True), *product((1, 50), ("normal", "max-deadline", "overflow"), (False, True))]
    results, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert len(raw) == item["size_bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        static_tick_dispatch = {
            hex(pc): raw[pc - BASE:pc - BASE + 4].hex()
            for pc in (0x8000232C, 0x80002334, 0x800023A8)
        }
        assert static_tick_dispatch == {
            "0x8000232c": "74009fe5", "0x80002334": "10ff2fe1", "0x800023a8": "a41f0680",
        }
        runner = DelayReplay(raw)
        rows = [runner.run(*case) for case in cases]
        wake = [
            runner.run_wake(*case)
            for case in product((1, 50), ("normal", "max-deadline", "overflow"), (False, True))
        ]
        coverage = {hex(pc): value for pc, value in sorted(runner.coverage.items())}
        results.append((rows, wake, coverage, static_tick_dispatch))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"],
                             delay_cases=len(rows), wake_cases=len(wake)))
    assert len(results) == 2 and results[0] == results[1]
    report = dict(schema="ys4470.scheduler-delay-paths.v1", versions=versions, delay_helper=hex(DELAY),
                  tick_helper=hex(TICK), cases=results[0][0], wake_cases=results[0][1],
                  instruction_bytes=results[0][2], static_tick_dispatch_bytes=results[0][3],
                  limits=["Original delay/list routines, scheduler unlock and SVC instruction execute.",
                          "Minimal task and list fixtures. Wake tests inject ticks directly or through suspend/unlock, and seed the other task as current after the trapped yield.",
                          "The pending ready list is empty. The SVC trap is intercepted without running the exception handler, and no hardware IRQ is delivered.",
                          "List counter/deadline values do not establish physical duration."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
