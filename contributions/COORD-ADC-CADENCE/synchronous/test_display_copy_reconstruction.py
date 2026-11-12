"""Compare freestanding ARM926 C copies against native firmware framebuffer hashes."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (
    UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_SP,
)

RETURN, RECT, SOURCE, PANEL, STACK = 0x10000000, 0x10001000, 0x10010000, 0x10020000, 0x100FF000
PANEL_BYTES = 480 * 854 * 2
FUNCTIONS = ("ys4470_panel_copy", "ys4470_panel_copy_rotated")


class CompiledReplay:
    def __init__(self, path):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        with path.open("rb") as stream:
            elf = ELFFile(stream)
            assert elf.elfclass == 32 and elf.little_endian and elf["e_machine"] == "EM_ARM"
            assert elf["e_type"] == "ET_EXEC"
            assert not any(s["sh_type"] in ("SHT_REL", "SHT_RELA") for s in elf.iter_sections())
            segments = [s for s in elf.iter_segments() if s["p_type"] == "PT_LOAD"]
            low = min(s["p_vaddr"] for s in segments) & ~0xFFF
            high = (max(s["p_vaddr"] + s["p_memsz"] for s in segments) + 0xFFF) & ~0xFFF
            assert 0x10100000 <= low < high <= 0x10120000
            u.mem_map(low, high - low)
            for segment in segments:
                assert segment["p_filesz"] <= segment["p_memsz"]
                u.mem_write(segment["p_vaddr"], segment.data())
            section = elf.get_section_by_name(".text")
            self.code_start, self.code_end = section["sh_addr"], section["sh_addr"] + section["sh_size"]
            symbols = elf.get_section_by_name(".symtab")
            self.entries = {name: symbols.get_symbol_by_name(name)[0]["st_value"] for name in FUNCTIONS}
        u.mem_map(RETURN, 0x100000)
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def code(self, u, pc, size, _):
        assert size == 4 and self.code_start <= pc < self.code_end

    def write(self, u, access, address, size, value, _):
        assert PANEL <= address and address + size <= PANEL + PANEL_BYTES or STACK - 0x100 <= address and address + size <= STACK

    def run(self, name, bounds):
        left, top, right, bottom = bounds
        count = max(0, right - left + 1) * max(0, bottom - top + 1)
        source = struct.pack(f"<{max(1,count)}H", *[
            ((i * 173) ^ 0xF386) & 0xFFFF for i in range(max(1, count))])
        u = self.u
        u.mem_write(RECT, struct.pack("<4h", *bounds))
        u.mem_write(SOURCE, source)
        u.mem_write(PANEL, b"\xA5\x5A" * (480 * 854))
        for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK), (UC_ARM_REG_LR, RETURN),
                           (UC_ARM_REG_R0, RECT), (UC_ARM_REG_R1, SOURCE), (UC_ARM_REG_R2, PANEL)):
            u.reg_write(reg, value)
        u.emu_start(self.entries[name], RETURN, count=100000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == STACK
        assert bytes(u.mem_read(SOURCE, len(source))) == source
        result = u.reg_read(UC_ARM_REG_R0)
        assert result in (0, 1)
        return bool(result), hashlib.sha256(u.mem_read(PANEL, PANEL_BYTES)).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--elf", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    replay = CompiledReplay(args.elf)
    images, inputs, counts = None, {}, {}
    for filename, function, rectangle_key in (
        ("display-flush-validation.json", FUNCTIONS[0], "rectangle"),
        ("display-rotation-validation.json", FUNCTIONS[1], "logical_rectangle"),
    ):
        path = Path(__file__).with_name(filename)
        raw = path.read_bytes()
        report = json.loads(raw)
        assert images is None or images == report["images"]
        images = report["images"]
        inputs[filename] = hashlib.sha256(raw).hexdigest()
        for case in report["cases"]:
            copied, digest = replay.run(function, case[rectangle_key])
            assert digest == case["frame_sha256"] and copied == (case["pixels_copied"] > 0)
        counts[function] = len(report["cases"])
    invalid = ((-1, 0, 0, 0), (0, -1, 0, 0), (0, 0, 854, 0), (0, 0, 0, 854))
    blank = hashlib.sha256(b"\xA5\x5A" * (480 * 854)).hexdigest()
    for function in FUNCTIONS:
        for bounds in invalid:
            assert replay.run(function, bounds) == (False, blank)
    report = dict(schema="ys4470.display-copy-reconstruction.v1", images=images,
                  original_evidence_sha256=inputs, comparisons=counts,
                  rejected_rectangles=len(invalid) * len(FUNCTIONS),
                  source_sha256={name: hashlib.sha256((Path("reconstruction") / name).read_bytes()).hexdigest()
                                 for name in ("display_copy.c", "display_copy.h")},
                  linked_elf_sha256=hashlib.sha256(args.elf.read_bytes()).hexdigest(),
                  limits=["Compiled freestanding C executes as ARM926 code in Unicorn.",
                          "The complete panel buffer hashes match the original replay cases.",
                          "C leaves source pixels intact and exposes a checked rectangle interface.",
                          "Native allocation, source mutation, busy flags, display scheduling and LCD hardware are outside this C component."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 26 original framebuffer comparisons and 8 invalid rectangle checks")


if __name__ == "__main__":
    main()
