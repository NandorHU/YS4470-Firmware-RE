"""Execute the native display flush callback into its original RAM framebuffer."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_SP

from trace_display_refresh_setup import (
    SetupReplay, BASE, BUFFERS, CONTEXT, DRIVER, FRAME1, FRAME2, LAYER, PANEL_FRAME, RETURN, STACK,
)

WIDTH, HEIGHT = 480, 854
FRAME_BYTES = WIDTH * HEIGHT * 2
RECTANGLES = (
    (0, 0, 0, 0), (479, 853, 479, 853), (0, 400, 479, 400),
    (17, 200, 25, 206), (477, 851, 479, 853), (0, 0, 479, 1),
    (20, 30, 19, 30), (20, 30, 25, 29),
)


class FlushReplay(SetupReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.pixel_offsets = set()

    def code(self, u, pc, size, data):
        if pc == self.stop:
            u.emu_stop()
            return
        if 0x800115F4 <= pc < 0x8001165C or 0x80025C7C <= pc < 0x80025C94:
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if PANEL_FRAME <= address < PANEL_FRAME + FRAME_BYTES:
            assert u.reg_read(UC_ARM_REG_PC) == 0x80011634
            assert size == 2 and address % 2 == 0 and address + size <= PANEL_FRAME + FRAME_BYTES
            self.pixel_offsets.add((address - PANEL_FRAME) // 2)
            return
        super().write(u, access, address, size, value, data)

    def run_flush(self):
        self.execute(0x8003B080, 0x80025AC8)
        callback = self.word(DRIVER + 0x14)
        assert callback == 0x800115F4
        cases = []
        initial = b"\xA5\x5A" * (WIDTH * HEIGHT)
        for source in (FRAME1, FRAME2):
            for bounds in RECTANGLES:
                left, top, right, bottom = bounds
                count = max(0, right - left + 1) * max(0, bottom - top + 1)
                pixels = [((i * 173) ^ 0xF386) & 0xFFFF for i in range(max(1, count))]
                src = struct.pack(f"<{len(pixels)}H", *pixels)
                self.u.mem_write(source, src)
                self.u.mem_write(PANEL_FRAME, initial)
                self.u.mem_write(LAYER, struct.pack("<4h", *bounds))
                self.put(BUFFERS + 0x10, 1)
                self.put(BUFFERS + 0x14, 1)
                self.pixel_offsets = set()
                self.execute(callback, RETURN, ((UC_ARM_REG_R0, DRIVER),
                                                (UC_ARM_REG_R1, LAYER), (UC_ARM_REG_R2, source)))
                assert self.u.reg_read(UC_ARM_REG_SP) == STACK
                assert self.word(BUFFERS + 0x10) == self.word(BUFFERS + 0x14) == 0
                expected = bytearray(initial)
                expected_offsets = set()
                index = 0
                for y in range(top, bottom + 1):
                    for x in range(left, right + 1):
                        offset = y * WIDTH + x
                        expected_offsets.add(offset)
                        expected[2 * offset:2 * offset + 2] = src[2 * index:2 * index + 2]
                        index += 1
                actual = bytes(self.u.mem_read(PANEL_FRAME, FRAME_BYTES))
                assert actual == expected and self.pixel_offsets == expected_offsets
                assert bytes(self.u.mem_read(source, len(src))) == src
                cases.append(dict(source=hex(source), rectangle=bounds, pixels_copied=count,
                                  completion_flags=[0, 0], frame_sha256=hashlib.sha256(actual).hexdigest(),
                                  outside_pixels_unchanged=WIDTH * HEIGHT - count))
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
        replay = FlushReplay(raw)
        cases = replay.run_flush()
        observations.append((cases, replay.coverage))
    assert observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.native-display-flush.v1", images=images, cases=cases,
                  native_driver=hex(DRIVER), flush_callback="0x800115f4",
                  panel_buffer=hex(PANEL_FRAME), panel_dimensions=[WIDTH, HEIGHT],
                  instruction_bytes={hex(pc): word for pc, word in sorted(coverage.items())},
                  limits=["The native callback copies RGB565 rows with stride 480 and calls original completion.",
                          "Native initialization derives the source buffers, callback and panel buffer address.",
                          "Panel hardware setup and allocations are modeled. Source pixels and rectangles are fixtures.",
                          "Valid rectangles and inverted-axis no-op cases are tested. Caller clipping remains open.",
                          "Rotation, scheduler-driven refresh and physical LCD output and timing remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 32 native display flush cases across both factory images")


if __name__ == "__main__":
    main()
