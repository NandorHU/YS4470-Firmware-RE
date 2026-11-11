"""Replay the registered Diode/Buzzer callback through the secondary command sender."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_control_gui_cfd0 import CallbackReplay, SECONDARY_READY, SETTING
from trace_control_gui_events import (
    SECOND_BINDINGS, SECOND_LITERALS, SECOND_REGISTER, SECOND_STOP, SOUND_ENABLE, UI,
)
from trace_scheduler_delay_wake import BASE, RET, STACK
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

WRITER, WIDGET = 0x8005A3BC, 0x10017300
GUARD_WORDS, BUSY = (0x805AAC48, 0x805AAC4C), 0x805AAC70
ACK = 0x8005E750
SUBMIT, TRANSPORT = 0x80060CCC, 0x8005FC08
STATES = ("idle_accept", "idle_reject", "busy", "missing_second_word")
WRITER_WINDOWS = ((WRITER, 0x8005A3F0), (0x8003752C, 0x8003753C),
                  (ACK, 0x8005E778), (0x80006E4C, 0x80006E60))
SENDER_WINDOWS = ((0x8005F274, 0x8005F2FC), (SUBMIT, 0x80060D84), (0x800009C4, 0x80000B28))


def in_windows(pc, windows):
    return any(start <= pc < end for start, end in windows)


class SecondaryReplay(CallbackReplay):
    def code(self, u, pc, size, data):
        r0, r1, r2, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR,
        ))
        if self.phase == "setup" and pc != RET:
            assert in_windows(pc, WRITER_WINDOWS), hex(pc)
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        if self.phase == "dispatch" and pc == TRANSPORT:
            assert (r0, r2, lr) == (1, 64, 0x80060D74)
            assert STACK - 0x400 <= r1 <= STACK - 64
            assert u.mem_read(BUSY, 1)[0] == 1
            self.transport.append(bytes(u.mem_read(r1, r2)).hex())
            self.return_leaf(u, lr, 0 if self.state == "idle_accept" else 1)
            return
        if self.phase == "dispatch" and in_windows(pc, SENDER_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            if pc == SUBMIT:
                assert r1 == 64 and lr == 0x8005F2F0
                self.submit.append(bytes(u.mem_read(r0, r1)).hex())
            if pc == 0x8005F2F8:
                self.secondary_returns.append(r0)
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if self.phase == "setup" and address in (*GUARD_WORDS, SETTING):
            assert size == 4 and (pc, address) in (
                (0x8005E760, GUARD_WORDS[0]), (0x8005E76C, GUARD_WORDS[1]), (0x8005A3DC, SETTING),
            )
            self.setup_stores.append([hex(pc), hex(address), value])
            return
        if self.phase == "dispatch" and address == BUSY:
            assert size == 1 and (pc, value) in ((0x80060D48, 1), (0x80060D78, 0))
            self.busy_stores.append([hex(pc), value])
            return
        super().write(u, access, address, size, value, data)

    def prepare_setting(self, setting):
        assert self.read(SETTING) == setting

    def prepare_secondary(self):
        self.put(SECONDARY_READY, 1)
        if self.state == "missing_second_word":
            self.put(GUARD_WORDS[1], 0)
        self.put(BUSY, int(self.state == "busy"))
        self.submit, self.transport, self.busy_stores = [], [], []

    def check_secondary(self):
        if self.state == "missing_second_word":
            assert self.secondary_returns == [0xFFFFFFFF]
            assert not any((self.submit, self.transport, self.busy_stores))
            assert self.read(BUSY) == 0
            return
        assert self.secondary_returns == [0]
        _, command, argument, value = self.secondary[0]
        frame = bytes((0, 0x10, 0x40, 2, command, argument, value, 255)) + bytes(56)
        assert self.submit == [frame.hex()]
        if self.state == "busy":
            assert not self.transport and not self.busy_stores and self.read(BUSY) == 1
        else:
            assert self.transport == self.submit
            accepted = self.state == "idle_accept"
            expected = [["0x80060d48", 1]] if accepted else [["0x80060d48", 1], ["0x80060d78", 0]]
            assert self.busy_stores == expected and self.read(BUSY) == int(accepted)

    def run_enabled(self, mode, widget_flags, state):
        self.state = state
        self.setup_stores = []
        self.put(SETTING, 0xA5A5A5A5)
        self.put(SOUND_ENABLE, 0)
        self.put(UI + 0x31C, WIDGET)
        self.u.mem_write(WIDGET + 0x20, widget_flags.to_bytes(2, "little"))
        for address in GUARD_WORDS:
            self.put(address, 0)
        self.phase = "setup"
        try:
            self.invoke(WRITER)
            self.invoke(ACK, 0, 0)
        finally:
            self.phase = None
        setting = widget_flags & 1
        assert self.read(SETTING) == setting
        assert all(self.read(address) == 1 for address in GUARD_WORDS)
        assert self.setup_stores == [
            ["0x8005a3dc", hex(SETTING), setting],
            ["0x8005e760", hex(GUARD_WORDS[0]), 1],
            ["0x8005e76c", hex(GUARD_WORDS[1]), 1],
        ]
        result = self.run_callback(mode, setting, 1)
        return dict(**result, state=state, widget_flags=widget_flags, setup_stores=self.setup_stores,
                    submit_frames=self.submit, transport_frames=self.transport,
                    busy_stores=self.busy_stores, busy_after=self.read(BUSY))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, runs = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        replay = SecondaryReplay(raw)
        binding = replay.register(SECOND_REGISTER, SECOND_STOP, SECOND_LITERALS, SECOND_BINDINGS)[8]
        cases = [replay.run_enabled(*inputs) for inputs in product((3, 4), (0, 1, 2), STATES)]
        images[item["version"]] = digest
        runs.append(dict(binding=binding, cases=cases, instruction_bytes={
            hex(pc): data for pc, data in sorted(replay.coverage.items())
        }))
    assert images.keys() == {"V3.6", "V3.8"} and runs[0] == runs[1]
    report = dict(schema="ys4470.control-gui-cfd0-secondary.v1", images=images, **runs[0], limits=[
        "The original writer reads bit 0 of the halfword at widget +0x20 via 0x8003752c. The harness seeds the widget and invokes this writer directly before dispatching the registered callback.",
        "The harness seeds the ready byte and calls the original null-input path of 0x8005e750 to populate the guard words. The missing-word case clears one word after setup.",
        "The original callback, frame builder, sender busy gate and copy execute. The hardware-facing 0x8005fc08 leaf is modeled with return 0 or 1. Physical transport, acknowledgement timing and full setting provenance are outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 24 cases per original image, 48 total")


if __name__ == "__main__":
    main()
