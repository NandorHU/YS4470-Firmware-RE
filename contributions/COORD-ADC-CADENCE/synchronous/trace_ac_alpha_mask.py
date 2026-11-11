"""Run the original 4-bit glyph unpacker to its blend dispatch."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_CPU_ARM_926,
)

BASE = 0x7FFFFFE0
ENTRY, LOOKUP, CACHE, SCALED = 0x80014688, 0x80068FC6, 0x805ABE08, 0x809B5518
RETURN, STACK, CONTEXT = 0x11000000, 0x11005000, 0x11001000
DRAW, POINT, GLYPH, CLIP, BLEND, BUFFER = (CONTEXT + n for n in (0x100, 0x200, 0x300, 0x400, 0x500, 0x1000))
WINDOWS = ((ENTRY, 0x80014A70), (0x80032E14, 0x80032EA4),
           (0x800289F8, 0x80028A5C), (0x80008FC4, 0x80009054))


class AlphaReplay:
    def __init__(self, raw):
        self.raw = raw
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        u.mem_map(BASE & ~0xFFF, 0x9D0000)
        u.mem_write(BASE, raw)
        u.mem_map(RETURN, 0x6000)
        u.mem_write(CONTEXT + 0x08, struct.pack("<I", CLIP))
        u.mem_write(CONTEXT + 0x54, struct.pack("<I", BLEND))
        self.coverage = {}
        self.scratch_length = 0
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def word(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def code(self, u, pc, size, data):
        r0, r1, lr = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
        if pc == BLEND:
            assert r0 == CONTEXT and lr == 0x80028A54
            bounds = struct.unpack("<4h", u.mem_read(self.word(r1), 8))
            left, top, right, bottom = bounds
            count = (right - left + 1) * (bottom - top + 1)
            assert 0 < count <= self.scratch_length
            assert self.word(r1 + 0x0C) == BUFFER
            assert self.word(r1 + 0x14) == self.word(r1)
            assert bytes(u.mem_read(r1 + 0x10, 1)) == b"\x02"
            self.outputs.append((bounds, bytes(u.mem_read(BUFFER, count))))
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        leaves = {
            0x8000B280: (0x8001480C, CONTEXT), 0x80025CE4: (0x80014810, 32767),
            0x80027694: (0x800148A8, 0), 0x80032A44: (0x80014A68, 0),
        }
        if pc == 0x800328C8:
            assert lr == 0x80014828 and 0 < r0 <= 0x3000
            self.scratch_length = r0
            u.reg_write(UC_ARM_REG_R0, BUFFER)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc in leaves:
            expected_lr, result = leaves[pc]
            assert lr == expected_lr
            if pc == 0x80032A44:
                assert r0 == BUFFER
            u.reg_write(UC_ARM_REG_R0, result)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        assert size == 4 and any(start <= pc < end for start, end in WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        assert any(start <= address and address + size <= end for start, end in (
            (STACK - 0x400, STACK), (BUFFER, BUFFER + self.scratch_length),
            (CACHE, CACHE + 8), (SCALED, SCALED + 16),
        )), (hex(u.reg_read(UC_ARM_REG_PC)), hex(address), size)

    def run(self, font, char, opacity, clip_kind):
        u = self.u
        font_data = self.word(font + 0x10)
        index = ord(char) - 31
        record = self.word(font_data + 4) + 8 * index
        encoded, width, height = struct.unpack("<IBB", u.mem_read(record, 6))
        address = self.word(font_data) + (encoded & 0xFFFFF)
        packed = bytes(u.mem_read(address, (width * height + 1) // 2))
        x, y = 20, 30
        dx, dy = (1, 1) if clip_kind == "trimmed" else (0, 0)
        right, bottom = x + width - 1 - dx, y + height - 1 - dy
        clip = (x + dx, y + dy, right, bottom)
        u.mem_write(CLIP, struct.pack("<4h", *clip))
        u.mem_write(POINT, struct.pack("<2h", x, y))
        u.mem_write(DRAW, bytes(32))
        u.mem_write(DRAW + 0x1A, bytes((opacity,)))
        u.mem_write(GLYPH, bytes(16))
        u.mem_write(GLYPH + 6, struct.pack("<2H", width, height))
        u.mem_write(GLYPH + 0xE, b"\x04")
        u.mem_write(STACK, struct.pack("<I", address))
        self.outputs = []
        for reg, value in ((UC_ARM_REG_R0, CONTEXT), (UC_ARM_REG_R1, DRAW), (UC_ARM_REG_R2, POINT),
                           (UC_ARM_REG_R3, GLYPH), (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_SP, STACK),
                           (UC_ARM_REG_CPSR, 0x13)):
            u.reg_write(reg, value)
        u.emu_start(ENTRY, RETURN, count=1_000_000)
        assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == STACK
        alpha = [i * 17 for i in range(16)]
        assert bytes(u.mem_read(LOOKUP, 16)) == bytes(alpha)
        if opacity < 253:
            alpha = [(v * opacity) >> 8 if v != 255 else opacity for v in alpha]
            assert bytes(u.mem_read(SCALED, 16)) == bytes(alpha)
        expected = bytearray()
        for row in range(dy, height - dy):
            for col in range(dx, width - dx):
                n = row * width + col
                value = packed[n // 2]
                expected.append(alpha[value & 15 if n & 1 else value >> 4])
        next_top = clip[1]
        for bounds, _ in self.outputs:
            assert bounds[0] == clip[0] and bounds[2] == clip[2] and bounds[1] == next_top
            next_top = bounds[3] + 1
        assert next_top == clip[3] + 1
        assert b"".join(data for _, data in self.outputs) == expected, (char, opacity, clip_kind)
        return dict(font=hex(font), character=char, opacity=opacity, clip_kind=clip_kind,
                    clip=clip, glyph_size=(width, height), alpha_bytes=len(expected),
                    blend_regions=[bounds for bounds, _ in self.outputs],
                    alpha_sha256=hashlib.sha256(expected).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    images, observations = {}, []
    for entry in manifest["images"]:
        raw = Path(entry["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry["sha256"] and len(raw) == entry["size_bytes"]
        images[entry["version"]] = digest
        replay = AlphaReplay(raw)
        cases = [replay.run(font, char, opacity, clip) for (font, char), opacity, clip in product(
            ((0x804B000C, "0"), (0x804B000C, "."), (0x800D0BB4, "V")), (64, 128, 255), ("full", "trimmed"))]
        observations.append((cases, replay.coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.ac-alpha-mask.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): data for pc, data in sorted(coverage.items())},
                  limits=["The original 4-bit glyph unpacker and blend dispatcher execute.",
                          "Glyph data comes from the factory fonts, and clip coordinates and opacity are fixtures.",
                          "Scratch allocation, external masks and the final RGB565 blend callback are modeled."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {2*len(cases)} original alpha mask cases across both images")


if __name__ == "__main__":
    main()
