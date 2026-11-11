"""Replay a native AC checkbox release through its derived value-change event."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_control_gui_events import (
    EVENT_CURRENT, EVENT_SEND, INDIRECT, MODE, PREVIOUS_EVENT, QUEUE, SECOND_BINDINGS,
    SECOND_LITERALS, SECOND_REGISTER, SECOND_STOP, SOUND_ENABLE, TIMER, UI,
)
from trace_control_gui_second_final import FLAG_EVENT, WIDGETS, FinalReplay
from trace_scheduler_delay_wake import BASE
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

CHECKBOX_CLASS, CHECKBOX_EVENT = 0x80068E70, 0x800246A8
BASE_CLASS, BASE_EVENT = 0x80063B0C, 0x80035428
CHECKBOX, RELEASED, VALUE_CHANGED = WIDGETS[0x300], 8, 0x1C
WINDOWS = (
    (CHECKBOX_EVENT, 0x8002470C), (BASE_EVENT, 0x80035560),
    (0x800356E8, 0x80035700), (0x80035A1C, 0x80035A7C),
    (0x8003A368, 0x8003A3B8), (0x8000AEF4, 0x8000AF20), (0x8000B278, 0x8000B280),
    (0x8002C688, 0x8002C69C), (0x8002C740, 0x8002C750), (0x8002F450, 0x8002F474),
)


class ReleaseReplay(FinalReplay):
    def code(self, u, pc, size, data):
        if self.phase != "dispatch":
            return super().code(u, pc, size, data)
        r0, r1, r2 = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2))
        if pc == EVENT_SEND:
            assert r0 == CHECKBOX and r2 == 0
            self.events_seen.append([r1, hex(self.read(EVENT_CURRENT))])
            if r1 == VALUE_CHANGED:
                assert 0x800356FC in self.coverage
                outer = self.read(EVENT_CURRENT)
                assert outer != PREVIOUS_EVENT and self.read(outer) == CHECKBOX
                assert u.mem_read(outer + 8, 1)[0] == RELEASED
                assert self.read(outer + 0x14) == PREVIOUS_EVENT
        if pc in (CHECKBOX_EVENT, BASE_EVENT):
            assert r0 == (CHECKBOX_CLASS if pc == CHECKBOX_EVENT else BASE_CLASS)
            assert self.read(r1) == self.read(r1 + 4) == CHECKBOX
            self.class_events.append([hex(pc), u.mem_read(r1 + 8, 1)[0]])
        if pc == INDIRECT:
            assert self.read(r0) == self.read(r0 + 4) == CHECKBOX
            assert self.read(EVENT_CURRENT) == r0 and r1 == FLAG_EVENT
            assert u.mem_read(r0 + 8, 1)[0] == VALUE_CHANGED
            outer = self.read(r0 + 0x14)
            assert u.mem_read(outer + 8, 1)[0] == RELEASED and self.read(outer + 0x14) == PREVIOUS_EVENT
            self.calls.append([hex(pc), hex(r1)])
        if pc == INDIRECT or any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "dispatch" and address == CHECKBOX + 0x20:
            assert size == 2 and u.reg_read(UC_ARM_REG_PC) == 0x8003A394
            self.checkbox_writes.append(value)
            return
        super().write(u, access, address, size, value, data)

    def release(self, initial, checkable, event):
        changes = event == RELEASED and checkable
        state = initial & ~0x20 if event == RELEASED else initial
        selector = 9
        if changes:
            state ^= 1
            selector = 10 if state & 1 else 9
        queue_before = self.prepare_dispatch(9, event, FLAG_EVENT, 0x8000F418 if selector == 10 else 0x8000F4A0)
        self.style, self.cells, self.events_seen, self.class_events, self.checkbox_writes = [], [], [], [], []
        for offset, address in WIDGETS.items():
            self.put(UI + offset, address)
        self.put(CHECKBOX, CHECKBOX_CLASS)
        self.put(CHECKBOX + 0x1C, 0x402 | (8 if checkable else 0))
        self.put(CHECKBOX + 0x20, initial)
        self.put(SOUND_ENABLE, 0)
        self.u.mem_write(MODE, b"\xA5" * 10)
        self.dispatch()
        assert self.read(CHECKBOX + 0x20) == state
        expected_state_writes = []
        if initial & 0x20 and event == RELEASED:
            expected_state_writes.append(initial & ~0x20)
        if changes:
            expected_state_writes.append(state)
        assert self.checkbox_writes == expected_state_writes
        expected_events = [event, VALUE_CHANGED] if changes else [event]
        assert [row[0] for row in self.events_seen] == expected_events
        assert self.class_events == [[hex(address), code] for code in expected_events
                                     for address in (CHECKBOX_EVENT, BASE_EVENT)]
        record = None
        if changes:
            assert self.calls == [[hex(INDIRECT), hex(FLAG_EVENT)]]
            data = bytes((2, 0, 0, 0, selector, 0x19))
            self.check_send(data, 2000)
            assert bytes(self.u.mem_read(MODE + 7, 2)) == data[4:6]
            record = data.hex()
        else:
            assert not any((self.calls, self.timer_stores, self.drained, self.producer_args, self.copies, self.ui_leaves))
            assert bytes(self.u.mem_read(QUEUE, 760)) == queue_before and self.read(TIMER) == 77
            assert bytes(self.u.mem_read(MODE, 10)) == b"\xA5" * 10
        return dict(initial_state=initial, checkable=checkable, input_event=event, state_after=state,
                    state_writes=self.checkbox_writes, dispatched_events=self.events_seen,
                    class_events=self.class_events, application_calls=self.calls, record_prefix=record,
                    drained=self.drained, timer_stores=self.timer_stores, modeled_ui_calls=self.ui_leaves)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, results = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        word = lambda pc: int.from_bytes(raw[pc - BASE:pc - BASE + 4], "little")
        assert word(0x800243B0) == CHECKBOX_CLASS and word(CHECKBOX_CLASS) == BASE_CLASS
        assert word(CHECKBOX_CLASS + 16) == CHECKBOX_EVENT and word(BASE_CLASS + 16) == BASE_EVENT
        assert raw[0x800514CC - BASE:0x800514CC - BASE + 7] == "交流\0".encode()
        replay = ReleaseReplay(raw)
        binding = replay.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)[9]
        cases = [replay.release(*case) for case in product((0, 1, 0x20, 0x21), (False, True), (7, RELEASED))]
        assert sum(case["record_prefix"] is not None for case in cases) == 4
        images[item["version"]] = digest
        results.append(dict(binding=binding, cases=cases, instruction_bytes={
            hex(pc): data for pc, data in sorted(replay.coverage.items())
        }))
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.ac-checkbox-release.v1", images=images, **results[0], limits=[
        "The harness installs the original checkbox class and callback on a seeded object and supplies the outer event code. The class callback executes original state updates and emits its own nested value-change event.",
        "Native registration, dispatch, timer, drain and queue producer execute. The fixture has no styles in the state-update path, and selected downstream UI leaves are modeled.",
        "Physical touch delivery, actual filter/conversion outcomes and native type-6 origin are outside this replay.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 16 AC checkbox cases per factory image, 32 total")


if __name__ == "__main__":
    main()
