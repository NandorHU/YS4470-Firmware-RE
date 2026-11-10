"""Replay original GUI registration and indirect dispatch into the control queue."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_gauge_scheduled_service import CTRL, PRODUCER, QUEUE, RECORD_SIZE, SELECTION, GaugeReplay
from trace_scheduler_delay_wake import BASE, RET, SCHED, STACK, TASK
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4,
)

REGISTER, STOP, LITERALS = 0x8004C3B4, 0x8004C47C, 0x8004C50C
SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS = 0x800517F4, 0x800518BC, 0x80051994
EVENT_SEND, INDIRECT = 0x8002C758, 0x8001B030
EVENT_CURRENT, EVENT_INPUT, EXTRA_COUNT = 0x805ABC18, 0x805ABC28, 0x805ABC30
UI, TIMER_HANDLE = 0x805AC098, 0x805ABEB8
MODE, TYPE2_CALLBACK, SOUND_ENABLE = 0x805ABEFC, 0x8000D294, 0x805AC780
CONTEXT, OBJECTS, EXTRAS, DESCRIPTORS = 0x10011000, 0x10015000, 0x10016000, 0x10016300
TIMER, DRAIN, LABEL = 0x10016800, 0x10016900, 0x10017A00
PREVIOUS_EVENT = 0x10017800
PREVIOUS = ("030000000019", "010000002b19")
# UI context offset, native callback, return after native producer BL, period, record prefix.
BUTTONS = (
    (0x424, 0x8000E798, 0x8000E7E4, 10000, "010000002713"),
    (0x42C, 0x8000E5F0, 0x8000E638, 1000, "000000000913"),
    (0x480, 0x8000E43C, 0x8000E484, 1000, "010000000f19"),
    (0x478, 0x8000E3B0, 0x8000E3F8, 1000, "010000000f19"),
    (0x470, 0x8000E328, 0x8000E370, 1000, "010000000c19"),
    (0x468, 0x8000E298, 0x8000E2E0, 3000, "010000000919"),
    (0x44C, 0x8000E680, 0x8000E6C8, 500, "010000002b00"),
    (0x444, 0x8000E70C, 0x8000E754, 500, "010000002a00"),
    (0x43C, 0x8000E55C, 0x8000E5A4, 2000, "010000002900"),
    (0x434, 0x8000E4C8, 0x8000E510, 2000, "010000002800"),
)
SECOND_BINDINGS = (
    (0x2C8, 0x8000CDC8, 1), (0x2D0, 0x8000D648, 1),
    (0x2E8, 0x8000D294, 1), (0x2D8, 0x8000D43C, 1),
    (0x2E0, 0x8000CFB8, 1), (0x2A0, 0x8000D740, 1),
    (0x2A8, 0x8000D538, 1), (0x2B0, 0x8000CE78, 1),
    (0x2B8, 0x8000CFD0, 1), (0x300, 0x8000F3B4, 0x1C),
)
WINDOWS = (
    (SECOND_REGISTER, SECOND_STOP), (REGISTER, STOP), (0x800338DC, 0x800339B8), (0x80034380, 0x800343E0),
    (0x80032E14, 0x80032EA4), (EVENT_SEND, 0x8002C7B8),
    (0x8001AE74, 0x8001B0F8), (0x8001B168, 0x8001B198),
    (0x8002F3A4, 0x8002F3B0), (0x80003D74, 0x80003DB8),
    (0x80040B4C, 0x80040B58), (0x80040B78, 0x80040B8C),
    (0x8000E298, 0x8000E80C), (TYPE2_CALLBACK, 0x8000D3B0), (0x80006E4C, 0x80006E60),
)


def within(address, size, start, length):
    return start <= address and address + size <= start + length


class EventReplay(GaugeReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.phase = None

    def return_leaf(self, u, lr, value):
        u.reg_write(UC_ARM_REG_R0, value)
        u.reg_write(UC_ARM_REG_PC, lr)
        if not lr & 1:
            u.reg_write(UC_ARM_REG_CPSR, u.reg_read(UC_ARM_REG_CPSR) & ~0x20)

    def code(self, u, pc, size, data):
        if self.phase is None:
            return super().code(u, pc, size, data)
        if self.phase == "register" and pc == self.registration_stop:
            u.emu_stop()
            return
        r0, r1, r2, r3, lr = (u.reg_read(r) for r in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc == 0x80032800:
            assert self.phase == "register" and lr == 0x800343AC and r0 == 28
            assert self.read(EXTRA_COUNT) == len(self.registrations)
            self.return_leaf(u, lr, EXTRAS + (len(self.registrations) - 1) * 0x40)
            return
        if pc == 0x80032AE4:
            assert self.phase == "register" and lr == 0x8003392C and (r0, r1) == (0, 12)
            self.return_leaf(u, lr, DESCRIPTORS + (len(self.registrations) - 1) * 0x10)
            return
        if pc in (0x80042AA0, 0x80060F5C):
            assert self.phase == "dispatch"
            if pc == 0x80042AA0:
                assert (r0, lr) == (RECORD_SIZE, 0x80003D88)
            else:
                assert r0 == DRAIN
            self.return_leaf(u, lr, DRAIN if pc == 0x80042AA0 else 0)
            return
        if pc == 0x80000544:
            assert self.phase == "dispatch" and size == 2 and u.reg_read(UC_ARM_REG_CPSR) & 0x20
            assert within(r0, 1, STACK - 0x300, 0x300)
            assert BASE <= r1 < 0x8000E834 and BASE <= r2 < 0x8000E834
            u.mem_write(r0, b"\0")
            self.ui_leaves.append([hex(pc), hex(lr)])
            self.return_leaf(u, lr, 0)
            return
        if pc in (0x80024CA4, 0x8003A718):
            assert self.phase == "dispatch" and self.callback == TYPE2_CALLBACK
            if pc == 0x80024CA4:
                assert r0 in (0x2A2A2A, 0xFA7700)
            else:
                assert r0 == LABEL and r2 == 0
            self.ui_leaves.append([hex(pc), hex(lr)])
            self.return_leaf(u, lr, r0)
            return
        if pc == 0x80006E4C:
            assert (r0, r1, lr) == (5, 1, 0x8001B034) and self.read(SOUND_ENABLE) == 0
        if pc == 0x80032038:
            assert self.phase == "dispatch" and r0 == LABEL and within(r1, 1, STACK - 0x300, 0x300)
            self.ui_leaves.append([hex(pc), hex(lr)])
            self.return_leaf(u, lr, r0)
            return
        if pc == 0x800338DC:
            assert self.phase == "register" and r3 == 0
            self.registrations.append([hex(lr), hex(r0), hex(r1), r2])
        if pc == INDIRECT:
            assert self.phase == "dispatch" and self.read(r0) == self.read(r0 + 4) == self.object
            assert u.mem_read(r0 + 8, 1)[0] == self.event and self.read(r0 + 0xC) == self.read(r0 + 0x10) == 0
            assert self.read(EVENT_CURRENT) == r0 and r1 == self.callback
            assert self.read(r0 + 0x14) == PREVIOUS_EVENT
            self.calls.append([hex(pc), hex(r1)])
        if pc == PRODUCER:
            assert self.phase == "dispatch" and lr == self.producer_return
            self.producer_args.append([r0, r1, r2])
        if pc == 0x80003DA4:
            assert r0 in (0, 1)
            self.drained.append(bytes(u.mem_read(DRAIN, 6)).hex() if r0 else None)
        if pc == 0x80061ACC:
            assert r0 == QUEUE and (r2, r3) == (10, 0)
            self.copies.append(bytes(u.mem_read(r1, RECORD_SIZE)))
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "register":
            assert (
                address == EXTRA_COUNT and size == 4
                or within(address, size, STACK - 0x300, 0x300)
                or within(address, size, OBJECTS, 0x280)
                or within(address, size, EXTRAS, 0x280)
                or within(address, size, DESCRIPTORS, 0xA0)
            ), (hex(u.reg_read(UC_ARM_REG_PC)), hex(address))
            return
        if self.phase == "dispatch":
            if self.callback == TYPE2_CALLBACK and address in (MODE + 2, MODE + 7, MODE + 8):
                assert size == 1
                return
            if within(address, size, DRAIN, RECORD_SIZE) or address == EVENT_CURRENT and size == 4:
                return
            if address in (TIMER, TIMER + 0x14) and size == 4:
                self.timer_stores.append([hex(u.reg_read(UC_ARM_REG_PC)), hex(address), value])
                return
            assert not (CTRL + 4 <= address < CTRL + 8), hex(address)
        super().write(u, access, address, size, value, data)

    def interrupt(self, u, number, data):
        assert self.phase is None, number
        super().interrupt(u, number, data)

    def register(self, entry, stop, literal_base, bindings):
        u = self.u
        self.put(EXTRA_COUNT, 0)
        u.mem_write(OBJECTS, bytes(0x280))
        u.mem_write(EXTRAS, b"\xA5" * 0x280)
        u.mem_write(DESCRIPTORS, b"\xA5" * 0xA0)
        for idx, (offset, _, _) in enumerate(bindings):
            self.put(CONTEXT + offset, OBJECTS + idx * 0x40)
        self.registrations = []
        self.registration_stop = stop
        u.reg_write(UC_ARM_REG_R4, CONTEXT)
        self.phase = "register"
        try:
            self.invoke(entry, stop=stop)
        finally:
            self.phase = None
        assert self.read(EXTRA_COUNT) == len(bindings)
        table = []
        for idx, (offset, callback, event) in enumerate(bindings):
            obj, extra, desc = OBJECTS + idx * 0x40, EXTRAS + idx * 0x40, DESCRIPTORS + idx * 0x10
            return_pc, literal = entry + (idx + 1) * 20, literal_base + idx * 4
            assert self.registrations[idx] == [hex(return_pc), hex(obj), hex(callback), event]
            assert self.read(obj + 8) == extra and self.read(extra + 0xC) == desc
            assert u.mem_read(extra + 0x1A, 1)[0] == 1
            assert self.read(desc) == callback and self.read(desc + 4) == 0 and u.mem_read(desc + 8, 1)[0] == event
            assert self.read(literal) == callback
            table.append(dict(registration_call=hex(return_pc - 4),
                              object_offset=hex(offset), literal=hex(literal),
                              callback=hex(callback), event_filter=event, descriptor=hex(desc),
                              bytes=bytes(u.mem_read(desc, 12)).hex()))
        return table

    def prepare_dispatch(self, idx, event, callback, producer_return):
        self.callback, self.producer_return = callback, producer_return
        self.object, self.event = OBJECTS + idx * 0x40, event
        self.seed("idle")
        u = self.u
        u.mem_write(CTRL, bytes(16))
        u.mem_write(QUEUE, b"\xA5" * 760)
        self.invoke_transport(0x800029DC)
        self.enqueue(3, 0)
        self.enqueue(1, 0x2B)
        assert self.read(QUEUE + 0x38) == 2
        queue_before = bytes(u.mem_read(QUEUE, 760))
        self.put(EVENT_CURRENT, PREVIOUS_EVENT)
        self.put(EVENT_INPUT, 0)
        self.put(TIMER_HANDLE, TIMER)
        self.put(UI + 0x4A8, LABEL)
        u.mem_write(TIMER, bytes(24))
        self.put(TIMER, 77)
        u.mem_write(SELECTION, b"\xA5\xA5")
        self.calls, self.producer_args, self.drained = [], [], []
        self.copies, self.ui_leaves, self.timer_stores = [], [], []
        return queue_before

    def dispatch(self):
        self.phase, self.transport_active = "dispatch", True
        self.u.reg_write(UC_ARM_REG_R2, 0)
        try:
            assert self.invoke(EVENT_SEND, self.object, self.event) == 1
        finally:
            self.phase, self.transport_active = None, False
        assert self.read(EVENT_CURRENT) == PREVIOUS_EVENT and self.read(CTRL + 4) == QUEUE
        assert self.read(SCHED) == TASK and self.read(SCHED + 0xC) == 100

    def check_send(self, expected, period):
        assert self.producer_args == [[expected[0], expected[4], expected[5]]]
        assert self.drained == [*PREVIOUS, None]
        (copy,), data = self.copies, self.read(QUEUE)
        assert copy[:6] == expected and bytes(self.u.mem_read(data + 2 * RECORD_SIZE, RECORD_SIZE)) == copy
        assert self.read(QUEUE + 0x38) == 1
        assert self.timer_stores == [
            ["0x80040b50", hex(TIMER + 0x14), 1], ["0x80040b84", hex(TIMER), period],
            ["0x80040b7c", hex(TIMER + 0x14), 0],
        ]

    def run_event(self, idx, event):
        _, callback, producer_return, period, prefix = BUTTONS[idx]
        queue_before = self.prepare_dispatch(idx, event, callback, producer_return)
        self.dispatch()
        u = self.u
        if event == 1:
            expected = bytes.fromhex(prefix)
            assert self.calls == [[hex(INDIRECT), hex(self.callback)]]
            self.check_send(expected, period)
            selection = bytes((9, 0x13)) if self.callback == 0x8000E798 else expected[4:]
            assert bytes(u.mem_read(SELECTION, 2)) == selection
            assert len(self.ui_leaves) == 2
        else:
            assert not any((self.calls, self.producer_args, self.drained, self.copies, self.ui_leaves, self.timer_stores))
            assert bytes(u.mem_read(QUEUE, 760)) == queue_before and self.read(TIMER) == 77
            assert bytes(u.mem_read(SELECTION, 2)) == b"\xA5\xA5"
        return dict(callback=hex(self.callback), event=event, indirect_calls=self.calls,
                    producer_args=self.producer_args, drained=self.drained,
                    queue_count=self.read(QUEUE + 0x38), record_prefix=prefix if self.copies else None,
                    restored_event_link=hex(PREVIOUS_EVENT),
                    timer_stores=self.timer_stores, modeled_ui_calls=self.ui_leaves)


    def run_type2(self, mode, option, enabled):
        send = mode == 1 and (enabled == 1 or option == 1)
        return_pc = 0x8000D3A0 if enabled else 0x8000D354
        queue_before = self.prepare_dispatch(2, 1, TYPE2_CALLBACK, return_pc)
        u = self.u
        u.mem_write(MODE, bytes((mode, option, enabled)) + bytes(4) + b"\xA5\xA5")
        self.put(SOUND_ENABLE, 0)
        self.put(UI + 0x2E8, LABEL)
        self.dispatch()
        assert self.calls == [[hex(INDIRECT), hex(TYPE2_CALLBACK)]] and len(self.ui_leaves) == 2
        assert bytes(u.mem_read(MODE, 3)) == bytes((mode, option, 1 - enabled))
        prefix = None
        if send:
            r1, r2 = (0xC if enabled else 0x22), (0x15 if option else 0x19)
            expected = bytes((2, 0, 0, 0, r1, r2))
            self.check_send(expected, 100)
            assert bytes(u.mem_read(MODE + 7, 2)) == expected[4:]
            prefix = expected.hex()
        else:
            assert not any((self.producer_args, self.drained, self.copies, self.timer_stores))
            assert bytes(u.mem_read(QUEUE, 760)) == queue_before and self.read(TIMER) == 77
            assert bytes(u.mem_read(MODE + 7, 2)) == b"\xA5\xA5"
        return dict(flags=[mode, option, enabled], enabled_after=1-enabled,
                    callback=hex(TYPE2_CALLBACK), producer_return=hex(return_pc) if send else None,
                    record_prefix=prefix, drained=self.drained, timer_stores=self.timer_stores,
                    queue_count=self.read(QUEUE + 0x38), modeled_ui_calls=self.ui_leaves)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, observations = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert len(raw) == item["size_bytes"] and digest == item["sha256"]
        replay = EventReplay(raw)
        primary = [(offset, callback, 1) for offset, callback, *_ in BUTTONS]
        registration = replay.register(REGISTER, STOP, LITERALS, primary)
        cases = [replay.run_event(idx, event) for idx in range(len(BUTTONS)) for event in (1, 2)]
        second_registration = replay.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)
        type2_cases = [replay.run_type2(*flags) for flags in product((0, 1), repeat=3)]
        assert sum(case["record_prefix"] is not None for case in type2_cases) == 3
        images.append(dict(version=item["version"], input_sha256=digest, cases=len(cases),
                           type2_cases=len(type2_cases), registration_runs=2))
        observations.append(dict(registration=registration, second_registration=second_registration,
                                 cases=cases, type2_cases=type2_cases, instruction_bytes={
            hex(pc): code for pc, code in sorted(replay.coverage.items())
        }))
    assert len(images) == 2 and observations[0] == observations[1]
    report = dict(schema="ys4470.control-gui-event-dispatch.v1", images=images, **observations[0], limits=[
        "The two original registration suffixes take a seeded UI context and ten distinct objects each. Original event extras and callback descriptors are initialized with modeled allocation.",
        "The event dispatcher, callback, timer stores, queue drain, producer and send execute the original image. Event code and object selection are supplied by the harness, with class and input-device callbacks inactive.",
        "UI formatting, text display and selected style leaves are modeled. The original sound helper takes its disabled path for type 2. The scheduler is idle, with no hardware input or IRQ progression.",
        "The second block dispatches only 0x8000d294, with all eight binary flag combinations. Native type-6 provenance and other indirect paths remain open.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 40 first-block event cases and 16 type-2 cases across V3.6 and V3.8")


if __name__ == "__main__":
    main()
