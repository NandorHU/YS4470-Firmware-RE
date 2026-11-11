"""Replay the native secondary sender and registered USB IRQ on one ARM926 state."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_scheduler_delay_wake import BASE, SCHED, TASK
from trace_scheduler_irq_context import (
    FOREGROUND_PC, FOREGROUND_SP, INTC_PENDING, IRQ_ENTRY, IRQ_VECTOR, REGS,
)
from trace_secondary_channel1 import ChannelRegisters, INDEX, INITIAL_INDEX, LOG, TXCSR, USB, reference_events
from trace_secondary_usb_irq import (
    BUS_STATUS, IRQ, IRQ_LOG_RETURNS, MODE, RX_STATUS, TX_STATUS, WINDOWS as IRQ_WINDOWS,
)
from trace_timer0_uart2_irq import (
    DISPATCH, HANDLERS, INTC_BASE, INTC_ENABLE, INTC_FLAG, INTC_PRIORITY, INTC_VECTOR, PeripheralReplay,
)
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC

SUBMIT, DATA = 0x80060CCC, 0x10017000
READY_A, READY_B, CHUNK, BUSY = 0x805AAC48, 0x805AAC4C, 0x805AAC68, 0x805AAC70
USB_SOURCE = 26
USB_SLOT = HANDLERS + 4 * USB_SOURCE
REG_SUFFIX, REG_STOP = 0x8005FA64, 0x8005FA78
SENDER_WINDOWS = (
    (SUBMIT, 0x80060D84), (0x800009C4, 0x80000B28),
    (0x8005E9B0, 0x8005E9EC), (0x8005FC08, 0x8005FD04),
    (0x80007C2C, 0x80007C88), (0x80007890, 0x800078EC),
)


class LifecycleRegisters(ChannelRegisters):
    def __init__(self, owner):
        self.owner = owner
        self.irq_events = []
        super().__init__(owner.u, [0, 0])

    def read(self, u, access, address, size, value, data):
        if self.owner.phase == "usb_irq":
            assert u.reg_read(UC_ARM_REG_PC) in (0x8000774C, 0x800077C0)
            assert address == TXCSR and size == 2
            assert bytes(u.mem_read(INDEX, 1)) == b"\x01"
            return
        super().read(u, access, address, size, value, data)

    def write(self, u, access, address, size, value, data):
        if self.owner.phase == "usb_irq":
            pc = u.reg_read(UC_ARM_REG_PC)
            assert (pc, address, size) in (
                (0x80007A58, BUS_STATUS, 1), (0x80007A28, TX_STATUS, 2), (0x80007BE4, INDEX, 1),
            )
            self.irq_events.append([hex(address), value])
            return
        assert self.owner.phase == "submit"
        super().write(u, access, address, size, value, data)

class LifecycleReplay(PeripheralReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.phase = None
        self.busy_stores = []
        self.hardware = LifecycleRegisters(self)

    def code(self, u, pc, size, data):
        if self.phase == "usb_register" and pc == REG_STOP:
            u.emu_stop()
            return
        if self.phase in ("submit", "usb_irq") and pc == LOG:
            lr = u.reg_read(UC_ARM_REG_LR)
            assert lr in ((0x8005FC48,) if self.phase == "submit" else IRQ_LOG_RETURNS)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if (
            self.phase == "usb_register" and REG_SUFFIX <= pc < REG_STOP
            or self.phase == "submit" and any(a <= pc < b for a, b in (*SENDER_WINDOWS, *IRQ_WINDOWS))
            or self.phase == "usb_irq" and any(a <= pc < b for a, b in IRQ_WINDOWS)
        ):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
            if pc == IRQ:
                self.events.append(["pc", hex(pc)])
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if USB <= address < USB + 0x1000:
            # The peripheral-specific hook validates register accesses.
            return
        if address == BUSY:
            assert (self.phase, pc, size, value) in (
                ("submit", 0x80060D48, 1, 1), ("usb_irq", 0x800606D4, 1, 0),
            )
            self.busy_stores.append([hex(pc), value])
            return
        if address in (USB_SLOT, INTC_PRIORITY + 4):
            assert self.phase == "usb_register" and size == 4
            self.events.append(["store", hex(address), value])
            return
        super().write(u, access, address, size, value, data)

    def read_access(self, u, access, address, size, value, data):
        if self.irq_active and address == USB_SLOT:
            assert size == 4
            self.events.append(["read", hex(address), self.read(address)])
        super().read_access(u, access, address, size, value, data)

    def register_usb(self):
        self.u.mem_write(INTC_FLAG, bytes(4 + 4 * 41))
        self.u.mem_write(INTC_VECTOR, bytes(0x100))
        self.events = []
        self.phase = "usb_register"
        try:
            self.invoke(REG_SUFFIX, stop=REG_STOP)
        finally:
            self.phase = None
        expected = [["store", hex(INTC_FLAG), 1], ["store", hex(INTC_BASE), HANDLERS],
                    ["store", hex(USB_SLOT), IRQ], ["store", hex(INTC_PRIORITY + 4), 3 << 20],
                    ["store", hex(INTC_ENABLE), 1 << USB_SOURCE]]
        assert self.events == expected
        assert self.read(USB_SLOT) == IRQ and self.read(INTC_ENABLE) == 1 << USB_SOURCE
        return self.events[:]

    def submit(self, frame, accepted):
        self.u.mem_write(DATA, frame)
        start = len(self.hardware.events)
        self.phase = "submit"
        try:
            self.invoke(SUBMIT, DATA, len(frame))
        finally:
            self.phase = None
        observed = self.hardware.events[start:]
        assert observed == (reference_events(frame, [64]) if accepted else [])
        assert self.read(BUSY) == 1
        return dict(frame=frame.hex(), accepted=accepted, writes=observed)

    def inject_usb_irq(self, ready, thumb):
        u = self.u
        u.mem_write(TX_STATUS, b"\x02\x00")
        u.mem_write(RX_STATUS, b"\x00\x00")
        u.mem_write(BUS_STATUS, b"\x00")
        u.mem_write(TXCSR, bytes((int(not ready), 0)))
        self.hardware.irq_events = []
        cpsr = 0xA000001F | (0x20 if thumb else 0)
        values = [0xAABB0000 + i for i in range(13)] + [FOREGROUND_SP, 0x11223344]
        u.reg_write(UC_ARM_REG_CPSR, cpsr)
        for reg, value in zip(REGS, values):
            u.reg_write(reg, value)
        self.phase = "usb_irq"
        try:
            route = self.enter(cpsr, FOREGROUND_PC, 1 << USB_SOURCE, USB_SLOT)
        finally:
            self.phase = None
        expected = [["pc", hex(IRQ_ENTRY)], ["read", hex(INTC_PENDING), 1 << USB_SOURCE],
                    ["pc", hex(DISPATCH)], ["read", hex(INTC_VECTOR), USB_SLOT],
                    ["read", hex(USB_SLOT), IRQ],
                    ["pc", hex(IRQ)], ["pc", "0x80002390"]]
        assert route == expected, route
        assert u.reg_read(UC_ARM_REG_PC) == FOREGROUND_PC and u.reg_read(UC_ARM_REG_CPSR) == cpsr
        assert [u.reg_read(reg) for reg in REGS] == values
        assert self.read(SCHED) == TASK and self.read(SCHED + 0xC) == 100
        assert self.read(BUSY) == int(not ready)
        assert bytes(u.mem_read(INDEX, 1)) == bytes((INITIAL_INDEX,))
        return dict(ready=ready, busy_after=self.read(BUSY), route=route, writes=self.hardware.irq_events)

    def run_lifecycle(self, first_arg, busy_interrupt_first, thumb):
        vectors = self.install_vectors(high_before=False)
        self.seed("idle")
        registration = self.register_usb()
        for address, value in ((MODE, 1), (READY_A, 1), (READY_B, 1), (CHUNK, 64), (BUSY, 0)):
            self.put(address, value)
        first = bytes((0, 0x10, 0x40, 2, 4, first_arg, 255, 255)) + bytes(56)
        second = bytes((0, 0x10, 0x40, 2, 4, 7 - first_arg, 255, 255)) + bytes(56)
        steps = [self.submit(first, True), self.submit(second, False)]
        if busy_interrupt_first:
            steps.extend([self.inject_usb_irq(False, thumb), self.submit(second, False)])
        steps.extend([self.inject_usb_irq(True, thumb), self.submit(second, True)])
        assert self.busy_stores == [["0x80060d48", 1], ["0x800606d4", 0], ["0x80060d48", 1]]
        return dict(first_arg=first_arg, busy_interrupt_first=busy_interrupt_first,
                    interrupted_thumb=thumb, vectors=vectors, registration=registration, steps=steps,
                    busy_stores=self.busy_stores,
                    instruction_bytes={hex(pc): self.coverage[pc] for pc in sorted(self.coverage)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        observations.append([
            LifecycleReplay(raw).run_lifecycle(*case)
            for case in product((3, 4), (False, True), (False, True))
        ])
        images[item["version"]] = digest
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.secondary-usb-lifecycle.v1", images=images, cases=observations[0], limits=[
        "Original vector installation, USB source-26 registration suffix, dispatcher, sender and USB interrupt handler execute in a single ARM926 state.",
        "The harness supplies the 64-byte application frames and initial gadget-mode guards. CPU-visible USB and interrupt-controller status are modeled. Log calls are modeled.",
        "The experiment proves the tested busy lifecycle through the CPU-visible FIFO and exception return. Physical USB transfer, host protocol, and hardware timing were not tested.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 registered USB sender/IRQ lifecycles per factory image, 16 total")


if __name__ == "__main__":
    main()
