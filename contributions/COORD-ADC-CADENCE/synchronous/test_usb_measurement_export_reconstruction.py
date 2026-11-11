"""Compare linked freestanding ARM926 export C with the original replay records."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from elftools.elf.elffile import ELFFile
from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_SP, UC_CPU_ARM_926,
)

RETURN, STACK, STATE, TEXT, MIRROR, WIRE = (
    0x10000000, 0x10005000, 0x10001000, 0x10002000, 0x10003000, 0x10004000,
)


class Reconstruction:
    def __init__(self, linked):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        with linked.open("rb") as stream:
            elf = ELFFile(stream)
            assert elf.elfclass == 32 and elf.little_endian
            assert elf["e_type"] == "ET_EXEC" and elf["e_machine"] == "EM_ARM"
            assert not any(section["sh_type"] in ("SHT_REL", "SHT_RELA") for section in elf.iter_sections())
            segments = [segment for segment in elf.iter_segments() if segment["p_type"] == "PT_LOAD"]
            low = min(segment["p_vaddr"] for segment in segments) & ~0xFFF
            high = (max(segment["p_vaddr"] + segment["p_memsz"] for segment in segments) + 0xFFF) & ~0xFFF
            assert 0 < high - low <= 0x20000
            assert low >= STACK
            u.mem_map(low, high - low)
            for segment in segments:
                assert segment["p_filesz"] <= segment["p_memsz"]
                u.mem_write(segment["p_vaddr"], segment.data())
            section = elf.get_section_by_name(".text")
            self.code_start = section["sh_addr"]
            self.code_end = self.code_start + section["sh_size"]
            names = elf.get_section_by_name(".symtab")
            self.entries = {}
            for name in ("ys4470_export_update", "ys4470_export_report"):
                symbol, = names.get_symbol_by_name(name)
                assert symbol["st_info"]["type"] == "STT_FUNC"
                self.entries[name] = symbol["st_value"]
        u.mem_map(RETURN, 0x5000)
        self.destination = None
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def code(self, u, pc, size, data):
        assert size == 4 and self.code_start <= pc < self.code_end

    def write(self, u, access, address, size, value, data):
        start, length = self.destination
        assert STACK - 0x100 <= address and address + size <= STACK or (
            start <= address and address + size <= start + length), hex(address)

    def call(self, name, args, destination):
        u = self.u
        self.destination = destination
        for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3), args):
            u.reg_write(reg, value)
        for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, RETURN)):
            u.reg_write(reg, value)
        u.emu_start(self.entries[name], RETURN, count=10_000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == STACK
        return u.reg_read(UC_ARM_REG_R0)

    def update(self, state, text, strip):
        self.u.mem_write(STATE, struct.pack("<i4BI", *state))
        if text is not None:
            self.u.mem_write(TEXT, text.encode("ascii") + b"\0")
        self.u.mem_write(MIRROR, b"\xA5" * 21)
        result = self.call("ys4470_export_update", (STATE, 0 if text is None else TEXT, strip, MIRROR), (MIRROR, 21))
        assert result in (0, 1)
        return bool(result), bytes(self.u.mem_read(MIRROR, 21))

    def report(self, mirror):
        assert len(mirror) == 21
        self.u.mem_write(MIRROR, mirror)
        self.u.mem_write(WIRE, b"\xA5" * 64)
        self.call("ys4470_export_report", (MIRROR, WIRE), (WIRE, 64))
        return bytes(self.u.mem_read(WIRE, 64))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    machine = Reconstruction(args.elf)
    inputs = {}
    for name in ("factory-usb-export-routing-validation.json", "ac-usb-export-validation.json"):
        data = Path(__file__).with_name(name).read_bytes()
        inputs[name] = (json.loads(data), hashlib.sha256(data).hexdigest())
    routing, live = (report for report, _ in inputs.values())
    assert routing["images"] == live["images"]
    for ui_mode, configuration, secondary, fast, raw, selector, text, strip, expected, mirror in routing["cases"]:
        changed, compiled = machine.update((raw, ui_mode, configuration, secondary, selector, fast), text, strip)
        assert changed == (expected is not None) and compiled.hex() == mirror
    built = [case for case in live["cases"] if case["frame_built"]]
    for case in built:
        assert machine.report(bytes.fromhex(case["mirror_hex"])).hex() == case["frame"]
    assert machine.update((100, 1, 11, 0x19, 0, 0), "12.345", 0) == (False, b"\xA5" * 21)
    receipt = dict(
        schema="ys4470.usb-export-reconstruction.v1", images=routing["images"],
        original_evidence_sha256={name: digest for name, (_, digest) in inputs.items()},
        linked_elf_sha256=hashlib.sha256(args.elf.read_bytes()).hexdigest(),
        source_sha256={name: hashlib.sha256((Path("reconstruction") / name).read_bytes()).hexdigest()
                       for name in ("usb_measurement_export.c", "usb_measurement_export.h")},
        c_mirror_cases=len(routing["cases"]), c_report_cases=len(built),
        unsupported_suffix_cases=1, link_entries={name: hex(value) for name, value in machine.entries.items()},
        limits=["A shared original observation is compared once with the compiled C.",
                "The reconstruction covers text/category routing, the mirror and report bytes.",
                "USB gates, FIFO transfers and enumeration remain outside the C component."],
    )
    args.out.write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
    print(f"PASS {len(routing['cases'])} ARM926 C mirror cases, {len(built)} report cases and 1 unsupported-suffix case")


if __name__ == "__main__":
    main()
