"""Run the native rotated refresh branch through the original LCD buffer callback."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R5, UC_ARM_REG_SP,
)

from trace_display_flush import FlushReplay, FRAME_BYTES, WIDTH, HEIGHT
from trace_display_refresh_setup import (
    BUFFERS, CONTEXT, DISPLAY, DRIVER, FRAME1, FRAME2, GLOBAL, LAYER, PANEL_FRAME, RETURN, STACK,
)

SCRATCH, SCRATCH_BYTES = 0x11005000, 0x2800
RECTANGLES = ((0, 0, 0, 0), (852, 478, 853, 479), (17, 200, 19, 206),
              (100, 20, 103, 23), (0, 100, 853, 100))
WINDOWS = ((0x80043448, 0x80043474), (0x80012930, 0x80012EF4),
           (0x8000F358, 0x8000F3B4), (0x80025CD8, 0x80025CE4))


class RotationReplay(FlushReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.allocations = []
        self.flush_rectangles = []

    def code(self, u, pc, size, data):
        if pc == self.stop:
            u.emu_stop()
            return
        if pc in (0x800019D0, 0x800328C8, 0x80032A44):
            lr = u.reg_read(UC_ARM_REG_LR)
            if pc == 0x800019D0:
                numerator, denominator = u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)
                assert numerator == 0x1400 and denominator > 0
                u.reg_write(UC_ARM_REG_R0, numerator // denominator)
            elif pc == 0x800328C8:
                assert u.reg_read(UC_ARM_REG_R0) == SCRATCH_BYTES
                self.allocations.append(SCRATCH_BYTES)
                u.reg_write(UC_ARM_REG_R0, SCRATCH)
            else:
                assert u.reg_read(UC_ARM_REG_R0) == SCRATCH
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc == 0x800115F4:
            self.flush_rectangles.append(list(struct.unpack("<4h", u.mem_read(u.reg_read(UC_ARM_REG_R1), 8))))
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if 0x80012930 <= pc < 0x80012EF4:
            if any(start <= address and address + size <= end for start, end in (
                (SCRATCH, SCRATCH + SCRATCH_BYTES),
                (FRAME1, FRAME1 + 192000), (FRAME2, FRAME2 + 192000),
            )):
                assert size == 2 and address % 2 == 0
                return
        super().write(u, access, address, size, value, data)

    def rotate_cases(self):
        self.execute(0x8003B080, 0x80025AC8)
        self.put(GLOBAL + 4, DISPLAY)
        assert self.word(DRIVER + 0x10) == 0x413C
        background = b"\xA5\x5A" * (WIDTH * HEIGHT)
        cases = []
        for source in (FRAME1, FRAME2):
            for bounds in RECTANGLES:
                left, top, right, bottom = bounds
                width, height = right - left + 1, bottom - top + 1
                pixels = [((i * 173) ^ 0xF386) & 0xFFFF for i in range(width * height)]
                self.u.mem_write(source, struct.pack(f"<{len(pixels)}H", *pixels))
                self.u.mem_write(PANEL_FRAME, background)
                self.u.mem_write(LAYER, struct.pack("<4h", *bounds))
                self.put(CONTEXT, source)
                self.put(CONTEXT + 4, LAYER)
                self.put(BUFFERS + 0x10, 1)
                self.put(BUFFERS + 0x14, 1)
                self.pixel_offsets = set()
                self.allocations = []
                self.flush_rectangles = []
                self.stop = 0x80043474
                for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK),
                                   (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_R0, DRIVER),
                                   (UC_ARM_REG_R5, CONTEXT)):
                    self.u.reg_write(reg, value)
                self.u.emu_start(0x80043448, 0, count=500000)
                assert self.u.reg_read(UC_ARM_REG_PC) == self.stop
                assert self.u.reg_read(UC_ARM_REG_SP) == STACK
                expected = bytearray(background)
                indices = set()
                for y in range(height):
                    for x in range(width):
                        panel_x, panel_y = WIDTH - 1 - (top + y), left + x
                        offset = panel_y * WIDTH + panel_x
                        indices.add(offset)
                        struct.pack_into("<H", expected, offset * 2, pixels[y * width + x])
                actual = bytes(self.u.mem_read(PANEL_FRAME, FRAME_BYTES))
                assert actual == expected and self.pixel_offsets == indices, (bounds, source)
                assert self.word(BUFFERS + 0x10) == self.word(BUFFERS + 0x14) == 0
                cases.append(dict(source=hex(source), logical_rectangle=bounds,
                                  callback_rectangles=self.flush_rectangles, pixels_copied=len(indices),
                                  scratch_allocations=self.allocations, completion_flags=[0, 0],
                                  frame_sha256=hashlib.sha256(actual).hexdigest()))
        return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        replay = RotationReplay(raw)
        cases = replay.rotate_cases()
        observations.append((cases, replay.coverage))
    assert observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.native-display-rotation.v1", images=images, cases=cases,
                  native_driver_flags="0x413c", logical_dimensions=[854, 480],
                  panel_dimensions=[480, 854], mapping="panel_x = 479 - logical_y; panel_y = logical_x",
                  instruction_bytes={hex(pc): word for pc, word in sorted(coverage.items())},
                  limits=["The original refresh branch at 0x80043448 selects original rotation 0x80012930.",
                          "The native initialized driver supplies the callback and 0x413c flags.",
                          "Layer geometry, active display, source pixels and busy flags are fixtures.",
                          "Division and rotation scratch allocation/release are modeled.",
                          "Original rotation and callback execute and the complete panel buffer is compared.",
                          "Full scheduler-driven rendering and physical LCD transfer and timing remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 20 native rotated display flush cases across both factory images")


if __name__ == "__main__":
    main()
