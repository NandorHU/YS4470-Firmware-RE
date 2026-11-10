"""Run the original GaugeCmdTask service loop through queue, SVC and IRQ."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_scheduler_delay_wake import SCHED, TASK, OTHER, READY_PRIO_0, READY_PRIO_1
from trace_scheduler_irq_context import (
    CANARY, FOREGROUND_SP, OTHER_SP, OTHER_PC, IRQ_ENTRY, REGS, SELECT, SVC_ENTRY,
)
from trace_timer0_uart2_irq import (
    CTRL, FSM, RESULT, RX, RX_COUNT, STORED, TIMER_SLOT, TX_READY, UART, UART_SLOT,
    UART_ISR, PeripheralReplay,
)
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2,
)

GAUGE_LOOP = 0x80003DD0
SERVICE = 0x80005B6C
FALLBACK = 0x80003DD8
HELPER = 0x80005F14
PRODUCER = 0x80006778
ALLOCATE = 0x80042AA0
QUEUE = 0x1001F000
DEFERRED = 0x805AC6D0
RECORD_SIZE = 68
NATIVE_PRODUCER = 0x8000E7C4
NATIVE_STOP = 0x8000E7E4
SELECTION = 0x805AC08C
FRAMES = {0x27: bytes.fromhex('c05515'), 0x2A: bytes.fromhex('c3c3'), 0x2B: bytes.fromhex('c4c4')}
PHASE = 0x805AB920
FLAG = 0x805AB91C
SERVICE_WINDOWS = (
    (0x800029DC, 0x800029FC), (GAUGE_LOOP, 0x80004050), (0x80004390, 0x80004490),
    (SERVICE, 0x80005D18), (HELPER, 0x80006090), (PRODUCER, 0x800067C4),
    (0x80061838, 0x80061CD4), (NATIVE_PRODUCER, NATIVE_STOP),
)


class GaugeReplay(PeripheralReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.executing_gauge = False
        self.trace = []

    def code(self, u, pc, size, data):
        if pc == NATIVE_STOP:
            u.emu_stop()
            return
        if pc == ALLOCATE:
            assert u.reg_read(UC_ARM_REG_R0) == 760 and u.reg_read(UC_ARM_REG_LR) == 0x80061858
            self.trace.append(["queue_alloc", 760])
            u.reg_write(UC_ARM_REG_R0, QUEUE)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if self.executing_gauge:
            if pc == GAUGE_LOOP:
                self.loop_count += 1
            elif pc == 0x80003DD4:
                self.back_edges += 1
            elif pc == FALLBACK:
                assert u.mem_read(FSM + 0x34, 1)[0] == u.mem_read(CTRL, 1)[0] == 0
                record = bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), RECORD_SIZE))
                assert record == bytes(u.mem_read(DEFERRED, RECORD_SIZE))
                self.trace.append(["fallback", self.read(SCHED + 0xC), record[:6].hex()])
            elif pc == HELPER:
                assert u.mem_read(FSM + 0x34, 1)[0] == 0
                self.trace.append(["helper", self.read(SCHED + 0xC), u.reg_read(UC_ARM_REG_R0)])
            elif pc == 0x80003EB0:
                self.trace.append(["helper_return", self.read(SCHED + 0xC), u.reg_read(UC_ARM_REG_R0)])
            elif pc == 0x80060FBC:
                assert u.reg_read(UC_ARM_REG_R0) == 1
                return_site = hex(u.reg_read(UC_ARM_REG_LR))
                self.wait_sites[return_site] = self.wait_sites.get(return_site, 0) + 1
            elif pc == SVC_ENTRY:
                self.svc_count += 1
            elif pc == SELECT:
                self.select_count += 1
        if any(start <= pc < end for start, end in SERVICE_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            if pc == 0x80061ACC:
                assert u.reg_read(UC_ARM_REG_R0) == QUEUE
                pointer = u.reg_read(UC_ARM_REG_R1)
                self.trace.append(["queue_send", bytes(u.mem_read(pointer, 6)).hex()])
            elif pc == 0x800618DC and self.read(QUEUE + 0x38):
                assert u.reg_read(UC_ARM_REG_R0) == QUEUE
                self.trace.append(["queue_receive", self.read(SCHED + 0xC), self.read(QUEUE + 0x38)])
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if QUEUE <= address and address + size <= QUEUE + 760:
            return
        if FOREGROUND_SP - 0x400 <= address and address + size <= FOREGROUND_SP:
            return
        if (
            address in (CTRL, CTRL + 4, PHASE, FLAG, SELECTION, SELECTION + 1)
            or DEFERRED <= address and address + size <= DEFERRED + RECORD_SIZE
        ):
            assert size in (1, 4)
            if address == CTRL and self.executing_gauge:
                self.trace.append(["pending_record", self.read(SCHED + 0xC), value])
            return
        pc = u.reg_read(UC_ARM_REG_PC)
        if pc == 0x8000740C:
            assert size == 1 and RX <= address < RX + 200
            self.trace.append(["irq_rx", self.read(SCHED + 0xC), value])
        super().write(u, access, address, size, value, data)

    def prepare_tasks(self, mixed, command):
        u = self.u
        self.seed("idle")
        self.configure()
        u.mem_write(QUEUE, bytes(760))
        u.mem_write(FSM, bytes(0x3C))
        u.mem_write(CTRL, bytes(0x10))
        self.put(CTRL + 8, 0x22)
        self.put(RESULT + 0x1C, STORED[0])
        self.put(RESULT + 0x20, STORED[1])
        self.put(RX_COUNT, 0)
        self.put(PHASE, 0)
        self.put(FLAG, 0)
        self.put(TX_READY, 2)
        self.trace = []
        self.transport_events = []
        self.invoke_transport(0x800029DC)
        assert self.read(CTRL + 4) == QUEUE
        assert (self.read(QUEUE + 0x3C), self.read(QUEUE + 0x40)) == (10, RECORD_SIZE)
        if command == 0x27:
            self.transport_active = True
            try:
                self.invoke(NATIVE_PRODUCER, stop=NATIVE_STOP)
            finally:
                self.transport_active = False
            assert bytes(u.mem_read(SELECTION, 2)) == bytes((9, 0x13))
        else:
            for kind, arg in ([(3, 0)] if mixed else []) + [(1, command)]:
                self.enqueue(kind, arg)
        assert self.read(QUEUE + 0x38) == (2 if mixed else 1)

        self.invoke(0x80060DE0, TASK + 4)
        self.put(TASK + 0x2C, 1)
        self.invoke(0x80060ECC, READY_PRIO_1, TASK + 4)
        self.invoke(0x80060ECC, READY_PRIO_0, OTHER + 4)
        self.put(READY_PRIO_1 + 4, TASK + 4)
        self.put(SCHED + 0x10, 1)
        self.put(OTHER + 0x30, CANARY)
        other = [0x22220000 + i for i in range(13)] + [OTHER_SP, 0x44332211]
        other_frame = OTHER_SP - 72
        u.mem_write(other_frame, struct.pack("<18I", 0, 0x1F, *other, OTHER_PC + 4))
        self.put(OTHER, other_frame)
        u.reg_write(UC_ARM_REG_CPSR, 0x1F)
        gauge = [0x11110000 + i for i in range(13)] + [FOREGROUND_SP, 0x11223344]
        for reg, value in zip(REGS, gauge):
            u.reg_write(reg, value)
        self.loop_count = self.back_edges = self.svc_count = self.select_count = 0
        self.wait_sites = {}

    def enqueue(self, kind, arg):
        self.u.reg_write(UC_ARM_REG_R2, 0x19)
        self.invoke_transport(PRODUCER, kind, arg)
        assert self.u.reg_read(UC_ARM_REG_R0) == 1

    def enter_gauge(self):
        self.events = []
        self.u.emu_start(GAUGE_LOOP, 0, count=50000)
        assert self.u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER

    def tick(self):
        count = self.read(SCHED + 0xC)
        events = self.enter(0x1F, OTHER_PC, 1 << 13, TIMER_SLOT)
        assert self.u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER
        assert self.read(SCHED + 0xC) == count + 1
        assert ["pc", hex(IRQ_ENTRY)] in events and ["pc", hex(SELECT)] in events

    def deliver(self, byte):
        old = self.read(SCHED + 0xC)
        self.put(UART + 8, 4)
        self.put(UART, byte)
        events = self.enter(0x1F, OTHER_PC, 1 << 3, UART_SLOT)
        assert self.u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER
        assert self.read(SCHED + 0xC) == old and ["pc", hex(UART_ISR)] in events

    def sent(self):
        return bytes(e[1] for e in self.transport_events if e[0] == "tx")

    def run_case(self, command, reply):
        mixed = reply in ("measurement-first", "replace-during-measurement")
        replacement = reply == "replace-during-measurement"
        effective = command ^ int(replacement)
        self.prepare_tasks(mixed, command)
        expected = FRAMES[effective]
        self.transport_active = self.executing_gauge = self.dispatch_svc = True
        try:
            self.enter_gauge()
            assert self.read(QUEUE + 0x38) == 0
            if mixed:
                assert self.sent() == b"\x60\x60"
                assert self.u.mem_read(CTRL, 1)[0] == self.u.mem_read(FSM + 0x34, 1)[0] == 1
                assert not any(e[0] == "fallback" for e in self.trace)
                if replacement:
                    assert self.u.mem_read(DEFERRED + 4, 1)[0] == command
                    context = self.u.context_save()
                    try:
                        self.enqueue(1, effective)
                    finally:
                        self.u.context_restore(context)
                        self.transport_active = True
                    assert self.read(QUEUE + 0x38) == 1
                    self.tick()
                    assert self.read(QUEUE + 0x38) == 0
                    assert self.u.mem_read(DEFERRED + 4, 1)[0] == effective
                    assert self.u.mem_read(CTRL, 1)[0] == self.u.mem_read(FSM + 0x34, 1)[0] == 1
                    assert not any(e[0] == "fallback" for e in self.trace)
                for byte in b"\x60\x45\x23\x01\x03":
                    self.deliver(byte)
                for _ in range(8):
                    self.tick()
                    if any(e[0] == "helper" for e in self.trace):
                        break
                assert (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == (0x012345, 3)
                assert self.sent() == b"\x60\x60" + expected
            else:
                assert self.sent() == expected
            assert self.u.mem_read(FSM + 0x34, 1)[0] == 0
            assert self.wait_sites.get("0x80005fec") == 1
            if reply == "wrong-then-match":
                self.deliver(expected[0] ^ 1)
                self.tick()
                assert self.wait_sites.get("0x80005fec") == 2 and self.sent() == expected
                # The helper compares the first RX slot. Leave the wrong byte in place
                # until the original retry clears the receive state.
            if reply in ("wrong-then-match", "retry-match", "no-reply"):
                for _ in range(501):
                    if self.sent() == expected * 2:
                        break
                    self.tick()
                assert self.sent() == expected * 2
                assert self.read(RX_COUNT) == 0 and self.wait_sites.get("0x80005fec") == 500
            if reply == "no-reply":
                for _ in range(500):
                    self.tick()
                assert self.wait_sites.get("0x80006064") == 500 and self.sent() == expected * 2
            else:
                self.deliver(expected[0])
                self.tick()
        finally:
            self.transport_active = self.executing_gauge = self.dispatch_svc = False

        returns = [e for e in self.trace if e[0] == "helper_return"]
        fallbacks = [e for e in self.trace if e[0] == "fallback"]
        helpers = [e for e in self.trace if e[0] == "helper"]
        assert len(fallbacks) == len(helpers) == len(returns) == 1
        secondary = 0x13 if command == 0x27 else 0x19
        assert fallbacks[0][2] == struct.pack("<IBB", 1, effective, secondary).hex()
        assert returns[0][2] == int(reply != "no-reply") and helpers[0][2] == effective
        assert [e[2] for e in self.trace if e[0] == "pending_record"] == ([1, 1, 0] if replacement else [1, 0])
        assert self.u.mem_read(CTRL, 1)[0] == self.u.mem_read(FSM + 0x34, 1)[0] == 0
        assert self.back_edges == self.loop_count - 1 and self.svc_count > 0
        assert self.select_count == 2 * self.svc_count - 1
        return dict(initial_command=hex(command), executed_command=hex(effective), reply=reply,
                    native_producer=hex(NATIVE_PRODUCER) if command == 0x27 else None,
                    queue_records=1 + int(mixed) + int(replacement),
                    gauge_loops=self.loop_count, loop_back_edges=self.back_edges,
                    svc_entries=self.svc_count, selections=self.select_count, waits=self.wait_sites,
                    timer_irqs=self.read(SCHED + 0xC) - 100, wire=self.sent().hex(),
                    final_raw=self.read(RESULT + 0x1C), trace=self.trace,
                    transport_events=self.transport_events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    results, versions = [], []
    for image in manifest["images"]:
        raw = (root / image["path"]).read_bytes()
        assert len(raw) == image["size_bytes"] and hashlib.sha256(raw).hexdigest() == image["sha256"]
        replay = GaugeReplay(raw)
        replay.install_vectors(False)
        rows = [replay.run_case(*case) for case in product(
            (0x2A, 0x2B),
            ("match", "wrong-then-match", "retry-match", "no-reply", "measurement-first", "replace-during-measurement"),
        )]
        rows.append(replay.run_case(0x27, "match"))
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        results.append((rows, coverage))
        versions.append(dict(version=image["version"], input_sha256=image["sha256"], cases=len(rows)))
    assert len(results) == 2 and results[0] == results[1]
    report = dict(schema="ys4470.gauge-service-scheduled.v1", versions=versions,
                  cases=results[0][0], instruction_bytes=results[0][1],
                  limits=["Start at the original GaugeCmdTask loop after the already-tested startup commands.",
                          "The queue constructor, producer, service, helper, scheduler SVC and IRQ handlers execute.",
                          "Queue allocation, initial task state and all Timer0/UART2 exception inputs are controlled.",
                          "The interrupted idle task is a fixed stop point. No hardware timing or UART peer is modeled."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
