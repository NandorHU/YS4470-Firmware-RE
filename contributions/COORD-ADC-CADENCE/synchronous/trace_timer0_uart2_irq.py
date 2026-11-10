"""Link original Timer0/UART2 registration to the installed IRQ routes."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_scheduler_delay_wake import SCHED, TASK, OTHER
from trace_scheduler_irq_context import (
    IrqReplay, IRQ_VECTOR, IRQ_ENTRY, SELECT, TICK, INTC_PENDING, TIMER_STATUS,
    FOREGROUND_PC, OTHER_PC, FOREGROUND_SP, OTHER_SP, REGS,
)
from unicorn import UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_PC, UC_ARM_REG_R2

STARTUP = 0x800617EC
STARTUP_STOP = 0x80061818
UART_REGISTER = 0x80006D5C
INTC_VECTOR = 0x01C20400
INTC_BASE = 0x01C20404
INTC_ENABLE = 0x01C20420
INTC_PRIORITY = 0x01C20460
INTC_FLAG = 0x805AB940
HANDLERS = 0x805AB944
TIMER_SLOT = HANDLERS + 4 * 13
UART_SLOT = HANDLERS + 4 * 3
UART = 0x01C25800
RX_COUNT = 0x805AB938
RX = 0x805B408C
UART_ISR = 0x800073BC
TIMER_ISR = 0x8005BF54
DISPATCH = 0x80005260
REGISTER = 0x80005274
TIMER = 0x01C20C00
TIMER_CONTROL = TIMER + 0x10
TIMER_INTERVAL = TIMER + 0x14
INPUT_BYTE = 0xD6
CTRL = 0x805AAE8C
FSM = 0x805AC694
RESULT = 0x805AC714
TX = 0x805B4154
TX_READY = UART + 0x7C
ARGS = 0x10018600
NEST = 0x805ABBF8
RAW = 0x012345
STORED = (14023, 3)
TRANSPORT_WINDOWS = (
    (0x80004490, 0x80004808), (0x8000482C, 0x80004930), (0x80005E84, 0x80005F10),
    (0x80006DC8, 0x80006E1C), (0x800009C4, 0x80000AFC), (0x80000B4C, 0x80000BA8),
    (0x800031B8, 0x800031E0), (0x80060EFC, 0x80060F58), (0x80061F84, 0x80061FA0),
)
ROUTE_WINDOWS = (
    (STARTUP, STARTUP_STOP), (UART_REGISTER, 0x80006D70),
    (DISPATCH, REGISTER), (REGISTER, 0x80005328), (0x800071A0, 0x80007250),
    (0x8000725C, 0x80007284), (UART_ISR, 0x80007418), (TIMER_ISR, 0x8005BF68),
)
REGISTER_WRITES = (INTC_BASE, INTC_ENABLE, INTC_PRIORITY, TIMER, TIMER_CONTROL, TIMER_INTERVAL)
IRQ_READS = (INTC_PENDING, INTC_VECTOR, TIMER_SLOT, UART_SLOT, UART + 8, UART)


class PeripheralReplay(IrqReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.u.mem_map(UART, 0x1000)
        self.u.mem_map(FSM & ~0xFFF, 0x1000)
        self.u.mem_map(RX & ~0xFFF, 0x1000)
        self.u.hook_add(UC_HOOK_MEM_READ, self.read_access)
        self.irq_active = False
        self.transport_active = False

    def code(self, u, pc, size, data):
        if pc == STARTUP_STOP:
            u.emu_stop()
            return
        if any(start <= pc < end for start, end in ROUTE_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            if pc in (DISPATCH, UART_ISR, TIMER_ISR):
                self.events.append(["pc", hex(pc)])
            return
        if self.transport_active and any(start <= pc < end for start, end in TRANSPORT_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            if pc == 0x80004738:
                self.transport_events.append(["parse", self.read(RX_COUNT), bytes(u.mem_read(RX, 5)).hex()])
            return
        super().code(u, pc, size, data)

    def read_access(self, u, access, address, size, value, data):
        if self.irq_active and address in IRQ_READS:
            assert size == 4
            self.events.append(["read", hex(address), self.read(address)])

    def write(self, u, access, address, size, value, data):
        if self.transport_active:
            if address == UART:
                assert size == 4 and u.reg_read(UC_ARM_REG_PC) == 0x80006E10
                self.transport_events.append(["tx", value & 0xFF])
                return
            if address in (RESULT + 0x1C, RESULT + 0x20):
                assert size == 4
                self.transport_events.append(["publish", hex(address), value])
                return
            if address == CTRL + 1:
                assert size == 1
                self.transport_events.append(["discard", value])
                return
            if (
                FSM <= address and address + size <= FSM + 0x3C
                or TX <= address and address + size <= TX + 200
                or RX <= address and address + size <= RX + 200
                or address in (NEST, 0x805AB920, 0x805AB91C, 0x01C208C4)
            ):
                return
        if address in REGISTER_WRITES or address in (UART_SLOT, TIMER_SLOT, RX_COUNT):
            assert size == 4
            self.events.append(["store", hex(address), value])
            return
        if address == INTC_FLAG or RX <= address < RX + 200:
            assert size == 1
            self.events.append(["store", hex(address), value])
            return
        super().write(u, access, address, size, value, data)

    def configure(self):
        u = self.u
        u.mem_write(INTC_FLAG, bytes(4 + 4 * 41))
        u.mem_write(INTC_VECTOR, bytes(0x100))
        u.mem_write(TIMER, bytes(0x100))
        self.events = []
        self.invoke(STARTUP, stop=STARTUP_STOP)
        assert self.read(TIMER_CONTROL) == 7 and self.read(TIMER_INTERVAL) == 24000
        assert self.read(TIMER) == 1 and self.read(TIMER_SLOT) == TIMER_ISR
        assert self.read(INTC_ENABLE) == 1 << 13 and self.read(INTC_BASE) == HANDLERS
        assert self.read(INTC_PRIORITY) == 3 << 26
        timer_writes = self.events[:]
        self.events = []
        self.invoke(UART_REGISTER)
        assert self.read(UART_SLOT) == UART_ISR and self.read(TIMER_SLOT) == TIMER_ISR
        assert self.read(INTC_ENABLE) == (1 << 13) | (1 << 3) and self.read(INTC_BASE) == HANDLERS
        assert self.read(INTC_PRIORITY) == (3 << 26) | (3 << 6)
        assert [e for e in self.events if e[0] == "store"] == [
            ["store", hex(UART_SLOT), UART_ISR],
            ["store", hex(INTC_PRIORITY), (3 << 26) | (3 << 6)],
            ["store", hex(INTC_ENABLE), (1 << 13) | (1 << 3)],
        ]
        return dict(timer_control=self.read(TIMER_CONTROL), timer_interval=self.read(TIMER_INTERVAL),
                    timer_startup_writes=timer_writes, uart_registration_writes=self.events[:])

    def enter(self, cpsr, return_pc, pending, slot):
        u = self.u
        self.events = []
        self.set_irq_entry(cpsr, return_pc)
        self.put(INTC_PENDING, pending)
        self.put(INTC_VECTOR, slot)
        self.irq_active = True
        try:
            u.emu_start(IRQ_VECTOR, 0, count=10000)
        finally:
            self.irq_active = False
        return self.events[:]

    def assert_uart_route(self, events, pending, ready, initial_count):
        assert [e for e in events if e[0] == "pc"] == [
            ["pc", hex(IRQ_ENTRY)], ["pc", hex(DISPATCH)], ["pc", hex(UART_ISR)], ["pc", "0x80002390"],
        ]
        expected_reads = [
            ["read", hex(INTC_PENDING), pending], ["read", hex(INTC_VECTOR), UART_SLOT],
            ["read", hex(UART_SLOT), UART_ISR], ["read", hex(UART + 8), 4 if ready else 0],
        ]
        if ready:
            expected_reads.append(["read", hex(UART), 0x12AB00 | INPUT_BYTE])
        assert [e for e in events if e[0] == "read"] == expected_reads
        assert not any(e[0] == "mmio_store" for e in events)
        assert self.read(INTC_PENDING) == pending and self.read(TIMER_STATUS) == 0x10
        expected = bytearray([0xA5] * 200)
        accepted = ready and initial_count < 200
        if accepted:
            expected[initial_count] = INPUT_BYTE
        assert self.read(RX_COUNT) == initial_count + int(accepted)
        assert bytes(self.u.mem_read(RX, 200)) == expected
        assert [e for e in events if e[0] == "store"] == (
            [["store", hex(RX_COUNT), initial_count + 1], ["store", hex(RX + initial_count), INPUT_BYTE]]
            if accepted else []
        )

    def run_routing(self, scenario, thumb):
        u = self.u
        tick_path = scenario in ("timer", "both-then-uart")
        self.seed("wake" if tick_path else "idle")
        initial_count = {"uart-last-slot": 199, "uart-full": 200}.get(scenario, 0)
        ready = scenario != "uart-not-ready"
        configuration = self.configure()
        self.put(RX_COUNT, initial_count)
        u.mem_write(RX, bytes((0xA5,)) * 200)
        self.put(UART + 8, 4 if ready else 0)
        self.put(UART, 0x12AB00 | INPUT_BYTE)
        old_cpsr = 0xA000001F | (0x20 if thumb else 0)
        other_cpsr = 0x4000001F | (0 if thumb else 0x20)
        foreground = [0x11110000 + i for i in range(13)] + [FOREGROUND_SP, 0x11223344]
        other = [0x22220000 + i for i in range(13)] + [OTHER_SP, 0x44332211]
        frame = OTHER_SP - 72
        u.mem_write(frame, struct.pack("<18I", 0, other_cpsr, *other, OTHER_PC + 4))
        self.put(OTHER, frame)
        u.reg_write(UC_ARM_REG_CPSR, old_cpsr)
        for reg, value in zip(REGS, foreground):
            u.reg_write(reg, value)

        pending = {"timer": 1 << 13, "both-then-uart": (1 << 13) | (1 << 3)}.get(scenario, 1 << 3)
        slot = TIMER_SLOT if scenario == "timer" else UART_SLOT
        events = self.enter(old_cpsr, FOREGROUND_PC, pending, slot)
        chained = []
        if tick_path:
            assert [e for e in events if e[0] == "pc"] == [
                ["pc", hex(IRQ_ENTRY)], ["pc", hex(TICK)], ["pc", hex(SELECT)], ["pc", "0x80002390"],
            ]
            assert [e for e in events if e[0] == "read"] == [["read", hex(INTC_PENDING), pending]]
            assert [e for e in events if e[0] == "mmio_store"] == [
                ["mmio_store", hex(INTC_PENDING), 0], ["mmio_store", hex(TIMER_STATUS), 1],
            ]
            assert self.read(SCHED + 0xC) == 101 and self.read(SCHED) == OTHER
            assert self.read(RX_COUNT) == initial_count and bytes(u.mem_read(RX, 200)) == bytes((0xA5,)) * 200
            assert u.reg_read(UC_ARM_REG_PC) == OTHER_PC and u.reg_read(UC_ARM_REG_CPSR) == other_cpsr
            assert [u.reg_read(reg) for reg in REGS] == other
            if scenario == "both-then-uart":
                chained = self.enter(other_cpsr, OTHER_PC, 1 << 3, UART_SLOT)
                self.assert_uart_route(chained, 1 << 3, True, initial_count)
                assert self.read(SCHED + 0xC) == 101 and self.read(SCHED) == OTHER
                assert u.reg_read(UC_ARM_REG_PC) == OTHER_PC and u.reg_read(UC_ARM_REG_CPSR) == other_cpsr
                assert [u.reg_read(reg) for reg in REGS] == other
        else:
            self.assert_uart_route(events, pending, ready, initial_count)
            assert self.read(SCHED + 0xC) == 100 and self.read(SCHED) == TASK
            assert u.reg_read(UC_ARM_REG_PC) == FOREGROUND_PC and u.reg_read(UC_ARM_REG_CPSR) == old_cpsr
            assert [u.reg_read(reg) for reg in REGS] == foreground
        return dict(scenario=scenario, interrupted_thumb=thumb, configuration=configuration,
                    first_irq=events, subsequent_explicit_uart_irq=chained,
                    scheduler_count_after=self.read(SCHED + 0xC), rx_count_after=self.read(RX_COUNT),
                    resumed_pc=hex(u.reg_read(UC_ARM_REG_PC)))

    def invoke_transport(self, pc, *args):
        self.transport_active = True
        try:
            self.invoke(pc, *args)
        finally:
            self.transport_active = False

    def transport_irq(self, pending, slot):
        u = self.u
        cpsr = 0xA000001F
        u.reg_write(UC_ARM_REG_CPSR, cpsr)
        foreground = [0x11110000 + i for i in range(13)] + [FOREGROUND_SP, 0x11223344]
        for reg, value in zip(REGS, foreground):
            u.reg_write(reg, value)
        events = self.enter(cpsr, FOREGROUND_PC, pending, slot)
        assert u.reg_read(UC_ARM_REG_PC) == FOREGROUND_PC and u.reg_read(UC_ARM_REG_CPSR) == cpsr
        assert [u.reg_read(reg) for reg in REGS] == foreground and self.read(SCHED) == TASK
        return events

    def run_transport(self, command, reply):
        u = self.u
        self.seed("idle")
        self.configure()
        u.mem_write(FSM, bytes(0x3C))
        u.mem_write(CTRL, bytes(0x10))
        self.put(CTRL + 8, 0x22)
        u.mem_write(CTRL + 1, bytes((int(reply == "discard"),)))
        self.put(RESULT + 0x1C, STORED[0])
        self.put(RESULT + 0x20, STORED[1])
        self.put(RX_COUNT, 0)
        u.mem_write(RX, bytes((0xA5,)) * 200)
        self.put(TX_READY, 2)
        self.put(ARGS, command)
        self.transport_events = []
        # TransactionBuilder uses r2 for one command. invoke() supplies r0 and r1.
        u.reg_write(UC_ARM_REG_R2, 1)
        self.invoke_transport(0x8000489C, 1 if command == 0x1D else 2, ARGS)

        def tick():
            count = self.read(SCHED + 0xC)
            events = self.transport_irq(1 << 13, TIMER_SLOT)
            assert self.read(SCHED + 0xC) == count + 1
            assert ["pc", hex(TICK)] in events and ["pc", hex(UART_ISR)] not in events

        def step():
            self.invoke_transport(0x80004490)
            return u.mem_read(FSM, 1)[0]

        for _ in range(6):
            state = step()
            if state == 3:
                break
            tick()
        assert state == 3 and self.read(RX_COUNT) == 0
        header = 0x60 if command == 0x1D else 0x5E
        sent = [e[1] for e in self.transport_events if e[0] == "tx"]
        assert sent == [header, header]
        payload = bytes((header ^ int(reply == "wrong"),)) + RAW.to_bytes(3, "little") + bytes((8,))
        if reply == "short":
            payload = payload[:-1]
        ingress = []
        for n, byte in enumerate(payload, 1):
            tick()
            self.put(UART + 8, 4)
            self.put(UART, byte)
            before = self.read(SCHED + 0xC)
            events = self.transport_irq(1 << 3, UART_SLOT)
            assert self.read(RX_COUNT) == n and bytes(u.mem_read(RX, n)) == payload[:n]
            assert self.read(SCHED + 0xC) == before and ["pc", hex(UART_ISR)] in events
            ingress.append(dict(counter=before, count=n, byte=byte, irq_events=events))
            state = step()
            if n < 5:
                assert not any(e[0] in ("parse", "publish") for e in self.transport_events)
        for _ in range(3):
            tick()
            state = step()
        parses = [e for e in self.transport_events if e[0] == "parse"]
        publishes = [e for e in self.transport_events if e[0] == "publish"]
        accepted = reply in ("publish", "discard")
        assert state == (0 if accepted else 3)
        assert [e[1] for e in self.transport_events if e[0] == "tx"] == (
            [header] * (4 if reply == "wrong" else 2)
        )
        assert parses == ([["parse", 5, payload.hex()]] if accepted else [])
        if reply == "publish":
            scale = 6 if command == 0x1D else 0
            assert publishes == [["publish", hex(RESULT + 0x1C), RAW], ["publish", hex(RESULT + 0x20), scale]]
            assert (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == (RAW, scale)
        else:
            assert not publishes and (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == STORED
        assert [e for e in self.transport_events if e[0] == "discard"] == (
            [["discard", 0]] if reply == "discard" else []
        )
        return dict(command=hex(command), reply=reply, uart_input_hex=payload.hex(), final_state=state,
                    ingress=ingress, transport_events=self.transport_events[:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    results, versions = [], []
    scenarios = ("timer", "uart-byte", "uart-last-slot", "uart-full", "uart-not-ready", "both-then-uart")
    for image in manifest["images"]:
        raw = (root / image["path"]).read_bytes()
        assert len(raw) == image["size_bytes"] and hashlib.sha256(raw).hexdigest() == image["sha256"]
        replay = PeripheralReplay(raw)
        vector = replay.install_vectors(False)
        rows = [replay.run_routing(*case) for case in product(scenarios, (False, True))]
        transport = [replay.run_transport(*case) for case in product(
            (0x1D, 0x1B), ("publish", "discard", "wrong", "short"),
        )]
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        results.append((rows, coverage, vector, transport))
        versions.append(dict(version=image["version"], input_sha256=image["sha256"],
                             cases=len(rows), transport_cases=len(transport)))
    assert len(results) == 2 and results[0] == results[1]
    report = dict(schema="ys4470.timer0-uart2-irq-routing.v1", versions=versions,
                  vector_setup=results[0][2], cases=results[0][0], instruction_bytes=results[0][1],
                  transport_cases=results[0][3],
                  limits=["Original low-vector install, Timer0 startup and UART2 registration tail execute.",
                          "Task contexts, INTC pending and vector register values, UART status/data and banked IRQ entry are seeded.",
                          "The second UART pending after simultaneous bits is an explicit host reassertion.",
                          "Transport starts at the original transaction builder and advances the original FSM from the host.",
                          "No autonomous timer, interrupt priority arbitration, electrical UART or physical time is modeled."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
