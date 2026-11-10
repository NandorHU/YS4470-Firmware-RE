"""Replay the original IRQ tick vector, scheduler selection and exception return."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_scheduler_delay_wake import (
    BASE, CURRENT, MAX, OTHER, OVERFLOW, PENDING, READY_PRIO_0, READY_PRIO_1, SCHED,
    STACK, SVC, TASK, TICK, DelayReplay,
)
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_SPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
    UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12,
)

VECTOR_TEMPLATE = 0x800023B0
IRQ_VECTOR = 0x18
IRQ_ENTRY = 0x800022C0
SVC_VECTOR = 0x08
SVC_ENTRY = 0x80002234
KEY_RETURN = 0x80005538
SVC_SP = STACK - 0x80
SELECT = 0x800612F8
INTC_PENDING = 0x01C20410
TIMER_STATUS = 0x01C20C04
FOREGROUND_PC = 0x10000000
OTHER_PC = 0x10000010
FOREGROUND_SP = 0x10013C00
OTHER_SP = 0x10013E00
CANARY = 0x10018A00
REGS = (
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4,
    UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8, UC_ARM_REG_R9,
    UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_R12, UC_ARM_REG_SP, UC_ARM_REG_LR,
)
IRQ_WINDOWS = (
    (IRQ_ENTRY, 0x80002394), (IRQ_VECTOR, IRQ_VECTOR + 4),
    (0x80002404, 0x80002408), (SELECT, 0x800613C0),
    (SVC_ENTRY, IRQ_ENTRY), (SVC_VECTOR, SVC_VECTOR + 4), (0x800023F4, 0x800023F8),
    (0x80000030, 0x80000064),
)


class IrqReplay(DelayReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.u.mem_map(0, 0x1000)
        self.u.mem_map(0x01C20000, 0x1000)
        self.dispatch_svc = False

    def code(self, u, pc, size, data):
        if pc in (FOREGROUND_PC, OTHER_PC, KEY_RETURN):
            u.emu_stop()
            return
        if any(a <= pc < b for a, b in IRQ_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            if pc in (IRQ_ENTRY, SVC_ENTRY, SELECT, 0x800022BC, 0x80002390):
                self.events.append(["pc", hex(pc)])
            return
        if pc == TICK:
            self.events.append(["pc", hex(pc)])
        super().code(u, pc, size, data)

    def interrupt(self, u, number, data):
        if not self.dispatch_svc:
            return super().interrupt(u, number, data)
        assert number == 2 and u.reg_read(UC_ARM_REG_PC) == SVC + 4
        old_cpsr = u.reg_read(UC_ARM_REG_CPSR)
        assert old_cpsr & 0x3F == 0x1F
        u.reg_write(UC_ARM_REG_CPSR, 0x93)
        u.reg_write(UC_ARM_REG_SPSR, old_cpsr)
        u.reg_write(UC_ARM_REG_SP, SVC_SP)
        u.reg_write(UC_ARM_REG_LR, SVC + 4)
        u.reg_write(UC_ARM_REG_PC, SVC_VECTOR)

    def write(self, u, access, address, size, value, data):
        if 0 <= address < 0x40:
            assert size == 4 and address % 4 == 0
            return
        if address in (INTC_PENDING, TIMER_STATUS):
            assert size == 4
            self.events.append(["mmio_store", hex(address), value])
            return
        if 0x10013B00 <= address < 0x10013F00:
            assert address + size <= 0x10013F00
            return
        super().write(u, access, address, size, value, data)

    def install_vectors(self, high_before):
        u = self.u
        control = (15, 0, 1, 0, 0, 0, False)
        initial = (u.cpr_read(*control) & ~0x2000) | (0x2000 if high_before else 0)
        u.cpr_write(*control, initial)
        u.mem_write(0, bytes((0xA6,)) * 0x44)
        u.reg_write(UC_ARM_REG_CPSR, 0xD3)
        u.emu_start(0x80000030, 0x80000084, count=80)
        assert u.reg_read(UC_ARM_REG_PC) == 0x80000084
        final = u.cpr_read(*control)
        assert final == initial & ~0x2000
        installed = bytes(u.mem_read(0, 0x40))
        assert installed == bytes(u.mem_read(VECTOR_TEMPLATE, 0x40))
        assert bytes(u.mem_read(0x40, 4)) == bytes((0xA6,)) * 4
        return dict(high_vectors_before=high_before, control_before=hex(initial),
                    control_after=hex(final), vector_bytes=installed.hex())

    def seed(self, scenario):
        u = self.u
        u.mem_write(SCHED, bytes(0x40))
        u.mem_write(TASK, bytes(0x500))
        for head in (READY_PRIO_0, READY_PRIO_1, CURRENT, OVERFLOW, PENDING):
            self.invoke(0x80060E48, head)
        u.mem_write(CANARY, bytes((0xA5,)) * 16)
        self.put(TASK + 0x30, CANARY)
        self.put(TASK + 0x10, TASK)
        self.put(OTHER + 0x10, OTHER)
        self.invoke(0x80060ECC, READY_PRIO_0, TASK + 4)
        self.put(READY_PRIO_0 + 4, TASK + 4)
        counter = MAX if scenario == "wrap-wake" else 100
        next_due = MAX
        if scenario == "timeslice":
            self.invoke(0x80060ECC, READY_PRIO_0, OTHER + 4)
        if scenario in ("wake", "wrap-wake", "future"):
            self.put(OTHER + 0x2C, 1)
            next_due = {"wake": 101, "wrap-wake": 0, "future": 102}[scenario]
            self.put(OTHER + 4, next_due)
            self.invoke(0x80060E74, OVERFLOW if scenario == "wrap-wake" else CURRENT, OTHER + 4)
        for offset, value in (
            (0, TASK), (8, 1), (0xC, counter), (0x28, MAX if scenario == "wrap-wake" else next_due),
            (0x30, int(scenario == "suspended")), (0x34, CURRENT), (0x38, OVERFLOW),
        ):
            self.put(SCHED + offset, value)
        return counter, next_due

    def set_irq_entry(self, cpsr, return_pc):
        self.put(INTC_PENDING, 0x2000)
        self.put(TIMER_STATUS, 0x10)
        self.u.reg_write(UC_ARM_REG_CPSR, 0x92)
        self.u.reg_write(UC_ARM_REG_SPSR, cpsr)
        self.u.reg_write(UC_ARM_REG_SP, STACK)
        self.u.reg_write(UC_ARM_REG_LR, return_pc + 4)

    def run_round_trip(self, delay, wrap, other_thumb):
        u = self.u
        self.seed("idle")
        u.mem_write(CANARY, bytes((0xA5,)) * 16)
        self.put(OTHER + 0x30, CANARY)
        self.invoke(0x80060DE0, TASK + 4)
        self.put(TASK + 0x2C, 1)
        self.invoke(0x80060ECC, READY_PRIO_1, TASK + 4)
        self.invoke(0x80060ECC, READY_PRIO_0, OTHER + 4)
        self.put(READY_PRIO_1 + 4, TASK + 4)
        self.put(SCHED + 0x10, 1)
        start = MAX - delay + 1 if wrap else 100
        self.put(SCHED + 0xC, start)
        other_cpsr = 0x4000001F | (0x20 if other_thumb else 0)
        other = [0x22220000 + i for i in range(13)] + [OTHER_SP, 0x44332211]
        other_frame = OTHER_SP - 72
        u.mem_write(other_frame, struct.pack("<18I", 0, other_cpsr, *other, OTHER_PC + 4))
        self.put(OTHER, other_frame)
        caller = 0x80005D10 if delay == 1 else 0x80005530
        resumed_pc = FOREGROUND_PC if delay == 1 else KEY_RETURN
        foreground = [0x11110000 + i for i in range(13)] + [FOREGROUND_SP, FOREGROUND_PC]
        u.reg_write(UC_ARM_REG_CPSR, 0x1F)
        for reg, value in zip(REGS, foreground):
            u.reg_write(reg, value)
        self.events = []
        self.dispatch_svc = True
        try:
            u.emu_start(caller, 0, count=10000)
        finally:
            self.dispatch_svc = False
        assert u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER
        assert u.reg_read(UC_ARM_REG_CPSR) == other_cpsr
        assert [u.reg_read(reg) for reg in REGS] == other
        assert self.read(SCHED + 0xC) == start
        assert self.read(TASK) == FOREGROUND_SP - 72
        frame = list(struct.unpack("<18I", u.mem_read(self.read(TASK), 72)))
        assert frame[-1] == SVC + 8 and frame[-2] == resumed_pc
        assert [e for e in self.events if e[0] == "pc"] == [
            ["pc", hex(SVC_ENTRY)], ["pc", hex(SELECT)], ["pc", "0x800022bc"],
        ]
        svc_events = self.events
        deadline = (start + delay) & MAX
        assert not self.members(READY_PRIO_1)
        assert self.members(OVERFLOW if wrap else CURRENT) == [[hex(TASK + 4), deadline]]
        for n in range(1, delay + 1):
            self.events = []
            self.set_irq_entry(other_cpsr, OTHER_PC)
            u.emu_start(IRQ_VECTOR, 0, count=10000)
            assert self.read(SCHED + 0xC) == (start + n) & MAX
            assert self.read(INTC_PENDING) == 0 and self.read(TIMER_STATUS) == 1
            if n < delay:
                assert self.read(SCHED) == OTHER and u.reg_read(UC_ARM_REG_PC) == OTHER_PC
                assert u.reg_read(UC_ARM_REG_CPSR) == other_cpsr and not self.members(READY_PRIO_1)
        assert self.read(SCHED) == TASK and u.reg_read(UC_ARM_REG_PC) == resumed_pc
        assert [u.reg_read(reg) for reg in REGS] == frame[2:-1]
        assert u.reg_read(UC_ARM_REG_CPSR) == frame[1]
        assert self.members(READY_PRIO_1) == [[hex(TASK + 4), deadline]]
        assert not self.members(CURRENT) and not self.members(OVERFLOW)
        assert [e for e in self.events if e[0] == "pc"] == [
            ["pc", hex(IRQ_ENTRY)], ["pc", hex(TICK)], ["pc", hex(SELECT)], ["pc", "0x80002390"],
        ]
        return dict(delay=delay, wrap=wrap, other_task_thumb=other_thumb, caller=hex(caller),
                    start=start, deadline=deadline, irq_ticks=delay, resumed_pc=hex(resumed_pc),
                    svc_saved_frame=[hex(x) for x in frame], svc_events=svc_events,
                    final_irq_events=self.events)

    def run_irq(self, scenario, thumb):
        u = self.u
        counter, next_due = self.seed(scenario)
        old_cpsr = 0xA000001F | (0x20 if thumb else 0)
        other_cpsr = 0x4000001F | (0 if thumb else 0x20)
        foreground = [0x11110000 + i for i in range(13)] + [FOREGROUND_SP, 0x11223344]
        other = [0x22220000 + i for i in range(13)] + [OTHER_SP, 0x44332211]
        other_frame = OTHER_SP - 72
        u.mem_write(other_frame, struct.pack("<18I", 0, other_cpsr, *other, OTHER_PC + 4))
        self.put(OTHER, other_frame)
        self.events = []
        u.reg_write(UC_ARM_REG_CPSR, old_cpsr)
        for reg, value in zip(REGS, foreground):
            u.reg_write(reg, value)
        # Seed the processor state immediately after IRQ exception entry.
        self.set_irq_entry(old_cpsr, FOREGROUND_PC)
        u.emu_start(IRQ_VECTOR, 0, count=10000)
        switch = scenario in ("timeslice", "wake", "wrap-wake")
        assert u.reg_read(UC_ARM_REG_PC) == (OTHER_PC if switch else FOREGROUND_PC)
        assert u.reg_read(UC_ARM_REG_CPSR) == (other_cpsr if switch else old_cpsr)
        assert [u.reg_read(reg) for reg in REGS] == (other if switch else foreground)
        assert self.read(SCHED) == (OTHER if switch else TASK)
        frame = self.read(TASK)
        assert frame == FOREGROUND_SP - 72
        saved = list(struct.unpack("<18I", u.mem_read(frame, 72)))
        assert saved == [0, old_cpsr, *foreground, FOREGROUND_PC + 4]
        assert self.read(SCHED + 0xC) == (counter if scenario == "suspended" else (counter + 1) & MAX)
        assert self.read(SCHED + 0x18) == int(scenario == "suspended")
        assert self.read(SCHED + 0x20) == int(scenario == "wrap-wake")
        assert self.read(INTC_PENDING) == 0 and self.read(TIMER_STATUS) == 1
        trace = [["pc", hex(IRQ_ENTRY)], ["pc", hex(TICK)]]
        if scenario == "wrap-wake":
            trace.append(["store", hex(SCHED + 0x28), 0])
        if scenario in ("wake", "wrap-wake"):
            trace.append(["store", hex(SCHED + 0x28), MAX])
        if switch:
            trace.append(["pc", hex(SELECT)])
        trace.extend([["mmio_store", hex(INTC_PENDING), 0], ["mmio_store", hex(TIMER_STATUS), 1],
                      ["pc", "0x80002390"]])
        assert self.events == trace, (scenario, thumb, self.events, trace)
        if scenario in ("wake", "wrap-wake"):
            assert self.members(READY_PRIO_1) == [[hex(OTHER + 4), next_due]]
            assert not self.members(CURRENT) and not self.members(OVERFLOW)
        if scenario == "future":
            assert self.members(CURRENT) == [[hex(OTHER + 4), 102]]
            assert not self.members(READY_PRIO_1)
        cpsr, pc = u.reg_read(UC_ARM_REG_CPSR), u.reg_read(UC_ARM_REG_PC)
        u.reg_write(UC_ARM_REG_CPSR, 0x92)
        assert u.reg_read(UC_ARM_REG_SP) == STACK
        return dict(scenario=scenario, incoming_thumb=thumb, switched=switch,
                    tick_after=self.read(SCHED + 0xC), deferred_ticks=self.read(SCHED + 0x18),
                    current_task=hex(self.read(SCHED)), restored_cpsr=hex(cpsr), resumed_pc=hex(pc),
                    outgoing_frame=[hex(x) for x in saved], events=trace)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    results, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert len(raw) == item["size_bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        runner = IrqReplay(raw)
        vector_cases = [runner.install_vectors(high) for high in (False, True)]
        rows = [
            runner.run_irq(*case)
            for case in product(("idle", "future", "wake", "wrap-wake", "timeslice", "suspended"), (False, True))
        ]
        round_trips = [runner.run_round_trip(*case) for case in product((1, 50), (False, True), (False, True))]
        assert bytes(runner.u.mem_read(0, 0x40)).hex() == vector_cases[-1]["vector_bytes"]
        results.append((rows, round_trips, vector_cases,
                        {hex(pc): val for pc, val in sorted(runner.coverage.items())}))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"],
                             irq_cases=len(rows), round_trips=len(round_trips), vector_cases=len(vector_cases)))
    assert len(results) == 2 and results[0] == results[1]
    report = dict(schema="ys4470.irq-tick-context.v1", versions=versions, vector_template=hex(VECTOR_TEMPLATE), irq_vector=hex(IRQ_VECTOR), svc_vector=hex(SVC_VECTOR),
                  irq_entry=hex(IRQ_ENTRY), cases=results[0][0], round_trips=results[0][1],
                  vector_install=results[0][2], instruction_bytes=results[0][3],
                  limits=["The original boot slice installs low vectors. The host seeds IRQ-mode CPU state before entering the installed IRQ slot.",
                          "Original SVC/IRQ context save, tick, ready selection and exception return execute.",
                          "For SVC, the host seeds banked exception state after the original SVC instruction traps.",
                          "Controlled task frames, ready/delay lists and INTC/timer register shadows.",
                          "Hardware exception signal delivery, the rest of boot, silicon acknowledge behavior and physical timing are outside the replay."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
