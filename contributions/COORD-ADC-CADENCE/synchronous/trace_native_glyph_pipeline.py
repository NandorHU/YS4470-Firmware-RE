"""Connect native dirty-area setup, factory glyph pixels and rotated panel copying."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_R5, UC_ARM_REG_R7, UC_ARM_REG_SP,
)

from trace_ac_alpha_mask import WINDOWS as ALPHA_WINDOWS, CACHE, SCALED
from trace_ac_rgb565_frame import rgb565
from trace_display_rotation import RotationReplay
from trace_display_refresh_setup import (
    BUFFERS, CONTEXT, DISPLAY, DRIVER, FRAME1, GLOBAL, PANEL_FRAME, RETURN, STACK,
)

DRAW, POINT, GLYPH, ALPHA = 0x11004000, 0x11004100, 0x11004200, 0x11008000
BOUNDS = (10, 10, 129, 121)
COLOR = 0xF386
CODE = (
    *ALPHA_WINDOWS, (0x80028A5C, 0x80029400), (0x8001B8C0, 0x8001BD48),
    (0x80024FA4, 0x80024FFC), (0x800218A8, 0x800218DC), (0x8002B9F8, 0x8002B9FC),
    (0x80043A58, 0x80043D3C), (0x80025DD8, 0x80025E14),
)


class GlyphReplay(RotationReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.alpha_size = 0

    def code(self, u, pc, size, data):
        if pc == self.stop:
            u.emu_stop()
            return
        lr = u.reg_read(UC_ARM_REG_LR)
        if pc == 0x800019D0 and lr == 0x80043B9C:
            numerator, divisor = u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)
            assert numerator == 96000 and divisor == 120
            u.reg_write(UC_ARM_REG_R0, numerator // divisor)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc == 0x800328C8 and lr == 0x80014828:
            self.alpha_size = u.reg_read(UC_ARM_REG_R0)
            assert 0 < self.alpha_size <= 854
            u.reg_write(UC_ARM_REG_R0, ALPHA)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc == 0x80027694:
            assert lr == 0x800148A8
            u.reg_write(UC_ARM_REG_R0, 0)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc == 0x80032A44 and lr == 0x80014A68:
            assert u.reg_read(UC_ARM_REG_R0) == ALPHA
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if any(lo <= pc < hi for lo, hi in CODE):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if STACK - 0x800 <= address and address + size <= STACK:
            return
        if FRAME1 <= address and address + size <= FRAME1 + 120 * 112 * 2:
            assert 0x8001B8C0 <= pc < 0x8001BD48 or 0x80012930 <= pc < 0x80012EF4
            return
        if any(lo <= address and address + size <= hi for lo, hi in (
            (ALPHA, ALPHA + self.alpha_size), (CACHE, CACHE + 8), (SCALED, SCALED + 16),
        )):
            return
        super().write(u, access, address, size, value, data)

    def call_glyph(self, font, character, opacity):
        font_data = self.word(font + 0x10)
        record = self.word(font_data + 4) + 8 * (ord(character) - 31)
        encoded, width, height = struct.unpack("<IBB", self.u.mem_read(record, 6))
        bitmap = self.word(font_data) + (encoded & 0xFFFFF)
        packed = bytes(self.u.mem_read(bitmap, (width * height + 1) // 2))
        self.u.mem_write(DRAW, bytes(32))
        self.u.mem_write(DRAW + 12, struct.pack("<H", COLOR))
        self.u.mem_write(DRAW + 0x1A, bytes((opacity,)))
        self.u.mem_write(POINT, struct.pack("<2h", 20, 20))
        self.u.mem_write(GLYPH, bytes(16))
        self.u.mem_write(GLYPH + 6, struct.pack("<2H", width, height))
        self.u.mem_write(GLYPH + 14, b"\x04")
        sp = STACK - 0x200
        self.u.mem_write(sp, struct.pack("<I", bitmap))
        self.stop = RETURN
        for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, sp), (UC_ARM_REG_LR, RETURN),
                           (UC_ARM_REG_R0, CONTEXT), (UC_ARM_REG_R1, DRAW),
                           (UC_ARM_REG_R2, POINT), (UC_ARM_REG_R3, GLYPH)):
            self.u.reg_write(reg, value)
        self.u.emu_start(0x80014688, 0, count=1000000)
        assert self.u.reg_read(UC_ARM_REG_PC) == RETURN and self.u.reg_read(UC_ARM_REG_SP) == sp
        return width, height, packed

    def run_pipeline(self):
        self.execute(0x8003B080, 0x80025AC8)
        self.put(GLOBAL + 4, DISPLAY)
        cases = []
        for font, character in ((0x804B000C, "0"), (0x804B000C, "."), (0x800D0BB4, "V")):
            for opacity in (128, 255):
                self.u.mem_write(DISPLAY + 0x30, struct.pack("<4h", *BOUNDS))
                self.put(BUFFERS + 8, FRAME1)
                self.put(BUFFERS + 0x18, 1)
                self.stop = 0x800430D0
                for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK - 0x80),
                                   (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_R0, DISPLAY), (UC_ARM_REG_R7, 0)):
                    self.u.reg_write(reg, value)
                self.u.emu_start(0x80043A58, 0, count=10000)
                assert self.u.reg_read(UC_ARM_REG_PC) == self.stop
                assert self.word(CONTEXT) == FRAME1
                assert struct.unpack("<4h", self.u.mem_read(self.word(CONTEXT + 4), 8)) == BOUNDS
                initial = b"\xA5\x5A" * (120 * 112)
                self.u.mem_write(FRAME1, initial)
                width, height, packed = self.call_glyph(font, character, opacity)
                expected = bytearray(initial)
                for y in range(height):
                    for x in range(width):
                        gx, gy = 20 + x, 20 + y
                        if not (BOUNDS[0] <= gx <= BOUNDS[2] and BOUNDS[1] <= gy <= BOUNDS[3]):
                            continue
                        n = y * width + x
                        nibble = packed[n // 2] & 15 if n & 1 else packed[n // 2] >> 4
                        alpha = nibble * 17
                        if opacity < 253:
                            alpha = opacity if alpha == 255 else alpha * opacity // 256
                        if alpha:
                            effective = alpha if opacity >= 253 else alpha * opacity // 256
                            offset = ((gy - BOUNDS[1]) * 120 + gx - BOUNDS[0]) * 2
                            pixel = COLOR if effective == 255 else rgb565(COLOR, 0x5AA5, effective)
                            struct.pack_into("<H", expected, offset, pixel)
                assert bytes(self.u.mem_read(FRAME1, len(initial))) == expected
                self.u.mem_write(PANEL_FRAME, b"\xA5\x5A" * (480 * 854))
                self.pixel_offsets = set()
                self.flush_rectangles = []
                self.stop = 0x80043474
                for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK - 0x200),
                                   (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_R0, DRIVER), (UC_ARM_REG_R5, CONTEXT)):
                    self.u.reg_write(reg, value)
                self.u.emu_start(0x80043448, 0, count=3000000)
                assert self.u.reg_read(UC_ARM_REG_PC) == self.stop
                panel = bytearray(b"\xA5\x5A" * (480 * 854))
                for y in range(112):
                    for x in range(120):
                        offset = ((BOUNDS[0] + x) * 480 + 479 - BOUNDS[1] - y) * 2
                        panel[offset:offset + 2] = expected[(y * 120 + x) * 2:(y * 120 + x + 1) * 2]
                actual = bytes(self.u.mem_read(PANEL_FRAME, len(panel)))
                assert actual == panel and len(self.pixel_offsets) == 120 * 112
                assert self.word(BUFFERS + 0x10) == self.word(BUFFERS + 0x14) == 0
                cases.append(dict(font=hex(font), character=character, opacity=opacity,
                                  glyph_size=[width, height], dirty_rectangle=BOUNDS,
                                  draw_sha256=hashlib.sha256(expected).hexdigest(),
                                  panel_sha256=hashlib.sha256(actual).hexdigest(),
                                  flush_rectangles=self.flush_rectangles, copied_pixels=len(self.pixel_offsets)))
        return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        replay = GlyphReplay(raw)
        cases = replay.run_pipeline()
        observations.append((cases, replay.coverage))
    assert observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.native-display-glyph-pipeline.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): data for pc, data in sorted(coverage.items())},
                  limits=["Original dirty-region setup derives buffer and clip from the native driver.",
                          "Original glyph alpha expansion, RGB565 blend, rotation and flush execute in the same emulation.",
                          "Selected glyph metadata, color, opacity, dirty rectangle, active display and entry registers are fixtures.",
                          "Panel hardware initialization, allocations, division and external masks are modeled.",
                          "The native object renderer is replaced by the selected original glyph path.",
                          "Live dirty production, complete object rendering, physical LCD transfer and timing remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 12 native dirty-region to glyph to rotated panel cases")


if __name__ == "__main__":
    main()
