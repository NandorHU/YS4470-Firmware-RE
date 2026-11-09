"""Execute queue creation, enqueue/dequeue, type-6 fallback and UART2 reinit."""

import argparse
import json
import struct
from itertools import groupby
from pathlib import Path

from trace_deferred_producers import CTRL, DEFERRED, FSM, HELPER, PRODUCER, SERVICE
from trace_uart_correlation import COUNT, RET, UART, OriginalUART, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3,
)

QUEUE = 0x1001B000
DATA = QUEUE + 0x50
SIZE = 68
STATUS = 0x805AB920
FLAG = 0x805AB91C
PIN7_CFG = 0x01C20890
PIN8_CFG = 0x01C20894
CLOCK_GATE = 0x01C20068
RESET_GATE = 0x01C202D0
INTC_BASE = 0x01C20404
INTC_ENABLE = 0x01C20420
INTC_PRIORITY = 0x01C20460
VECTOR = 0x805AB950
INIT = 0x80006BB8
IRQ_BIND = 0x80005274
FRAMES = {9: b"\x58\x03\x5b", 0x28: b"\xc1\xc1"}
WINDOWS = (
    (0x80000D74, 0x80000E58),  # ARM division body used by the original UART setup.
    (0x800019D0, 0x80001AC0), (0x800029DC, 0x800029FC), (0x8000302C, 0x800030C4),
    (0x80003DD8, 0x80004050), (0x80004390, 0x80004490), (0x80005274, 0x80005328),
    (0x80005B6C, 0x80005D18), (0x80005F14, 0x80006090),
    (0x80006778, 0x800067C4), (0x80006BB8, 0x80006DA8),
    (0x800418A4, 0x800418A8), (0x80060E48, 0x80060E68), (0x80061838, 0x80061CD4),
)
CONFIG_REGISTERS = (
    PIN7_CFG, PIN8_CFG, 0x01C208AC, CLOCK_GATE, RESET_GATE,
    UART, UART + 4, UART + 8, UART + 0xC, UART + 0x10,
    INTC_BASE, INTC_ENABLE, INTC_PRIORITY,
)


class RealQueueReplay(OriginalUART):
    def code(self, u, pc, size, data):
        r0, r1, r2, r3, lr = (
            u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                                    UC_ARM_REG_R3, UC_ARM_REG_LR)
        )
        if pc == 0x800418A8:
            u.reg_write(UC_ARM_REG_PC, RET)
            return
        if pc == 0x80042AA0:
            assert r0 == 760 and lr == 0x80061858
            u.reg_write(UC_ARM_REG_R0, QUEUE)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc in (0x80060FBC, 0x80011594):
            self.delays.append((pc, lr, r0))
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc in (0x800618DC, 0x80061ACC):
            assert r0 == QUEUE and r3 == 0
            if pc == 0x80061ACC:
                record = bytes(u.mem_read(r1, SIZE))
                assert r2 == (0 if int.from_bytes(record[:4], "little") == 3 else 10)
                self.enqueued.append(record)
            else:
                assert r2 == 0
                self.receives.append(self.rd(QUEUE + 0x38))
        if pc == 0x8000489C and lr == 0x80005C54:
            assert r2 == 1
            self.measurement_starts.append((r0, self.rd(r1)))
        if pc == 0x80003DD8:
            assert self.byte(FSM + 0x34) == self.byte(CTRL) == 0
            record = bytes(u.mem_read(r0, SIZE))
            assert record == bytes(u.mem_read(DEFERRED, SIZE)) == self.expected_deferred
            self.handled.append(record)
        if pc == HELPER:
            assert self.rd(STATUS) == self.rd(FLAG) == 0
            self.commands.append(r0)
        if pc == 0x80003E30:
            self.helper_returns.append(r0)
        if pc == INIT:
            self.init_args.append((r0, r1, r2, r3))
            self.configuring = True
        if pc == IRQ_BIND:
            self.irq_args.append((r0, r1, r2, r3))
        if self.injection and not self.in_isr and pc == self.injection["site"] and not self.injection["done"]:
            assert not u.reg_read(UC_ARM_REG_CPSR) & 0x80
            self.pause = True
            u.emu_stop()
            return
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size in (2, 4)
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if self.configuring and address in CONFIG_REGISTERS:
            assert size == 4
            if access == UC_MEM_WRITE:
                self.config_writes.append((pc, address, value))
            return
        if access == UC_MEM_WRITE and (
            address == CTRL + 4 or address == CTRL
            or DEFERRED <= address and address + size <= DEFERRED + SIZE
            or self.configuring and address in (0x805AB940, VECTOR)
        ):
            return
        super().memory(u, access, address, size, value, data)

    def run_case(self, records, ack, prebound, *, wrap=False, busy=False):
        self.reset()
        self.configuring = False
        self.enqueued, self.receives, self.handled, self.commands = [], [], [], []
        self.measurement_starts = []
        self.helper_returns, self.delays, self.init_args, self.irq_args, self.config_writes = [], [], [], [], []
        self.u.mem_write(0x10010000, bytes(0x10000))
        for address in CONFIG_REGISTERS:
            self.put(address, 0)
        self.put(UART + 0x7C, 2)
        self.put(STATUS, 0x99)
        self.put(FLAG, 0x88)
        self.put(RESET_GATE, 1 << 22)
        if prebound:
            self.u.mem_write(0x805AB940, b"\1")
            self.put(INTC_BASE, 0x805AB944)
            self.put(VECTOR, 0x11223344)
        self.invoke(0x800418A4)
        assert self.rd(CTRL + 4) == QUEUE
        assert (self.rd(QUEUE + 0x3C), self.rd(QUEUE + 0x40)) == (10, SIZE)
        assert self.rd(QUEUE) == DATA and self.rd(QUEUE + 4) == DATA + SIZE * 10
        assert self.rd(QUEUE + 0x38) == 0
        first_slot = 9 if wrap else 0
        if wrap:
            for _ in range(first_slot):
                assert self.invoke(PRODUCER, (7, 0, 0)) == 1
                assert self.invoke(0x800618DC, (QUEUE, 0x10018000, 0, 0)) == 1
            self.enqueued.clear()
            self.receives.clear()
            assert self.rd(QUEUE + 8) == DATA + first_slot * SIZE
        if busy:
            self.build()
            assert self.step(0) == 3 and self.byte(FSM + 0x34) == 1
        for index, (kind, command) in enumerate(records):
            assert self.invoke(PRODUCER, (kind, command, 0x19)) == 1
            assert self.rd(QUEUE + 0x38) == index + 1
            slot = (first_slot + index) % 10
            stored = bytes(self.u.mem_read(DATA + slot * SIZE, SIZE))
            assert stored == self.enqueued[index]
            assert stored[:6] == struct.pack("<IBB", kind, command, 0x19)
        deferred = max(index for index, (kind, _) in enumerate(records) if kind not in (3, 4))
        self.expected_deferred = self.enqueued[deferred]
        active, command = records[deferred]
        starts = records[0][0] in (3, 4)
        busy_gate = None
        expected_receives = list(range(len(records), -1, -1))
        if busy or starts:
            self.invoke(SERVICE)
            assert self.byte(CTRL) == 1 and self.byte(FSM + 0x34) == 1
            assert bytes(self.u.mem_read(DEFERRED, SIZE)) == self.expected_deferred
            assert self.receives == expected_receives and not self.handled and not self.config_writes
            assert [x[2] for x in self.delays] == [1]
            for tick in range(1, 150):
                self.step(tick)
                if self.byte(FSM + 0x34) == 0:
                    break
            assert self.byte(FSM + 0x34) == 0 and self.byte(CTRL) == 1
            busy_gate = dict(model_tick_at_idle=tick, acquisition_wire_hex=bytes(self.wire).hex())
            self.wire.clear()
            self.delays.clear()
            expected_receives.append(0)
        if ack:
            self.injection = dict(site=0x80005FCC, packet=FRAMES[command][:1], done=False)
        self.invoke(SERVICE)
        assert self.rd(QUEUE + 0x38) == self.byte(CTRL) == 0
        assert self.receives == expected_receives
        assert self.handled == [self.expected_deferred]
        assert self.measurement_starts == (
            [(1, 0x1D)] if records[0][0] == 3 else [(2, 0x1B)] if records[0][0] == 4 else []
        )
        assert self.commands == ([command] if active == 6 else [])
        frame = FRAMES.get(command, b"") if active == 6 else b""
        assert bytes(self.wire) == frame * (1 if ack else 2)
        assert self.rd(COUNT) == int(ack)
        if active == 6:
            assert self.helper_returns == [int(ack)]
            assert self.init_args == [(2, 720000000, 19200, 1)]
            assert self.irq_args == [(1, 3, 0x800073BC, 3)]
            assert self.rd(STATUS) == self.rd(FLAG) == 0
            assert self.rd(VECTOR) == 0x800073BC
            assert self.rd(INTC_BASE) == 0x805AB944
            assert self.rd(INTC_ENABLE) == 1 << 3 and self.rd(INTC_PRIORITY) == 3 << 6
            assert self.rd(CLOCK_GATE) == self.rd(RESET_GATE) == 1 << 22
            assert self.rd(PIN7_CFG) == 3 << 28 and self.rd(PIN8_CFG) == 3
            assert self.rd(UART + 0xC) == 3
            assert [w for w in self.config_writes if w[1] in (UART, UART + 4)] == [
                (0x80006CE8, UART + 4, 3), (0x80006D08, UART, 0x49), (0x80006D14, UART + 4, 2),
            ]
            assert [w[2] for w in self.config_writes if w[1] == UART + 0xC] == [0x80, 0, 3]
            assert [w[2] for w in self.config_writes if w[1] == RESET_GATE] == [0, 1 << 22]
            assert sum(w[1] == INTC_BASE for w in self.config_writes) == int(not prebound)
            retries = [] if ack or not frame else [1] * 1000
            assert [x[2] for x in self.delays] == [200] + retries + [200, 10, 1]
        else:
            assert self.rd(STATUS) == 0x99 and self.rd(FLAG) == 0x88
            assert not self.init_args and not self.config_writes and not self.helper_returns
            assert [x[2] for x in self.delays] == [1]
        return dict(records=records, ack=ack, vector_prebound=prebound, first_slot=first_slot,
                    busy_gate=busy_gate,
                    measurement_starts=self.measurement_starts,
                    handled_prefix=self.handled[0][:6].hex(), received_counts=self.receives,
                    commands=self.commands, helper_returns=self.helper_returns, wire_hex=bytes(self.wire).hex(),
                    call_arguments=self.init_args, irq_arguments=self.irq_args,
                    config_writes=[(hex(pc), hex(address), hex(value)) for pc, address, value in self.config_writes],
                    requested_delay_runs=[(hex(pc), hex(lr), value, len(list(run)))
                                          for (pc, lr, value), run in groupby(self.delays)])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    results, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        machine = RealQueueReplay(raw)
        cases = [machine.run_case(records, ack, bound) for bound in (False, True)
                 for records, ack in (
                     (((6, 9),), True), (((6, 9),), False), (((6, 0x28),), True),
                     (((6, 0x30),), False), (((6, 9), (7, 0)), False),
                     (((7, 0), (6, 9)), True),
                 )]
        cases += [
            machine.run_case(((7, 0), (6, 9)), True, False, wrap=True),
            machine.run_case(((6, 9), (7, 0)), False, False, wrap=True),
            machine.run_case(((6, 9),), True, False, busy=True),
        ]
        for immediate in (3, 4):
            cases += [
                machine.run_case(((immediate, 0), (6, 9)), True, False),
                machine.run_case(((6, 9), (immediate, 0)), True, False),
            ]
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=len(cases)))
        results.append((cases, {hex(pc): value for pc, value in sorted(machine.coverage.items())}))
    assert results[0] == results[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.type6-queue-replay.v1", versions=versions, source_sha256=sha(Path(__file__).read_bytes()),
        uart_harness_sha256=sha((Path(__file__).parent / "../uart/trace_uart_correlation.py").read_bytes()),
        shared_cases=results[0][0], shared_instruction_bytes=results[0][1],
        limits=[
            "The host calls the original producer with type 6/7. Native reachability is outside this replay.",
            "The original queue constructor, copy/send/receive and service execute with fixture allocation and empty waiter lists.",
            "UART2 configuration and IRQ binding write memory shadows; both delay primitives and reply arrival are modeled.",
        ],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS", sum(v["cases"] for v in versions), "real-queue type-6/control cases")


if __name__ == "__main__":
    main()
