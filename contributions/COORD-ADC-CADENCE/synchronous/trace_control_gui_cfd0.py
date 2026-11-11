"""Replay the registered 0x8000cfd0 GUI callback with the secondary channel disabled."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_control_gui_events import (
    EventReplay, MODE, QUEUE, SECOND_BINDINGS, SECOND_LITERALS, SECOND_REGISTER,
    SECOND_STOP, SOUND_ENABLE, TIMER, UI,
)
from trace_scheduler_delay_wake import BASE
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
)

CALLBACK = 0x8000CFD0
SETTING = 0x805AC788
SECONDARY_READY = 0x805AAC40
PREPARE_SECONDARY = 0x8005F254
SECONDARY_RETURN = 0x8005F270
WIDGETS = {offset: 0x10017100 + i * 0x40
           for i, offset in enumerate((0x2C0, 0x2C4, 0x2C8, 0x2F4, 0x300))}
NATIVE_WINDOWS = ((CALLBACK, 0x8000D1A0), (PREPARE_SECONDARY, SECONDARY_RETURN + 4),
                  (0x8005E9B0, 0x8005E9EC))


class CallbackReplay(EventReplay):
    def code(self, u, pc, size, data):
        if self.phase != "dispatch" or self.callback != CALLBACK:
            return super().code(u, pc, size, data)
        r0, r1, r2, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR,
        ))
        if pc in (0x800028FC, 0x8000299C, 0x800339BC, 0x80024CA4, 0x8003A718, 0x80032038):
            expected = {
                0x800028FC: {0x8000CFD8},
                0x8000299C: {0x8000D0EC},
                0x800339BC: {0x8000CFE8},
                0x80024CA4: {0x8000D020, 0x8000D03C, 0x8000D0F4, 0x8000D138, 0x8000D154},
                0x8003A718: {0x8000D034, 0x8000D050, 0x8000D108, 0x8000D14C, 0x8000D168},
                0x80032038: {0x8000D118},
            }
            assert lr in expected[pc], (hex(pc), hex(lr))
            if pc == 0x800339BC:
                assert (r0, r1) == (WIDGETS[0x300], 1)
            if pc == 0x80024CA4:
                assert r0 in (0x4F4F4F, 0xFA7700)
            if pc == 0x8003A718:
                assert r0 in (WIDGETS[0x2C0], WIDGETS[0x2C4], WIDGETS[0x2C8])
                assert r1 in (0x4F4F4F, 0xFA7700) and r2 == 0
            if pc == 0x80032038:
                assert (r0, r1) == (WIDGETS[0x2F4], 0x8000D1B8)
            self.ui_leaves.append([hex(pc), hex(lr)])
            self.return_leaf(u, lr, r0)
            return
        if pc == PREPARE_SECONDARY:
            self.secondary.append([hex(lr), r0, r1, r2])
        if pc == SECONDARY_RETURN:
            self.secondary_returns.append(r0)
        if any(lo <= pc < hi for lo, hi in NATIVE_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "dispatch" and self.callback == CALLBACK and MODE <= address < MODE + 11:
            assert size == 1 and u.reg_read(UC_ARM_REG_PC) in (
                0x8000D014, 0x8000D0A8, 0x8000D0AC, 0x8000D0B4, 0x8000D0CC,
                0x8000D0D0, 0x8000D0D4, 0x8000D0E0, 0x8000D0E4, 0x8000D108, 0x8000D12C,
            )
            return
        super().write(u, access, address, size, value, data)

    def run_callback(self, mode, setting, event):
        use_type5 = mode != 4 and setting == 1
        producer_return = 0x8000D0A4 if use_type5 else 0x8000D0CC
        queue_before = self.prepare_dispatch(8, event, CALLBACK, producer_return)
        self.secondary, self.secondary_returns = [], []
        u = self.u
        u.mem_write(MODE, bytes((mode,)) + b"\xA5" * 10)
        self.put(SETTING, setting)
        self.put(SOUND_ENABLE, 0)
        self.put(SECONDARY_READY, 0)
        for offset, widget in WIDGETS.items():
            self.put(UI + offset, widget)
        self.dispatch()
        after = bytes(u.mem_read(MODE, 11))
        prefix = None
        if event == 1:
            assert self.calls == [["0x8001b030", hex(CALLBACK)]]
            expected = bytes.fromhex("050000002213" if use_type5 else "020000000e19")
            self.check_send(expected, 100)
            next_mode = 3 if mode == 4 else 4
            assert after == bytes((next_mode, 0)) + b"\xA5" * 4 + bytes((2, *expected[4:], 1, 0))
            assert self.secondary == [["0x8000d198", 4, 3, 255] if mode == 4 else ["0x8000d080", 4, 4, 255]]
            assert self.secondary_returns == [0xFFFFFFFF]
            prefix = expected.hex()
        else:
            assert not any((self.calls, self.producer_args, self.copies, self.drained,
                            self.secondary, self.secondary_returns, self.timer_stores, self.ui_leaves))
            assert bytes(u.mem_read(QUEUE, 760)) == queue_before and self.read(TIMER) == 77
            assert after == bytes((mode,)) + b"\xA5" * 10
        return dict(mode=mode, setting=setting, event=event, callback=hex(CALLBACK),
                    indirect_calls=self.calls, mode_bytes_after=after.hex(), record_prefix=prefix,
                    producer_return=hex(producer_return) if prefix else None,
                    producer_args=self.producer_args, drained=self.drained,
                    queue_count=self.read(QUEUE + 0x38), timer_stores=self.timer_stores,
                    secondary_args=self.secondary, secondary_returns=self.secondary_returns,
                    modeled_ui_calls=self.ui_leaves)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, reports = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        replay = CallbackReplay(raw)
        binding = replay.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)[8]
        cases = [replay.run_callback(*inputs) for inputs in product((3, 4), (0, 1, 2), (1, 2))]
        images[item["version"]] = digest
        reports.append(dict(binding=binding, cases=cases, instruction_bytes={
            hex(pc): data for pc, data in sorted(replay.coverage.items())
        }))
    assert images.keys() == {"V3.6", "V3.8"} and reports[0] == reports[1]
    report = dict(schema="ys4470.control-gui-cfd0.v1", images=images, **reports[0], limits=[
        "Original second registration suffix, dispatcher, callback, timer stores, queue drain and producer execute with seeded widgets and an idle scheduler.",
        "Allocator, UI leaves and input event origin are modeled. The secondary command reaches its original disabled guard at 0x805aac40; the sound helper likewise takes its disabled path.",
        "The setting at 0x805ac788 is seeded with 0, 1 and 2. Its origin, the enabled secondary route, later queue consumer behavior, physical timing and native type-6 provenance remain open.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 12 cases per original image, 24 total")


if __name__ == "__main__":
    main()
