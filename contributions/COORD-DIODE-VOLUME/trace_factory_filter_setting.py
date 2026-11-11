"""Identify the factory Filter checkbox and verify the saved cutoff setting."""

import argparse
import hashlib
import json
import struct
import zlib
from itertools import product
from pathlib import Path

from trace_factory_settings_roundtrip import BASE, CRC_LENGTH, FLASH_OFFSET, LOAD, META_FIELDS, RECORD_SIZE, SETTING, UI, WRITE, SettingsReplay
from trace_ac_checkbox_release import BASE_CLASS, BASE_EVENT, CHECKBOX_CLASS, CHECKBOX_EVENT, RELEASED, VALUE_CHANGED, WINDOWS
from trace_control_gui_events import (
    CONTEXT, EVENT_CURRENT, EVENT_INPUT, EVENT_SEND, INDIRECT, OBJECTS,
    PREVIOUS_EVENT, SOUND_ENABLE, EventReplay,
)
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R4

REGISTER, STOP, LITERAL = 0x800548FC, 0x80054910, 0x80054B30
SETTER, STORE, FIELD = 0x8005A534, 0x8005A554, SETTING + 0x14
LABEL_PC, LABEL_LITERAL = 0x8004551C, 0x80045694
LABEL, SOUND, LABEL_WIDGET = 0x80032038, 0x80006E4C, 0x10017B00
CHECKBOX_OFFSET, LABEL_OFFSET = 0x328, 0x324


class FilterReplay(SettingsReplay):
    def __init__(self, raw, flags=0, event=RELEASED):
        super().__init__(raw)
        self.flags, self.input_event = flags, event
        self.filter_register = self.filter_dispatch = False
        self.filter_writes, self.filter_events, self.filter_calls = [], [], []
        self.filter_class_events, self.filter_sound_calls, self.checkbox_writes = [], [], []
        self.label_text = None
        self.repaired_record = None

    def code(self, u, pc, size, data):
        if self.filter_register and pc == 0x800338DC:
            return EventReplay.code(self, u, pc, size, data)
        r0, r1, lr = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
        if self.phase == "label":
            if pc == 0x80045528:
                u.emu_stop()
                return
            if pc == LABEL:
                assert (r0, r1, lr) == (LABEL_WIDGET, LABEL_LITERAL, 0x80045528)
                self.label_text = bytes(u.mem_read(r1, 7))
                self.return_leaf(u, lr, 0)
                return
            assert LABEL_PC <= pc < 0x80045528
        elif self.phase == "load" and pc == WRITE:
            assert (r0, r1, u.reg_read(UC_ARM_REG_R2), u.reg_read(UC_ARM_REG_R3), lr) == (
                0, SETTING, FLASH_OFFSET, RECORD_SIZE, 0x800081C8,
            )
            self.repaired_record = bytes(u.mem_read(r1, RECORD_SIZE))
            self.return_leaf(u, lr, 0)
            return
        elif self.phase == "load" and pc == 0x8005A8A8 and lr == 0x80008134:
            assert r0 == 0x80008234
            self.logs.append(["default", hex(r0)])
            self.return_leaf(u, lr, 0)
            return
        elif self.filter_dispatch:
            if pc == EVENT_SEND:
                assert r0 == OBJECTS and u.reg_read(UC_ARM_REG_R2) == 0
                self.filter_events.append(r1)
            if pc in (CHECKBOX_EVENT, BASE_EVENT):
                assert r0 == (CHECKBOX_CLASS if pc == CHECKBOX_EVENT else BASE_CLASS)
                assert self.read(r1) == self.read(r1 + 4) == OBJECTS
                self.filter_class_events.append([hex(pc), u.mem_read(r1 + 8, 1)[0]])
            if pc == INDIRECT:
                assert r1 == SETTER and self.read(EVENT_CURRENT) == r0
                assert self.read(r0) == self.read(r0 + 4) == OBJECTS
                assert u.mem_read(r0 + 8, 1)[0] == VALUE_CHANGED
                assert self.read(r0 + 0xC) == self.read(r0 + 0x10) == 0
                assert self.read(self.read(r0 + 0x14)) == OBJECTS
                assert u.mem_read(self.read(r0 + 0x14) + 8, 1)[0] == RELEASED
                self.filter_calls.append([hex(pc), hex(r1)])
            if pc == SOUND:
                assert (r0, r1, lr) == (5, 1, 0x8001B034) and self.read(SOUND_ENABLE) == 0
                self.filter_sound_calls.append([hex(lr), r0, r1])
        if self.phase == "label" or self.filter_register and REGISTER <= pc < STOP or self.filter_dispatch and (
            pc == INDIRECT or SETTER <= pc <= 0x8005A564 or any(lo <= pc < hi for lo, hi in WINDOWS)
        ):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.filter_dispatch and address in (FIELD, OBJECTS + 0x20):
            pc = u.reg_read(UC_ARM_REG_PC)
            if address == FIELD:
                assert (pc, size) == (STORE, 4)
                self.filter_writes.append(value)
            else:
                assert (pc, size) == (0x8003A394, 2)
                self.checkbox_writes.append(value)
            return
        super().write(u, access, address, size, value, data)

    def label(self):
        self.put(CONTEXT + LABEL_OFFSET, LABEL_WIDGET)
        self.u.reg_write(UC_ARM_REG_R4, CONTEXT)
        self.phase = "label"
        try:
            self.invoke(LABEL_PC, stop=0x80045528)
        finally:
            self.phase = None
        assert self.label_text == b"Filter\0"

    def before_save_event(self):
        self.label()
        self.filter_register = True
        try:
            self.binding, = self.register(REGISTER, STOP, LITERAL, ((CHECKBOX_OFFSET, SETTER, VALUE_CHANGED),))
        finally:
            self.filter_register = False
        self.put(UI + CHECKBOX_OFFSET, OBJECTS)
        self.put(OBJECTS, CHECKBOX_CLASS)
        self.put(OBJECTS + 0x1C, 0x40A)
        self.put(OBJECTS + 0x20, self.flags)
        self.put(EVENT_CURRENT, PREVIOUS_EVENT)
        self.put(EVENT_INPUT, 0)
        self.put(FIELD, self.flags & 1)
        self.u.reg_write(UC_ARM_REG_R2, 0)
        self.phase = "dispatch"
        self.filter_dispatch = True
        self.callback = SETTER
        try:
            assert self.invoke(EVENT_SEND, OBJECTS, self.input_event) == 1
        finally:
            self.filter_dispatch = False
            self.phase = None
        changed = self.input_event == RELEASED
        expected = (self.flags & 1) ^ int(changed)
        assert self.read(EVENT_CURRENT) == PREVIOUS_EVENT
        assert self.read(FIELD) == expected
        assert self.filter_events == ([RELEASED, VALUE_CHANGED] if changed else [self.input_event])
        assert self.filter_class_events == [[hex(pc), code] for code in self.filter_events
                                           for pc in (CHECKBOX_EVENT, BASE_EVENT)]
        assert self.checkbox_writes == ([expected] if changed else [])
        assert self.filter_calls == ([[hex(INDIRECT), hex(SETTER)]] if changed else [])
        assert self.filter_writes == ([expected] if changed else [])
        assert self.filter_sound_calls == ([["0x8001b034", 5, 1]] if changed else [])
        assert not self.saved
        # Restore the separate Save button's descriptor after the isolated
        # checkbox registration reused the small allocation fixture.
        self.install_callbacks()

    def case(self):
        result = self.roundtrip(1, 1)
        expected = (self.flags & 1) ^ int(self.input_event == RELEASED)
        assert self.read(FIELD) == expected
        assert int.from_bytes(self.storage_record[0x14:0x18], "little") == expected
        return dict(flags=self.flags, event=self.input_event, checkbox_writes=self.checkbox_writes,
                    application_calls=self.filter_calls, emitted_events=self.filter_events,
                    field_writes=self.filter_writes, saved_and_loaded_word=expected, record_crc32=result["crc32"])

    def invalid_default(self):
        self.storage_record = bytes(RECORD_SIZE)
        self.u.mem_write(SETTING, b"\xCC" * RECORD_SIZE)
        metadata = int.from_bytes(self.raw[0x8000827C - BASE:0x80008280 - BASE], "little")
        self.u.mem_write(metadata + 8, struct.pack("<3H", *META_FIELDS))
        self.phase = "load"
        try:
            self.invoke(LOAD)
        finally:
            self.phase = None
        assert self.read(FIELD) == 1
        assert ["0x80008160", 0x14, 4] in self.load_writes
        assert self.repaired_record[0x14:0x18] == b"\x01\x00\x00\x00"
        crc = zlib.crc32(self.repaired_record[:CRC_LENGTH])
        assert self.repaired_record[CRC_LENGTH:] == crc.to_bytes(4, "little")
        return dict(invalid_record_word=0, initialized_word=1, default_write_crc32=hex(crc),
                    logs=self.logs, stores=self.load_writes)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        cases, coverage = [], {}
        for flags, event in product((0, 1), (7, RELEASED)):
            replay = FilterReplay(raw, flags, event)
            cases.append(replay.case())
            coverage.update(replay.coverage)
        invalid = FilterReplay(raw)
        default = invalid.invalid_default()
        coverage.update(invalid.coverage)
        observations.append(dict(binding=replay.binding, english_label=replay.label_text[:-1].decode("ascii"),
                                 event_cases=cases, invalid_record_default=default, instruction_bytes={
                                     hex(pc): encoded for pc, encoded in sorted(coverage.items())
                                 }))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.factory-filter-setting.v1", images=images, **observations[0], limits=[
        "The label assignment and checkbox registration run as original bounded blocks with seeded GUI objects.",
        "The checkbox class emits its native nested event. Original callback, CRC save and valid/invalid loaders execute.",
        "The label sink, object allocator and flash transfers are modeled. No physical touch, flash or ADC conversion is exercised.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 4 factory Filter event/persistence cases and 1 invalid-record default per image, 10 total")


if __name__ == "__main__":
    main()
