"""Verify Fast CONT UI binding, default and CRC-protected persistence.

Executes bounded original ARM926 code; every storage, GUI setter and sound
API is a stop boundary. The optional device dump is opened read-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import struct
import zlib
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import UC_PROT_READ, UC_PROT_EXEC
from unicorn.arm_const import (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                               UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R5,
                               UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_SP,
                               UC_ARM_REG_PC)

from emulate_state5_parser import BASE, EXPECTED_INPUTS
from trace_measurement_event_sources import EventMachine, GUI, SETTINGS, STACK, TOP

FLAG, FLASH_OFFSET, RECORD_SIZE = SETTINGS + 0x18, 0xF00000, 0x48
CRC_BYTES, WRITE_BOUNDARY, PRINT_BOUNDARY = 0x44, 0x80006374, 0x8005A8A8
COPY_BOUNDARY, SOUND_BOUNDARY, WIDGET = 0x80000A98, 0x80006E4C, STACK + 0x800


def read_u32(mu, address):
    return struct.unpack("<I", mu.mem_read(address, 4))[0]


class SettingsMachine(EventMachine):
    def __init__(self, image):
        super().__init__(image)
        for page in (0x80008000, 0x8005A000, 0x80037000, 0x80054000,
                     0x80034000, 0x80000000):
            self.mu.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
            self.mu.mem_write(page, image[page - BASE:page - BASE + 0x1000])

    def on_write(self, mu, access, address, size, value, user_data):
        if not (STACK <= address and address + size <= STACK + 0x1000
                or SETTINGS <= address and address + size <= SETTINGS + RECORD_SIZE):
            raise RuntimeError(f"unexpected guest write {address:#x}/{size}")
        self.writes.append((address, size))

    def run(self, start, stops, allowed):
        self.stops, self.allowed = set(stops), allowed
        self.mu.emu_start(start, 0x80006FFC, count=10000)
        pc = self.mu.reg_read(UC_ARM_REG_PC)
        if pc not in self.stops:
            raise RuntimeError("experiment exceeded its instruction bound")
        return pc

    def binding(self):
        result = {}
        for language, start in (("english", 0x8004557C), ("chinese", 0x80045630)):
            self.reset()
            self.mu.reg_write(UC_ARM_REG_SP, STACK + 0xD00)
            self.mu.reg_write(UC_ARM_REG_R4, GUI)
            self.mu.mem_write(GUI + 0x320, struct.pack("<I", WIDGET + 0x80))
            self.run(start, (0x80032038,), [(start, start + 16)])
            pointer = self.mu.reg_read(UC_ARM_REG_R1)
            text = self.image[pointer - BASE:].split(b"\0", 1)[0].decode("utf-8")
            expected = "Fast CONT" if language == "english" else "快速通断"
            if text != expected or self.mu.reg_read(UC_ARM_REG_R0) != WIDGET + 0x80:
                raise AssertionError("label binding mismatch")
            result[language] = {"text": text, "address": hex(pointer), "label_offset": "0x320"}
        self.reset()
        self.mu.reg_write(UC_ARM_REG_R4, GUI)
        self.mu.mem_write(GUI + 0x31C, struct.pack("<I", WIDGET))
        self.run(0x80054910, (0x800338DC,), [(0x80054910, 0x80054924)])
        observed = [self.mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if observed != [WIDGET, 0x8005A3BC, 0x1C, 0]:
            raise AssertionError("checkbox callback registration mismatch")
        result["checkbox_registration"] = {"object_offset": "0x31c", "callback": "0x8005a3bc", "event_argument": 28}
        return result

    def callback(self, widget_state):
        self.reset()
        self.mu.mem_write(GUI + 0x31C, struct.pack("<I", WIDGET))
        self.mu.mem_write(WIDGET + 0x20, struct.pack("<H", widget_state))
        self.mu.mem_write(FLAG, struct.pack("<I", 0xDEADBEEF))
        self.run(0x8005A3BC, (SOUND_BOUNDARY,),
                 [(0x8005A3BC, 0x8005A3F0), (0x8003752C, 0x8003753C)])
        value = read_u32(self.mu, FLAG)
        if value != int(bool(widget_state & 1)):
            raise AssertionError("checkbox normalization mismatch")
        globals_written = [w for w in self.writes if w[0] >= SETTINGS]
        if globals_written != [(FLAG, 4)] or self.mu.reg_read(UC_ARM_REG_SP) != TOP:
            raise AssertionError("callback state/stack contract mismatch")
        if [self.mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)] != [5, 1]:
            raise AssertionError("sound notification boundary arguments changed")
        return value

    def restore_checkbox(self, flag):
        self.reset()
        self.mu.mem_write(FLAG, struct.pack("<I", flag))
        self.mu.mem_write(GUI + 0x31C, struct.pack("<I", WIDGET))
        self.mu.reg_write(UC_ARM_REG_R6, SETTINGS)
        self.mu.reg_write(UC_ARM_REG_R7, GUI)
        pc = self.run(0x80054A4C, (0x80033A5C, 0x80034B04),
                      [(0x80054A4C, 0x80054A64), (0x80054CB8, 0x80054CBC)])
        if pc != (0x80033A5C if flag else 0x80034B04):
            raise AssertionError("checkbox restore branch mismatch")
        if [self.mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1)] != [WIDGET, 1]:
            raise AssertionError("checkbox restore arguments changed")
        return {"stored_word": flag, "ui_checked": bool(flag), "setter_boundary": hex(pc)}

    def capture_write(self):
        args = [self.mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if args != [0, SETTINGS, FLASH_OFFSET, RECORD_SIZE]:
            raise AssertionError("settings write boundary arguments changed")
        return bytes(self.mu.mem_read(SETTINGS, RECORD_SIZE))

    def save_record(self, record):
        self.reset()
        self.mu.mem_write(SETTINGS, record)
        self.run(0x800082C0, (WRITE_BOUNDARY,), [(0x800082C0, 0x8000832C)])
        actual = self.capture_write()
        expected = record[:CRC_BYTES] + struct.pack("<I", zlib.crc32(record[:CRC_BYTES]))
        if actual != expected:
            raise AssertionError("settings save CRC differs from independent zlib CRC32")
        if [w for w in self.writes if w[0] >= SETTINGS] != [(SETTINGS + CRC_BYTES, 4)]:
            raise AssertionError("save modified a non-CRC field")
        return actual

    def validate_record(self, record):
        self.reset()
        pointer = STACK + 0xD00
        self.mu.reg_write(UC_ARM_REG_SP, pointer)
        self.mu.mem_write(pointer, record)
        self.mu.mem_write(SETTINGS, b"\xa5" * RECORD_SIZE)
        pc = self.run(0x800080B4, (COPY_BOUNDARY, PRINT_BOUNDARY), [(0x800080B4, 0x80008134)])
        valid = zlib.crc32(record[:CRC_BYTES]) == struct.unpack_from("<I", record, CRC_BYTES)[0]
        if (pc == COPY_BOUNDARY) != valid:
            raise AssertionError("firmware CRC acceptance differs from independent CRC32")
        if valid and [self.mu.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)] != [SETTINGS, pointer, RECORD_SIZE]:
            raise AssertionError("valid-record copy boundary arguments changed")
        if bytes(self.mu.mem_read(SETTINGS, RECORD_SIZE)) != b"\xa5" * RECORD_SIZE:
            raise AssertionError("validation slice unexpectedly wrote settings")
        return valid

    def defaults(self, initial):
        self.reset()
        self.mu.mem_write(SETTINGS, initial)
        self.mu.reg_write(UC_ARM_REG_R5, SETTINGS)
        self.mu.reg_write(UC_ARM_REG_R4, 0x12477CDF)  # retained from reader before invalid-CRC branch
        self.run(0x80008134, (WRITE_BOUNDARY,), [(0x80008134, 0x800081C8)])
        actual = self.capture_write()
        defaults = struct.pack("<7I", 0, 0x4089999A, 100, 90, 1, 1, 1)
        data = defaults + initial[len(defaults):CRC_BYTES]
        expected = data + struct.pack("<I", zlib.crc32(data))
        if actual != expected:
            raise AssertionError("invalid-record default initialization differs")
        return {"fast_cont_default": read_u32(self.mu, FLAG),
                "crc32_valid": True, "unassigned_tail_preserved": True}


def collect(label, path):
    image = path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if EXPECTED_INPUTS.get(label) != digest:
        raise ValueError("only pinned original V3.6/V3.8 inputs are accepted")
    m = SettingsMachine(image)
    binding = m.binding()
    states = [*range(256), 0x100, 0x101, 0x8000, 0x8001, 0xFFFE, 0xFFFF]
    fingerprint = hashlib.sha256()
    for state in states:
        fingerprint.update(struct.pack("<II", state, m.callback(state)))
    restored = [m.restore_checkbox(flag) for flag in (0, 1, 2, 0xFFFFFFFF)]
    rng = random.Random(4470)
    patterns = [bytes(RECORD_SIZE), b"\xff" * RECORD_SIZE,
                bytes(range(RECORD_SIZE))] + [bytes(rng.randrange(256) for _ in range(RECORD_SIZE)) for _ in range(3)]
    records = []
    for pattern in patterns:
        for flag in (0, 1, 2, 0xFFFFFFFF):
            record = bytearray(pattern)
            struct.pack_into("<I", record, 0x18, flag)
            saved = m.save_record(bytes(record))
            if not m.validate_record(saved):
                raise AssertionError("freshly checksummed record rejected")
            records.append(saved)
            fingerprint.update(saved)
    corruption_tests = 0
    for offset in range(RECORD_SIZE):
        damaged = bytearray(records[1])
        damaged[offset] ^= 1
        if m.validate_record(bytes(damaged)):
            raise AssertionError("single-bit-damaged record was accepted")
        corruption_tests += 1
    defaults = [m.defaults(pattern) for pattern in patterns]
    links = []
    for state in (0, 1, 2, 3, 0x8000, 0x8001, 0xFFFF):
        flag = m.callback(state)
        event = m.gui_branch("buzzer_callback", flag, True)
        expected = (5, 34, 19) if flag else (2, 14, 25)
        if (event["case"], event["byte4"], event["byte5"]) != expected:
            raise AssertionError("checkbox -> Buzzer event selection mismatch")
        links.append({"widget_state": state, "normalized_setting": flag, "event": list(expected)})
        fingerprint.update(json.dumps(links[-1], sort_keys=True).encode())
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    windows = {}
    for name, start, end in (("settings_reader_and_defaults", 0x80008098, 0x8000821C),
                             ("settings_save", 0x800082C0, 0x80008340),
                             ("checkbox_handler", 0x8005A3BC, 0x8005A3F8),
                             ("checkbox_state_getter", 0x8003752C, 0x8003753C),
                             ("english_label_tail", 0x8004557C, 0x8004558C),
                             ("registration", 0x80054910, 0x80054924),
                             ("checkbox_restore", 0x80054A4C, 0x80054A64)):
        blob = image[start - BASE:end - BASE]
        windows[name] = {"start": hex(start), "end_exclusive": hex(end), "sha256": hashlib.sha256(blob).hexdigest(),
                         "listing_scope": "Per-word decode may include literals; executed slices are bounded separately",
                         "assembly": [{"address": hex(i.address), "assembly": f"{i.mnemonic} {i.op_str}"}
                                      for addr in range(start, end, 4)
                                      for i in md.disasm(image[addr - BASE:addr - BASE + 4], addr)]}
    return {"version": label, "input_sha256": digest, "gui_binding_slices_passed": 3,
            "checkbox_states_passed": len(states), "checkbox_restore_cases_passed": len(restored),
            "settings_save_cases_passed": len(records), "valid_load_cases_passed": len(records),
            "corrupt_load_cases_rejected": corruption_tests, "default_cases_passed": len(defaults),
            "checkbox_to_event_cases_passed": len(links), "failed": 0,
            "results_sha256": fingerprint.hexdigest(), "gui_binding": binding,
            "restore_examples": restored, "default_example": defaults[0],
            "checkbox_to_event_examples": links, "windows": windows}


def snapshot(path):
    image = path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if len(image) != 16777216 or digest != "ab1e0c4539a2e3e053af78b39c1be5d3b4d3c2934dc96b29d4fd5a9395008be3":
        raise ValueError("unrecognized historical device backup")
    record = image[FLASH_OFFSET:FLASH_OFFSET + RECORD_SIZE]
    valid = zlib.crc32(record[:CRC_BYTES]) == struct.unpack_from("<I", record, CRC_BYTES)[0]
    if not valid:
        raise AssertionError("device backup settings CRC invalid")
    return {"kind": "read-only historical 2026-11-06 E2-modified device backup",
            "flash_sha256": digest, "record_offset": hex(FLASH_OFFSET), "record_bytes": RECORD_SIZE,
            "record_sha256": hashlib.sha256(record).hexdigest(), "crc32_valid": valid,
            "fast_cont_stored_word": struct.unpack_from("<I", record, 0x18)[0],
            "raw_record_published": False, "live_device_observation": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, metavar="VERSION=PATH")
    parser.add_argument("--flash", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = [collect(label, Path(path)) for label, path in (v.split("=", 1) for v in args.input)]
    shared = results[0]["windows"]
    for result in results:
        if {k: v["sha256"] for k, v in result["windows"].items()} != {k: v["sha256"] for k, v in shared.items()}:
            raise AssertionError("original-version code windows differ")
        result["windows"] = {k: {"start": w["start"], "end_exclusive": w["end_exclusive"], "sha256": w["sha256"]}
                             for k, w in result["windows"].items()}
    report = {"schema": "ys4470.fast-cont-setting.v1", "date": "2026-11-07", "cpu_model": "UC_CPU_ARM_926",
              "setting": {"ui_name": "Fast CONT", "address": hex(FLAG), "object": hex(SETTINGS), "offset": "0x18",
                          "default": 1, "flash_record_offset": hex(FLASH_OFFSET), "flash_record_bytes": RECORD_SIZE,
                          "crc": "CRC-32/ISO-HDLC (zlib CRC32), first 0x44 bytes, little-endian u32 at +0x44"},
              "shared_assembly_windows": shared, "versions": results,
              "historical_flash_snapshot": None if args.flash is None else snapshot(args.flash),
              "limits": ["Stops before all storage, GUI state setter, sound and logging/copy API implementations.",
                         "CRC reader begins after the storage read with a synthetic stack record; actual flash I/O is not emulated.",
                         "Default block begins after the error log, with the reader's retained CRC mask and object pointer.",
                         "CRC acceptance alone does not validate field ranges; GUI restore tests use nonzero, while event selection requires exact 1.",
                         "Fast CONT names the UI option, not a measured response time or full reconstruction of continuity hardware."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    keys = ("gui_binding_slices_passed", "checkbox_states_passed", "checkbox_restore_cases_passed",
            "settings_save_cases_passed", "valid_load_cases_passed", "corrupt_load_cases_rejected",
            "default_cases_passed", "checkbox_to_event_cases_passed")
    print(json.dumps({"versions": len(results), **{k: sum(r[k] for r in results) for k in keys},
                      "version_results_equal": len({r["results_sha256"] for r in results}) == 1,
                      "historical_fast_cont": report["historical_flash_snapshot"]}))


if __name__ == "__main__":
    main()
