"""Replay factory AC glyph alpha dispatch through the RGB565 framebuffer writer."""

import argparse
import hashlib
from itertools import product
import json
from pathlib import Path
import struct

from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP,
)

from trace_ac_alpha_mask import AlphaReplay, BASE, BUFFER, CLIP, CONTEXT, DRAW, ENTRY, RETURN, STACK


INIT, DISPATCH, BLEND, FILL = 0x80029CC8, 0x80028A50, 0x80028A5C, 0x8001B8C0
DISPLAY, DRIVER, AREA, FRAME = 0x11001500, 0x11001600, 0x11001700, 0x11010000
WIDTH, HEIGHT, FRAME_MAP_BYTES = 160, 160, 0xD000
COLOR = 0xF386
CASES = ((0x804B000C, "0"), (0x804B000C, "."), (0x800D0BB4, "V"))
EXTRA_CODE = (
    (INIT, 0x80029D60), (0x8002B9F8, 0x8002B9FC), (BLEND, 0x80029400),
    (0x800218A8, 0x800218DC), (FILL, 0x8001BD48), (0x80024FA4, 0x80024FFC),
)


def rgb565(foreground, background, alpha):
    """Reference packed RGB565 mixer with the original five-bit mix ratio."""
    ratio = (alpha + 4) // 8
    mask = 0x07E0F81F
    fg = (foreground * 0x10001) & mask
    bg = (background * 0x10001) & mask
    mixed = (bg + (((fg - bg) * ratio % (1 << 32)) >> 5)) & mask
    return (mixed | mixed >> 16) & 0xFFFF


class FrameReplay(AlphaReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.u.mem_map(FRAME, FRAME_MAP_BYTES)
        self.u.mem_write(DISPLAY, struct.pack("<I", DRIVER))
        self.u.mem_write(DRIVER + 0x10, b"\x08")
        self.u.reg_write(UC_ARM_REG_CPSR, 0x13)
        self.u.reg_write(UC_ARM_REG_R1, CONTEXT)
        self.u.reg_write(UC_ARM_REG_LR, RETURN)
        self.u.reg_write(UC_ARM_REG_SP, STACK)
        self.u.emu_start(INIT, RETURN, count=300)
        assert self.u.reg_read(UC_ARM_REG_PC) == RETURN
        assert self.word(CONTEXT + 0x54) == BLEND and self.word(CONTEXT + 0x48) == 0x8002A0BC
        self.u.mem_write(CONTEXT, struct.pack("<2I", FRAME, AREA))
        self.u.mem_write(CONTEXT + 8, struct.pack("<I", CLIP))
        self.u.mem_write(AREA, struct.pack("<4h", 0, 0, WIDTH - 1, HEIGHT - 1))

    def code(self, u, pc, size, data):
        if pc == ENTRY:
            u.mem_write(DRAW + 0xC, struct.pack("<H", COLOR))
        if pc == 0x8000B280 and u.reg_read(UC_ARM_REG_LR) == 0x80028AD0:
            u.reg_write(UC_ARM_REG_R0, DISPLAY)
            u.reg_write(UC_ARM_REG_PC, 0x80028AD0)
            return
        if pc == DISPATCH:
            r1 = u.reg_read(UC_ARM_REG_R1)
            bounds = struct.unpack("<4h", u.mem_read(self.word(r1), 8))
            left, top, right, bottom = bounds
            assert 0 <= left <= right < WIDTH and 0 <= top <= bottom < HEIGHT
            assert self.word(r1 + 0xC) == BUFFER and self.word(r1 + 0x14) == self.word(r1)
            assert u.mem_read(r1 + 0x10, 1) == b"\x02"
            count = (right - left + 1) * (bottom - top + 1)
            assert 0 < count <= self.scratch_length
            self.outputs.append((bounds, bytes(u.mem_read(BUFFER, count))))
        if any(lo <= pc < hi for lo, hi in EXTRA_CODE):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if CONTEXT <= address < CONTEXT + 0x58:
            pc = u.reg_read(UC_ARM_REG_PC)
            assert INIT <= pc < INIT + 0x98 or 0x80032E14 <= pc < 0x80032EA4
            return
        if FRAME <= address < FRAME + FRAME_MAP_BYTES:
            assert FILL <= u.reg_read(UC_ARM_REG_PC) < 0x8001BD48
            assert address % 2 == 0 and size in (2, 4) and address + size <= FRAME + WIDTH * HEIGHT * 2
            self.written.update(range((address - FRAME) // 2, (address - FRAME + size) // 2))
            return
        super().write(u, access, address, size, value, data)

    def frame_case(self, font, char, opacity, clip_kind):
        pixels = [((i * 173) ^ (i // WIDTH * 719) ^ 0x2937) & 0xFFFF for i in range(WIDTH * HEIGHT)]
        initial = struct.pack(f"<{len(pixels)}H", *pixels)
        self.u.mem_write(FRAME, initial)
        self.written = set()
        result = self.run(font, char, opacity, clip_kind)
        left, top, right, bottom = result["clip"]
        inside = {y * WIDTH + x for y in range(top, bottom + 1) for x in range(left, right + 1)}
        for (x1, y1, x2, y2), values in self.outputs:
            for index, alpha in enumerate(values):
                row, col = divmod(index, x2 - x1 + 1)
                pixel = (y1 + row) * WIDTH + x1 + col
                assert pixel in inside
                if alpha:
                    effective = alpha if opacity >= 253 else opacity if alpha == 255 else alpha * opacity // 256
                    pixels[pixel] = COLOR if effective == 255 else rgb565(COLOR, pixels[pixel], effective)
        actual = bytes(self.u.mem_read(FRAME, len(initial)))
        expected = struct.pack(f"<{len(pixels)}H", *pixels)
        if actual != expected:
            diff = next(i for i in range(len(pixels)) if actual[i*2:i*2+2] != expected[i*2:i*2+2])
            offset = 2 * diff
            raise AssertionError((char, opacity, clip_kind, divmod(diff, WIDTH),
                                  actual[offset:offset + 2].hex(), expected[offset:offset + 2].hex()))
        assert self.written <= inside and self.written
        result.update(frame_sha256=hashlib.sha256(actual).hexdigest(),
                      pixels_written=len(self.written), outside_clip_unchanged=len(pixels) - len(inside))
        return result


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
        replay = FrameReplay(raw)
        cases = [replay.frame_case(font, char, opacity, clip)
                 for (font, char), opacity, clip in product(CASES, (64, 128, 255), ("full", "trimmed"))]
        assert {INIT, DISPATCH, BLEND, FILL, 0x80024FA4} <= replay.coverage.keys()
        observations.append((cases, replay.coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.ac-rgb565-frame.v1", images=images, cases=cases,
                  original_callbacks={"0x54": hex(BLEND), "0x48": "0x8002a0bc"},
                  frame_size=[WIDTH, HEIGHT], color=hex(COLOR),
                  instruction_bytes={hex(pc): data for pc, data in sorted(coverage.items())},
                  limits=["Factory glyphs and blend code execute in ARM926 emulation.",
                          "Framebuffer, color, opacity, clip and display flags are fixtures.",
                          "Scratch allocation, display lookup and external masks are modeled.",
                          "Custom display callback, physical LCD transfer and timing remain untested."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {2*len(cases)} original RGB565 glyph cases across both images")


if __name__ == "__main__":
    main()
