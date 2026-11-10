"""Execute original long fallback producers with real queue, SVC and IRQ waits."""

import argparse
import hashlib
import json
from pathlib import Path

from trace_gauge_scheduled_service import (
    CTRL, FLAG, FSM, OTHER, PHASE, QUEUE, RX, RX_COUNT, SCHED, STORED, TIMER_SLOT,
    GaugeReplay, PeripheralReplay,
)
from trace_scheduler_irq_context import IRQ_ENTRY, OTHER_PC, SELECT, TICK
from trace_timer0_uart2_irq import NEST, RESULT
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0

PRODUCERS = {
    0: (0x8000E61C, 0x8000E638, "000000000913", (9, 0x13)),
    0x28: (0x8000E4F4, 0x8000E510, "010000002800", (0x28, 0)),
    0x29: (0x8000E588, 0x8000E5A4, "010000002900", (0x29, 0)),
}
SELECTION = 0x805AC08C
GPIO = 0x01C208C4
DELAY = 0x80060FBC
STATUS_CHECK = 0x80003F68
REPLY_RETURN_SITES = (0x80005D04, 0x80003EC8, 0x80003F14, 0x80003FEC)
TYPE0_FRAME = bytes.fromhex("c000c0")
PREPARE_FRAME = bytes.fromhex("c05515")


class LongGaugeReplay(GaugeReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.native_stop = None
        self.waits = []
        self.completed_waits = []
        self.replies = []

    def code(self, u, pc, size, data):
        if self.native_stop is not None:
            if pc == self.native_stop:
                u.emu_stop()
                return
            if self.native_start <= pc < self.native_stop:
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
                return
        if self.executing_gauge:
            if pc == DELAY:
                delay = u.reg_read(UC_ARM_REG_R0)
                assert delay in (1, 200, 500, 600, 1000, 2000, 10000)
                self.waits.append(dict(start=self.read(SCHED + 0xC), delay=delay,
                                       return_site=hex(u.reg_read(UC_ARM_REG_LR))))
                # Reuse the scheduler's original execution window with long waits.
                PeripheralReplay.code(self, u, pc, size, data)
                return
            if pc == STATUS_CHECK:
                self.trace.append(["status_poll", self.read(SCHED + 0xC), self.read(RX_COUNT),
                                   bytes(u.mem_read(RX, 2)).hex()])
            if pc in REPLY_RETURN_SITES and (pc != 0x80005D04 or self.variant == 0):
                self.replies.append([hex(pc), self.read(SCHED + 0xC), u.reg_read(UC_ARM_REG_R0)])
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.executing_gauge:
            pc = u.reg_read(UC_ARM_REG_PC)
            if address == RX_COUNT and pc in (0x80003F24, 0x80003F44):
                assert size == 4 and value == 0 and self.read(NEST) > 0
                assert u.reg_read(UC_ARM_REG_CPSR) & 0x80
                self.trace.append(["critical_clear", hex(pc), self.read(RX_COUNT)])
            elif address in (PHASE, FLAG, GPIO):
                assert size == 4
                self.trace.append(["control_store", hex(pc), hex(address), value])
        super().write(u, access, address, size, value, data)

    def enqueue(self, kind, arg):
        assert kind == 1 and arg == self.variant
        self.native_start, self.native_stop, record, selection = PRODUCERS[self.variant]
        self.transport_active = True
        try:
            self.invoke(self.native_start, stop=self.native_stop)
        finally:
            self.transport_active = False
            self.native_stop = None
        assert bytes(self.u.mem_read(SELECTION, 2)) == bytes(selection)
        assert [e for e in self.trace if e[0] == "queue_send"] == [["queue_send", record]]

    def advance(self, delay):
        wait = self.waits[-1]
        start = self.read(SCHED + 0xC)
        assert (wait["start"], wait["delay"]) == (start, delay)
        deadline = start + delay
        for index in range(1, delay + 1):
            events = self.enter(0x1F, OTHER_PC, 1 << 13, TIMER_SLOT)
            assert self.u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER
            assert self.read(SCHED + 0xC) == start + index
            assert ["pc", hex(IRQ_ENTRY)] in events and ["pc", hex(TICK)] in events
            assert events.count(["pc", hex(SELECT)]) == (2 if index == delay else 0)
        assert len(self.waits) == len(self.completed_waits) + 2
        self.completed_waits.append({**wait, "irq_ticks": delay, "woke_at": deadline})

    def run_long(self, variant):
        self.variant = variant
        self.prepare_tasks(False, variant)
        self.put(PHASE, 0x99)
        self.put(FLAG, 0x99)
        self.put(GPIO, 0x80)
        self.waits, self.completed_waits, self.replies = [], [], []
        self.transport_active = self.executing_gauge = self.dispatch_svc = True
        try:
            self.enter_gauge()
            assert self.read(QUEUE + 0x38) == 0 and not self.sent()
            if variant == 0:
                self.advance(200)
                assert self.sent() == TYPE0_FRAME
                self.deliver(0xC0)
                self.advance(1)
                expected_wire = TYPE0_FRAME
                expected_helpers = [0x26]
                returns = ["0x80005d04"]
                result = 0
            else:
                self.advance(600)
                assert self.sent() == PREPARE_FRAME
                self.deliver(0xC0)
                self.advance(1)
                self.advance(500)
                self.advance(500)
                header = 0xC1 if variant == 0x28 else 0xC2
                expected_wire = PREPARE_FRAME + bytes((header, header))
                assert self.sent() == expected_wire
                # ACK plus premature status. First clear must remove all three bytes.
                for byte in (header, 0xA0, 3):
                    self.deliver(byte)
                self.advance(1)
                assert self.read(RX_COUNT) == 0 and not any(self.u.mem_read(RX, 200))
                for byte in (0xA1, 1):
                    self.deliver(byte)
                self.advance(10000)
                assert self.read(RX_COUNT) == 0 and not any(self.u.mem_read(RX, 200))
                assert self.read(PHASE) == 0
                packet = bytes((0xA0, 2) if variant == 0x28 else (0xA1, 4))
                for byte in packet:
                    self.deliver(byte)
                self.advance(1000)
                result = 2 if variant == 0x28 else 7
                assert self.read(PHASE) == result
                expected_wire += TYPE0_FRAME
                assert self.sent() == expected_wire
                self.deliver(0xC0)
                self.advance(1)
                self.advance(2000)
                self.advance(500)
                expected_helpers = [0x27, variant, 0x26]
                returns = ["0x80003ec8", "0x80003f14", "0x80003fec"]
                assert [e for e in self.trace if e[0] == "critical_clear"] == [
                    ["critical_clear", "0x80003f24", 3], ["critical_clear", "0x80003f44", 2],
                ]
                assert [e[2:] for e in self.trace if e[0] == "status_poll"] == [[2, packet.hex()]]
                assert [e[-1] for e in self.trace if e[0] == "control_store" and e[2] == hex(GPIO)][-4:] == [
                    0x80, 0x84, 0x84, 0x80,
                ]
        finally:
            self.transport_active = self.executing_gauge = self.dispatch_svc = False
        assert self.sent() == expected_wire
        assert self.waits[-1] == dict(start=self.read(SCHED + 0xC), delay=1, return_site="0x80003dd4")
        assert self.read(PHASE) == result and self.read(FLAG) == 0 and self.read(GPIO) == 0x80
        assert self.u.mem_read(CTRL, 1)[0] == self.u.mem_read(FSM + 0x34, 1)[0] == 0
        assert (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == STORED
        assert [e[2] for e in self.trace if e[0] == "helper"] == expected_helpers
        assert [e[2] for e in self.trace if e[0] == "fallback"] == [PRODUCERS[variant][2]]
        assert [(site, value) for site, _, value in self.replies] == [(site, 1) for site in returns]
        assert self.loop_count == 1 and self.back_edges == 0
        assert self.svc_count == len(self.completed_waits) + 1 and self.select_count == 2 * self.svc_count - 1
        return dict(variant="type-0" if variant == 0 else hex(variant), producer=hex(PRODUCERS[variant][0]),
                    wire_hex=self.sent().hex(), completed_waits=self.completed_waits,
                    pending_service_wait=self.waits[-1], helper_returns=self.replies, phase=result,
                    injected_ticks=self.read(SCHED + 0xC) - 100, trace=self.trace)


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
        replay = LongGaugeReplay(raw)
        replay.install_vectors(False)
        cases = [replay.run_long(variant) for variant in (0, 0x28, 0x29)]
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        results.append((cases, coverage))
        versions.append(dict(version=image["version"], input_sha256=image["sha256"], cases=len(cases)))
    assert len(results) == 2 and results[0] == results[1]
    report = dict(schema="ys4470.gauge-long-fallback-scheduled.v1", versions=versions,
                  cases=results[0][0], instruction_bytes=results[0][1],
                  limits=["Original producer suffixes begin after earlier queue drains. Queue allocation is a fixture.",
                          "Original task loop, queue, fallback, delay, SVC/IRQ and UART code execute.",
                          "Timer IRQs and UART bytes are injected individually. No elapsed physical time or external peer is modeled.",
                          "Extended cases cover the first status poll after the second clear. No exhaustive late status or hardware interrupt claim."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
