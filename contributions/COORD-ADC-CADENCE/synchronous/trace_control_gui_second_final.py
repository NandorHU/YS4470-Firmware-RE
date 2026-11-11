"""Replay the final three registered callbacks in the original second GUI block."""

import argparse
import hashlib
import json
from pathlib import Path

from trace_control_gui_events import (
    EventReplay, INDIRECT, MODE, PREVIOUS, QUEUE, RECORD_SIZE, SECOND_BINDINGS,
    SECOND_LITERALS, SECOND_REGISTER, SECOND_STOP, SOUND_ENABLE, TIMER, UI,
)
from trace_control_gui_second_group import OBJECTS_BY_OFFSET
from trace_scheduler_delay_wake import BASE
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
)

RESET, TOGGLE, FLAG_EVENT = 0x8000CFB8, 0x8000D43C, 0x8000F3B4
WIDGETS = {**OBJECTS_BY_OFFSET, 0x280: 0x10017500, 0x2F0: 0x10017540,
           0x2F8: 0x10017580, 0x304: 0x100175C0, 0x314: 0x10017600}
NATIVE = ((RESET, 0x8000CFD0), (TOGGLE, 0x8000D528), (FLAG_EVENT, 0x8000F544),
          (0x8001EB80, 0x8001EC1C), (0x8003752C, 0x8003753C))
STYLE_CALLS = {
    0x80034A50: {0x8000D484, 0x8000D490, 0x8000D49C, 0x8000D518, 0x8000D524},
    0x800339BC: {0x8000D4A8, 0x8000D4B4, 0x8000D4F4, 0x8000D500, 0x8000D50C},
    0x80033A5C: {0x8000F42C, 0x8000F438, 0x8000F444, 0x8000F450,
                 0x8000F45C, 0x8000F468, 0x8000F474, 0x8000F480},
    0x80034B04: {0x8000F4B4, 0x8000F4C0, 0x8000F4CC, 0x8000F4D8,
                 0x8000F4E4, 0x8000F4F0, 0x8000F4FC},
}
STATE_WRITES = {0x8001EB94: 4, 0x8001EBD8: 5, 0x8000D474: 3, 0x8000D4E4: 3,
                0x8000F41C: 7, 0x8000F4A4: 7, 0x8000F528: 8, 0x8000F530: 1}
FIXTURES = ((RESET, 0), (TOGGLE, 0), (TOGGLE, 1), (FLAG_EVENT, 0), (FLAG_EVENT, 1), (FLAG_EVENT, 2))


class FinalReplay(EventReplay):
    def code(self, u, pc, size, data):
        if self.phase != "dispatch":
            return super().code(u, pc, size, data)
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc == 0x8003EB48:
            assert lr in (0x8001EBBC, 0x8001EC00) and r3 == 0x8005D264
            assert r0 == WIDGETS[0x280 if lr == 0x8001EBBC else 0x314]
            self.cells.append([hex(r0), r1, r2])
        elif pc in STYLE_CALLS:
            assert lr in STYLE_CALLS[pc] and r0 in WIDGETS.values()
            assert r1 == (0x80 if self.callback == FLAG_EVENT else 1)
            self.style.append([hex(pc), hex(r0), r1])
        elif pc == 0x80024CA4:
            assert lr in (0x8000D45C, 0x8000D4CC, 0x8000F510)
            assert r0 in (0x2A2A2A, 0xFA7700)
        elif pc == 0x8003A718:
            assert lr in (0x8000D470, 0x8000D4E0, 0x8000F524)
            assert r0 == WIDGETS[0x2C8 if self.callback == FLAG_EVENT else 0x2D8]
            assert r1 in (0x2A2A2A, 0xFA7700) and r2 == 0
        elif pc == 0x8005A8A8:
            assert self.callback == FLAG_EVENT and lr in (0x8000F3C0, 0x8000F408, 0x8000F490, 0x8000F504)
        elif pc == 0x8000299C:
            assert self.callback == FLAG_EVENT and lr == 0x8000F508
        else:
            if any(lo <= pc < hi for lo, hi in NATIVE):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
                return
            return super().code(u, pc, size, data)
        self.ui_leaves.append([hex(pc), hex(lr)])
        self.return_leaf(u, lr, r0)

    def write(self, u, access, address, size, value, data):
        if self.phase == "dispatch" and MODE <= address < MODE + 10:
            assert size == 1 and STATE_WRITES.get(u.reg_read(UC_ARM_REG_PC)) == address - MODE
            return
        super().write(u, access, address, size, value, data)

    def run(self, callback, flags, matching_event):
        idx = next(i for i, (_, address, _) in enumerate(SECOND_BINDINGS) if address == callback)
        event_filter = SECOND_BINDINGS[idx][2]
        event = event_filter if matching_event else 2 if event_filter == 1 else 1
        active_bit = flags & 1
        producer_return = 0x8000F418 if active_bit else 0x8000F4A0
        queue_before = self.prepare_dispatch(idx, event, callback, producer_return)
        self.style, self.cells = [], []
        before = bytearray(b"\xA5" * 10)
        before[3] = flags
        self.u.mem_write(MODE, bytes(before))
        self.put(SOUND_ENABLE, 0)
        for offset, address in WIDGETS.items():
            self.put(UI + offset, address)
        self.u.mem_write(WIDGETS[0x300] + 0x20, flags.to_bytes(2, "little"))
        self.dispatch()
        prefix = None
        if matching_event:
            assert self.calls == [[hex(INDIRECT), hex(callback)]]
            if callback == RESET:
                before[4] = before[5] = 0
                assert self.cells == [[hex(WIDGETS[off]), row, col]
                                      for off, count in ((0x280, 4), (0x314, 10))
                                      for row in range(count) for col in range(6)]
                assert not self.style
            elif callback == TOGGLE:
                before[3] = 0 if flags else 1
                names = (0x80034A50, 0x800339BC) if flags else (0x800339BC, 0x80034A50)
                assert self.style == [[hex(names[i >= 3]), hex(WIDGETS[off]), 1]
                                      for i, off in enumerate((0x2F4, 0x2F8, 0x304, 0x280, 0x2F0))]
                assert not self.cells
            else:
                selector = 10 if active_bit else 9
                before[1], before[7], before[8] = 0, selector, 0x19
                record = bytes((2, 0, 0, 0, selector, 0x19))
                self.check_send(record, 2000)
                assert self.drained == [*PREVIOUS, None]
                prefix = record.hex()
                offsets = (0x2A0, 0x2A8, 0x2B0, 0x2B8, 0x2A8, 0x2D0, 0x2C8, 0x2E8) if active_bit else (
                    0x2A0, 0x2B0, 0x2B8, 0x2A8, 0x2D0, 0x2C8, 0x2E8)
                assert self.style == [[hex(0x80033A5C if active_bit else 0x80034B04), hex(WIDGETS[off]), 0x80]
                                      for off in offsets]
        else:
            assert not any((self.calls, self.ui_leaves, self.style, self.cells))
        if not matching_event or callback != FLAG_EVENT:
            assert not any((self.timer_stores, self.drained, self.producer_args, self.copies))
            assert bytes(self.u.mem_read(QUEUE, 760)) == queue_before and self.read(TIMER) == 77
        assert bytes(self.u.mem_read(MODE, 10)) == bytes(before)
        return dict(callback=hex(callback), initial_flags=flags, event=event, matching_event=matching_event,
                    mode_after=bytes(before).hex(), record_prefix=prefix, cells=self.cells, style=self.style,
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
        replay = FinalReplay(raw)
        bindings = replay.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)
        cases = [replay.run(*fixture, matched) for fixture in FIXTURES for matched in (True, False)]
        images[item["version"]] = digest
        results.append(dict(bindings=bindings, cases=cases, instruction_bytes={
            hex(pc): data for pc, data in sorted(replay.coverage.items())
        }))
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.control-gui-second-final.v1", images=images, **results[0], limits=[
        "Original second registration block, dispatcher, three callbacks and applicable native queue paths execute in a seeded idle scheduler.",
        "Object allocation, grid-cell and style calls, logging and selected UI leaves are modeled. The sound helper takes its original disabled path.",
        "The 0x8000f3b4 handler uses seeded widget flags and event 0x1c. Physical event origin, full GUI state coverage and downstream timing remain open.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 12 registered GUI cases per factory image, 24 total")


if __name__ == "__main__":
    main()
