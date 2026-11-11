"""Replay five more registered callbacks in the original second GUI block."""

import argparse
import hashlib
import json
from pathlib import Path

from trace_control_gui_cfd0 import NATIVE_WINDOWS, SECONDARY_READY, SECONDARY_RETURN
from trace_control_gui_events import (
    EventReplay, INDIRECT, MODE, OBJECTS, PREVIOUS, QUEUE, RECORD_SIZE,
    SECOND_BINDINGS, SECOND_LITERALS, SECOND_REGISTER, SECOND_STOP, SOUND_ENABLE, TIMER, UI,
)
from trace_scheduler_delay_wake import BASE
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3,
)

CDC8, CE78, D538, D648, D740 = 0x8000CDC8, 0x8000CE78, 0x8000D538, 0x8000D648, 0x8000D740
RESULT_FIELD, STATIC_LABEL = 0x805AC730, 0x10017400
OBJECTS_BY_OFFSET = {offset: OBJECTS + i * 0x40 for i, (offset, _, _) in enumerate(SECOND_BINDINGS)}
OBJECTS_BY_OFFSET[0x2F4] = STATIC_LABEL
NATIVE_CALLBACKS = ((CDC8, 0x8000CE68), (CE78, 0x8000CF64), (D538, 0x8000D62C),
                    (D648, 0x8000D72C), (D740, 0x8000D838))
MODEL_LEAVES = {
    0x8000299C: {0x8000CDD0, 0x8000CF1C, 0x8000D5E0, 0x8000D650, 0x8000D7E8},
    0x800028FC: {0x8000CE8C, 0x8000D54C, 0x8000D754},
    0x80024CA4: {0x8000CDD8, 0x8000CE98, 0x8000CF24, 0x8000D558, 0x8000D5E8,
                 0x8000D658, 0x8000D6F8, 0x8000D760, 0x8000D7F0},
    0x8003A718: {0x8000CDF0, 0x8000CEB0, 0x8000CF38, 0x8000D570, 0x8000D5FC,
                 0x8000D670, 0x8000D70C, 0x8000D778, 0x8000D804},
    0x800339BC: {0x8000CEBC, 0x8000D57C},
    0x80034A50: {0x8000D784},
    0x80034B04: {0x8000D814},
    0x80032038: {0x8000CF4C, 0x8000D610, 0x8000D820},
}
MODE_WRITES = {
    0x8000CDFC: 1, 0x8000CE44: 8, 0x8000CE84: 0, 0x8000CF08: 6,
    0x8000CF0C: 7, 0x8000CF14: 8, 0x8000CF3C: 1, 0x8000CF50: 9,
    0x8000D544: 0, 0x8000D5C8: 6, 0x8000D5D0: 7, 0x8000D5D8: 8,
    0x8000D600: 1, 0x8000D618: 9, 0x8000D67C: 1, 0x8000D6C4: 8,
    0x8000D6DC: 7, 0x8000D6E4: 8, 0x8000D6EC: 2, 0x8000D74C: 0,
    0x8000D7D0: 6, 0x8000D7D8: 7, 0x8000D7E0: 8, 0x8000D804: 1, 0x8000D824: 9,
}
TIMER_WRITES = [["0x80040b50", hex(TIMER + 0x14), 1], ["0x80040b84", hex(TIMER), 100],
                ["0x80040b7c", hex(TIMER + 0x14), 0]]
CASES = ((CDC8, 9), (CDC8, 0x22), (CE78, 9), (D538, 9), (D740, 9),
         (D648, 9), (D648, 10), (D648, 12), (D648, 0x22), (D648, 0x0F))


def expected(callback, selector):
    if callback == CDC8:
        return (0x8000CE58, selector, 0x19), {1: 0, 8: 0x19}, None
    if callback == D648:
        if selector in (9, 10):
            return (0x8000D6D4, selector, 0x13), {1: 1, 8: 0x13}, None
        if selector in (12, 0x22):
            return (0x8000D71C, 12, 0x15), {1: 1, 2: 0, 7: 12, 8: 0x15}, None
        return None, {1: 1}, None
    mode, selector, ret, extra, second_return = {
        CE78: (2, 0xF, 0x8000CF04, 1, 0x8000CEF0),
        D538: (1, 0xC, 0x8000D5C4, 0, 0x8000D5B0),
        D740: (0, 9, 0x8000D7CC, 1, 0x8000D7B8),
    }[callback]
    return (ret, selector, 0x19), {0: mode, 1: 0, 6: 2, 7: selector, 8: 0x19, 9: extra}, (second_return, mode)


class GroupReplay(EventReplay):
    def code(self, u, pc, size, data):
        if self.phase != "dispatch":
            return super().code(u, pc, size, data)
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc in MODEL_LEAVES:
            assert lr in MODEL_LEAVES[pc], (hex(pc), hex(lr))
            if pc == 0x80024CA4:
                assert r0 in (0xFA7700, 0x2A2A2A)
            if pc == 0x8003A718:
                assert r0 in OBJECTS_BY_OFFSET.values() and r1 in (0xFA7700, 0x2A2A2A) and r2 == 0
            if pc in (0x800339BC, 0x80034A50, 0x80034B04):
                assert (r0, r1) == (OBJECTS_BY_OFFSET[0x300], 1)
            if pc == 0x80032038:
                assert r0 == STATIC_LABEL and bytes(u.mem_read(r1, 5)) == b"----\0"
            self.ui_leaves.append([hex(pc), hex(lr)])
            self.return_leaf(u, lr, r0)
            return
        if pc == 0x8005F254:
            self.secondary.append([hex(lr), r0, r1, r2, r3])
        if pc == SECONDARY_RETURN and u.reg_read(UC_ARM_REG_CPSR) & (1 << 30):
            self.secondary_returns.append(r0)
        if pc == 0x80006E4C:
            assert (r0, r1) == (5, 1) and self.read(SOUND_ENABLE) == 0
            assert lr == (0x8000D620 if self.callback == D538 else 0x8001B034)
            self.sound.append(hex(lr))
        if pc == 0x80006E4C or any(lo <= pc < hi for lo, hi in (*NATIVE_CALLBACKS, *NATIVE_WINDOWS[1:])):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "dispatch" and (MODE <= address < MODE + 10 or address == RESULT_FIELD):
            pc = u.reg_read(UC_ARM_REG_PC)
            if address == RESULT_FIELD:
                assert (pc, size, value) == (0x8000D624, 4, 0)
            else:
                assert size == 1 and MODE_WRITES.get(pc) == address - MODE
            return
        super().write(u, access, address, size, value, data)

    def run(self, callback, selector, event):
        producer, changes, secondary = expected(callback, selector)
        idx = next(i for i, (_, address, _) in enumerate(SECOND_BINDINGS) if address == callback)
        queue_before = self.prepare_dispatch(idx, event, callback, producer[0] if producer else 0)
        self.secondary, self.secondary_returns, self.sound = [], [], []
        initial = bytearray(b"\xA5" * 10)
        initial[7] = selector
        self.u.mem_write(MODE, bytes(initial))
        self.put(SECONDARY_READY, 0)
        self.put(SOUND_ENABLE, 0)
        self.put(RESULT_FIELD, 0x12345678)
        for offset, address in OBJECTS_BY_OFFSET.items():
            self.put(UI + offset, address)
        self.dispatch()
        prefix = None
        if event == 1:
            assert self.calls == [[hex(INDIRECT), hex(callback)]]
            assert self.drained == [*PREVIOUS, None] + ([None] if callback == CDC8 else [])
            assert self.timer_stores == TIMER_WRITES * (2 if callback == CDC8 else 1)
            assert self.sound == ["0x8000d620" if callback == D538 else "0x8001b034"]
            for offset, value in changes.items():
                initial[offset] = value
            if secondary:
                ret, mode = secondary
                assert self.secondary == [[hex(ret), 4, mode, 255, 255]]
                assert self.secondary_returns == [0xFFFFFFFF]
            else:
                assert not self.secondary and not self.secondary_returns
            if producer:
                _, arg, format_byte = producer
                expected_prefix = bytes((2, 0, 0, 0, arg, format_byte))
                assert self.producer_args == [[2, arg, format_byte]]
                (copy,), slot = self.copies, self.read(QUEUE) + 2 * RECORD_SIZE
                assert copy[:6] == expected_prefix and bytes(self.u.mem_read(slot, RECORD_SIZE)) == copy
                prefix = expected_prefix.hex()
            else:
                assert not self.producer_args and not self.copies
            assert self.read(QUEUE + 0x38) == int(bool(producer))
            assert self.read(RESULT_FIELD) == (0 if callback == D538 else 0x12345678)
        else:
            assert not any((self.calls, self.drained, self.timer_stores, self.sound, self.secondary,
                            self.secondary_returns, self.producer_args, self.copies, self.ui_leaves))
            assert bytes(self.u.mem_read(QUEUE, 760)) == queue_before and self.read(TIMER) == 77
            assert self.read(RESULT_FIELD) == 0x12345678
        assert bytes(self.u.mem_read(MODE, 10)) == bytes(initial)
        return dict(callback=hex(callback), selector=selector, event=event, indirect_calls=self.calls,
                    record_prefix=prefix, mode_after=bytes(initial).hex(), result_after=self.read(RESULT_FIELD),
                    drained=self.drained, timer_stores=self.timer_stores, secondary_args=self.secondary,
                    secondary_returns=self.secondary_returns, sound_return_sites=self.sound,
                    producer_args=self.producer_args, queue_count=self.read(QUEUE + 0x38),
                    modeled_ui_calls=self.ui_leaves)


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
        replay = GroupReplay(raw)
        registrations = replay.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)
        cases = [replay.run(*case, event) for case in CASES for event in (1, 2)]
        assert sum(case["record_prefix"] is not None for case in cases) == 9
        images[item["version"]] = digest
        observations.append(dict(registrations=registrations, cases=cases, instruction_bytes={
            hex(pc): data for pc, data in sorted(replay.coverage.items())
        }))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.control-gui-second-group.v1", images=images, **observations[0], limits=[
        "Original registration, indirect dispatch, selected callback, timer stores, drains and queue producer execute in a seeded idle scheduler.",
        "UI leaves are modeled. Secondary and sound calls take the original disabled path. The test seeds selector and foreground event values; it does not model physical input.",
        "These five callbacks are covered for the listed local state and event cases. Native type-6 provenance outside these paths and downstream physical timing remain open.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 20 registered GUI cases per factory image, 40 total")


if __name__ == "__main__":
    main()
