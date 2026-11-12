"""Execute the original dirty-area splitter through each renderer dispatch."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R7, UC_ARM_REG_SP,
)

from trace_display_refresh_setup import (
    SetupReplay, BUFFERS, CONTEXT, DISPLAY, DRIVER, FRAME1, FRAME2, GLOBAL, RETURN, STACK,
)

RECTANGLES = ((0, 0, 853, 479), (0, 0, 0, 0), (17, 200, 25, 206),
              (0, 111, 853, 337), (852, 478, 853, 479))


class DirtyReplay(SetupReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.regions = []
        self.capacity = 96000

    def code(self, u, pc, size, data):
        if pc == 0x800430D0:
            assert u.reg_read(UC_ARM_REG_R0) == CONTEXT
            area = struct.unpack("<4h", u.mem_read(self.word(CONTEXT + 4), 8))
            assert self.word(CONTEXT + 8) == self.word(CONTEXT + 4)
            self.regions.append(dict(rectangle=list(area), source=hex(self.word(CONTEXT)),
                                     last=bool(self.word(BUFFERS + 0x18) & 2)))
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if pc == 0x800019D0:
            width = u.reg_read(UC_ARM_REG_R1)
            assert width > 0 and u.reg_read(UC_ARM_REG_R0) == self.capacity
            u.reg_write(UC_ARM_REG_R0, self.capacity // width)
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if 0x80043A58 <= pc < 0x80043D3C or 0x80025DD8 <= pc < 0x80025E14:
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def run_dirty(self):
        self.execute(0x8003B080, 0x80025AC8)
        assert self.word(DRIVER + 0x10) == 0x413C
        self.put(GLOBAL + 4, DISPLAY)
        cases = []
        for source in (FRAME1, FRAME2):
            for bounds in RECTANGLES:
                self.u.mem_write(DISPLAY + 0x30, struct.pack("<4h", *bounds))
                self.put(BUFFERS + 8, source)
                self.put(BUFFERS + 0x18, 1)
                self.stop = 0x80043D3C
                self.regions = []
                for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK - 0x80),
                                   (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_R0, DISPLAY),
                                   (UC_ARM_REG_R7, 0)):
                    self.u.reg_write(reg, value)
                self.u.emu_start(0x80043A58, 0, count=50000)
                assert self.u.reg_read(UC_ARM_REG_PC) == self.stop
                left, top, right, bottom = bounds
                width = right - left + 1
                rows = min(bottom - top + 1, self.capacity // width)
                expected = [[left, y, right, min(bottom, y + rows - 1)]
                            for y in range(top, bottom + 1, rows)]
                assert [r["rectangle"] for r in self.regions] == expected
                assert all(r["source"] == hex(source) for r in self.regions)
                assert [r["last"] for r in self.regions] == [False] * (len(expected) - 1) + [True]
                cases.append(dict(dirty_rectangle=bounds, buffer=hex(source), capacity_pixels=self.capacity,
                                  rows_per_chunk=rows, renderer_calls=self.regions))
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
        replay = DirtyReplay(raw)
        cases = replay.run_dirty()
        observations.append((cases, replay.coverage))
    assert observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.native-display-dirty-regions.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): word for pc, word in sorted(coverage.items())},
                  limits=["The original dirty-area path uses the native initialized 0x413c driver.",
                          "Dirty rectangles, active display, buffer selection and entry registers are seeded.",
                          "Display hardware, allocation, integer division and renderer 0x800430d0 are modeled.",
                          "Each callback records native buffer, rectangle and final-chunk flag.",
                          "Scheduler-driven dirty production, original object rendering and physical LCD timing remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 20 native dirty-area refresh schedules across both factory images")


if __name__ == "__main__":
    main()
