"""Replay the factory settings UI save and load using synthetic in-memory storage."""

import argparse
import hashlib
import json
import struct
import sys
import zlib
from itertools import product
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "COORD-ADC-CADENCE" / "synchronous"))
from trace_control_gui_events import (
    CONTEXT, DESCRIPTORS, EVENT_CURRENT, EVENT_INPUT, EVENT_SEND, EXTRA_COUNT, EXTRAS,
    INDIRECT, OBJECTS, PREVIOUS_EVENT, SOUND_ENABLE, UI, EventReplay,
)
from trace_scheduler_delay_wake import BASE, RET, STACK
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP,
)

REGISTER, OTHER_CALLBACK, SAVE_CALLBACK = 0x8001B2D0, 0x8004542C, 0x800453C8
SAVE, LOAD, WRITE, READ = 0x800082C0, 0x80008098, 0x80006374, 0x8005A6BC
SETTER, SETTING, FAST_CONT = 0x8005A3BC, 0x805AC770, 0x805AC788
RECORD_SIZE, CRC_LENGTH, FLASH_OFFSET = 72, 68, 0xF00000
OBJECT, CHECKBOX = OBJECTS + 0x40, 0x10017500
META_FIELDS = (0x1122, 0x3344, 0x5566)
WINDOWS = (
    (REGISTER, 0x8001B304), (SAVE_CALLBACK, 0x80045424), (SAVE, 0x80008338),
    (SETTER, 0x8005A3F0), (0x8003752C, 0x8003753C), (0x80006E4C, 0x80006E60),
    (0x8002C688, 0x8002C694), (LOAD, 0x80008214), (0x800009C4, 0x80000B0C),
)


class SettingsReplay(EventReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.raw = raw
        self.storage_record = None
        self.saved, self.loaded, self.transitions, self.logs = [], [], [], []
        self.checksum_writes, self.setting_writes, self.load_writes = [], [], []

    def code(self, u, pc, size, data):
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc == 0x800338DC and self.phase == "register":
            assert r3 == CONTEXT and r2 == 0
            self.registrations.append([hex(lr), hex(r0), hex(r1), r2, hex(r3)])
        elif pc == INDIRECT and self.phase == "dispatch":
            assert self.read(EVENT_CURRENT) == r0 and self.read(r0) == self.read(r0 + 4) == OBJECT
            assert u.mem_read(r0 + 8, 1)[0] == self.event and self.read(r0 + 0xC) == CONTEXT
            assert self.read(r0 + 0x10) == 0 and self.read(r0 + 0x14) == PREVIOUS_EVENT
            assert r1 == SAVE_CALLBACK
            self.calls.append([hex(pc), hex(r1)])
        elif pc == 0x8005CA1C and self.phase == "dispatch":
            assert lr == 0x80045418 and (r0, r1, r2, r3) == (UI, UI + 0xC, 0, UI + 0x36C)
            stack = struct.unpack("<6I", u.mem_read(u.reg_read(UC_ARM_REG_SP), 24))
            assert stack == (0x80045EA8, 0, 200, 200, 1, 1)
            self.transitions.append([hex(lr), list(stack)])
            self.return_leaf(u, lr, 0)
            return
        elif pc == WRITE:
            assert self.phase == "dispatch" and lr == 0x8000832C
            assert (r0, r1, r2, r3) == (0, SETTING, FLASH_OFFSET, RECORD_SIZE)
            self.storage_record = bytes(u.mem_read(r1, r3))
            self.saved.append([hex(r2), r3, hashlib.sha256(self.storage_record).hexdigest()])
            self.return_leaf(u, lr, 0)
            return
        elif pc == READ:
            assert self.phase == "load" and lr == 0x800080B4
            assert (r0, r1, r3) == (0, FLASH_OFFSET, RECORD_SIZE)
            assert STACK - 0x100 <= r2 <= STACK - RECORD_SIZE
            assert self.storage_record is not None
            u.mem_write(r2, self.storage_record)
            self.loaded.append([hex(r1), r3, hashlib.sha256(self.storage_record).hexdigest()])
            self.return_leaf(u, lr, 0)
            return
        elif pc == 0x8005A8A8 and self.phase in ("dispatch", "load"):
            assert (self.phase == "dispatch" and r0 == 0x80008340) or (
                self.phase == "load" and lr == 0x800081D0
            )
            self.logs.append([self.phase, hex(r0)])
            self.return_leaf(u, lr, 0)
            return
        if pc == 0x80006E4C and self.phase == "setter":
            assert (r0, r1) == (5, 1) and self.read(SOUND_ENABLE) == 0
        if pc in (0x800338DC, INDIRECT) and self.phase in ("register", "dispatch") or any(
            lo <= pc < hi for lo, hi in WINDOWS
        ):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if SETTING <= address and address + size <= SETTING + RECORD_SIZE:
            pc = u.reg_read(UC_ARM_REG_PC)
            if self.phase == "setter":
                assert (pc, address, size) == (0x8005A3DC, FAST_CONT, 4)
                self.setting_writes.append([hex(address), value])
            elif self.phase == "dispatch":
                assert (pc, address, size) == (0x80008318, SETTING + CRC_LENGTH, 4)
                self.checksum_writes.append(value)
            else:
                assert self.phase == "load"
                self.load_writes.append([hex(pc), address - SETTING, size])
            return
        super().write(u, access, address, size, value, data)

    def install_callbacks(self):
        u = self.u
        self.put(EXTRA_COUNT, 0)
        u.mem_write(OBJECTS, bytes(0x80))
        u.mem_write(EXTRAS, b"\xA5" * 0x80)
        u.mem_write(DESCRIPTORS, b"\xA5" * 0x20)
        self.put(CONTEXT + 0x384, OBJECTS)
        self.put(CONTEXT + 0x394, OBJECT)
        self.registrations = []
        self.registration_stop = RET
        self.phase = "register"
        try:
            self.invoke(REGISTER, CONTEXT)
        finally:
            self.phase = None
        assert self.read(EXTRA_COUNT) == 2
        assert self.registrations == [
            ["0x8001b2ec", hex(OBJECTS), hex(OTHER_CALLBACK), 0, hex(CONTEXT)],
            [hex(RET), hex(OBJECT), hex(SAVE_CALLBACK), 0, hex(CONTEXT)],
        ]
        descriptor = DESCRIPTORS + 0x10
        assert self.read(OBJECT + 8) == EXTRAS + 0x40
        assert self.read(EXTRAS + 0x4C) == descriptor
        assert self.read(descriptor) == SAVE_CALLBACK and self.read(descriptor + 4) == CONTEXT
        assert u.mem_read(descriptor + 8, 1)[0] == 0

    def save_event(self, flags, event):
        self.install_callbacks()
        self.put(UI + 0x31C, CHECKBOX)
        self.u.mem_write(CHECKBOX + 0x20, flags.to_bytes(2, "little"))
        self.u.mem_write(SETTING, bytes((i * 13 + flags) & 0xFF for i in range(RECORD_SIZE)))
        self.put(SOUND_ENABLE, 0)
        self.phase = "setter"
        try:
            self.invoke(SETTER)
        finally:
            self.phase = None
        normalized = flags & 1
        assert self.read(FAST_CONT) == normalized and self.setting_writes == [[hex(FAST_CONT), normalized]]
        assert not self.saved
        self.before_save_event()
        old = bytes(self.u.mem_read(SETTING, RECORD_SIZE))

        self.object, self.event, self.callback = OBJECT, event, SAVE_CALLBACK
        self.calls = []
        self.put(EVENT_CURRENT, PREVIOUS_EVENT)
        self.put(EVENT_INPUT, 0)
        self.phase = "dispatch"
        self.u.reg_write(UC_ARM_REG_R2, 0)
        try:
            assert self.invoke(EVENT_SEND, OBJECT, event) == 1
        finally:
            self.phase = None
        assert self.read(EVENT_CURRENT) == PREVIOUS_EVENT
        assert self.calls == [[hex(INDIRECT), hex(SAVE_CALLBACK)]]
        return normalized, old

    def before_save_event(self):
        pass

    def roundtrip(self, flags, event):
        normalized, old = self.save_event(flags, event)
        if event != 1:
            assert not any((self.saved, self.loaded, self.transitions, self.checksum_writes, self.logs))
            assert bytes(self.u.mem_read(SETTING, RECORD_SIZE)) == old
            return dict(widget_flags=flags, event=event, settings_word=normalized, saved=False)

        crc = zlib.crc32(old[:CRC_LENGTH])
        assert self.storage_record == old[:CRC_LENGTH] + crc.to_bytes(4, "little")
        assert self.checksum_writes == [crc] and len(self.saved) == len(self.transitions) == 1
        self.u.mem_write(SETTING, b"\xCC" * RECORD_SIZE)
        metadata = int.from_bytes(self.raw[0x8000827C - BASE:0x80008280 - BASE], "little")
        self.u.mem_write(metadata + 8, struct.pack("<3H", *META_FIELDS))
        self.phase = "load"
        try:
            self.invoke(LOAD)
        finally:
            self.phase = None
        expected = bytearray(self.storage_record)
        expected[0x1C:0x2C] = self.raw[0x80008260 - BASE:0x80008270 - BASE]
        expected[0x2D:0x36] = self.raw[0x80008270 - BASE:0x80008279 - BASE]
        expected[0x3E:0x44] = struct.pack("<3H", *META_FIELDS)
        assert bytes(self.u.mem_read(SETTING, RECORD_SIZE)) == bytes(expected)
        assert self.read(FAST_CONT) == normalized and self.saved == self.loaded
        assert len(self.logs) == 2
        return dict(widget_flags=flags, event=event, settings_word=normalized, saved=True,
                    crc32=hex(crc), storage_write=self.saved[0], storage_read=self.loaded[0],
                    transition_arguments=self.transitions[0], load_writes=self.load_writes,
                    metadata_overwrites=[[0x1C, 0x2C], [0x2D, 0x36], [0x3E, 0x44]])


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
        coverage, cases = {}, []
        for flags, event in product((0, 1, 2, 3), (1, 7, 0x1C)):
            replay = SettingsReplay(raw)
            cases.append(replay.roundtrip(flags, event))
            coverage.update(replay.coverage)
        images[item["version"]] = digest
        results.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.factory-settings-ui-roundtrip.v1", images=images, **results[0], limits=[
        "Original settings callback registration, indirect event dispatch, Fast CONT setter, CRC calculation and valid-record copy execute.",
        "The storage read and write boundaries use a synthetic in-memory 72-byte record. GUI transition and log calls are modeled. No private settings or flash dump is used.",
        "The load overwrites known metadata spans after CRC validation. The test does not establish an unused setting slot or physical flash behavior.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 12 factory settings event cases per image, 24 total")


if __name__ == "__main__":
    main()
