"""Execute factory display setup and the original refresh-to-buffer binding."""

import argparse
import hashlib
import json
from pathlib import Path
import struct

from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE, UC_HOOK_MEM_WRITE
from unicorn.arm_const import (
    UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R8, UC_ARM_REG_R9, UC_ARM_REG_SP,
)

BASE = 0x7FFFFFE0
GLOBAL = 0x805ABC40
DRIVER, BUFFERS = 0x80B45B34, 0x809B5618
FRAME1, FRAME2, PANEL_FRAME = 0x809B5634, 0x80A7D8B4, 0x80B45B84
DISPLAY, CONTEXT, LAYER = 0x11001000, 0x11002000, 0x11003000
RETURN, STACK = 0x11000000, 0x1100F000
WINDOWS = (
    (0x8003B080, 0x8003B0F8), (0x800259B4, 0x80025A54),
    (0x80025A5C, 0x80025AC8), (0x80029CC8, 0x80029D60),
    (0x80032E14, 0x80032EA4), (0x800442B0, 0x800442D0),
    (0x80026E60, 0x80026E70), (0x80029D9C, 0x80029E14),
    (0x8000B280, 0x8000B28C), (0x80025CE4, 0x80025D20),
)


class SetupReplay:
    def __init__(self, raw):
        self.u = u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        u.ctl_set_cpu_model(UC_CPU_ARM_926)
        u.mem_map(0x7FFFF000, 0x2001000)
        u.mem_write(BASE, raw)
        u.mem_map(RETURN, 0x10000)
        self.coverage, self.writes, self.hardware_calls = {}, [], []
        self.stop = 0x80025AC8
        u.hook_add(UC_HOOK_CODE, self.code)
        u.hook_add(UC_HOOK_MEM_WRITE, self.write)

    def word(self, address):
        return struct.unpack("<I", self.u.mem_read(address, 4))[0]

    def put(self, address, value):
        self.u.mem_write(address, struct.pack("<I", value))

    def code(self, u, pc, size, _):
        if pc == self.stop:
            u.emu_stop()
            return
        leaves = {0x80006B2C: None, 0x8000A9D8: DISPLAY, 0x80032800: CONTEXT}
        if pc in leaves:
            if pc == 0x80006B2C:
                self.hardware_calls.append([u.reg_read(r) for r in (
                    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)])
            elif pc == 0x80032800:
                assert u.reg_read(UC_ARM_REG_R0) == 0x58
            if leaves[pc] is not None:
                u.reg_write(UC_ARM_REG_R0, leaves[pc])
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        assert size == 4 and any(lo <= pc < hi for lo, hi in WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, _):
        allowed = (
            (STACK - 0x200, STACK), (DISPLAY, DISPLAY + 0x15C),
            (CONTEXT, CONTEXT + 0x58), (LAYER, LAYER + 0x2C),
            (DRIVER, DRIVER + 0x50), (BUFFERS, BUFFERS + 0x1C),
            (0x805ABE10, 0x805ABE14), (FRAME1, FRAME1 + 0x200),
        )
        assert any(lo <= address and address + size <= hi for lo, hi in allowed), (hex(u.reg_read(UC_ARM_REG_PC)), hex(address))
        self.writes.append((hex(u.reg_read(UC_ARM_REG_PC)), hex(address), size, value))

    def execute(self, entry, stop, registers=()):
        self.stop = stop
        for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK),
                           (UC_ARM_REG_LR, RETURN), *registers):
            self.u.reg_write(reg, value)
        self.u.emu_start(entry, 0, count=10000)
        assert self.u.reg_read(UC_ARM_REG_PC) == stop

    def run(self):
        self.execute(0x8003B080, 0x80025AC8)
        assert self.hardware_calls == [[480, 854, PANEL_FRAME, 0]]
        assert struct.unpack("<2H", self.u.mem_read(DRIVER, 4)) == (480, 854)
        assert [self.word(BUFFERS + off) for off in (0, 4, 8, 12)] == [FRAME1, FRAME2, FRAME1, 96000]
        assert self.word(DRIVER + 0x10) == 0x413C
        assert self.word(DRIVER + 0x3C) == CONTEXT
        assert self.word(DRIVER + 0x40) == 0x80029CC8
        assert self.word(DRIVER + 0x14) == 0x800115F4
        assert self.word(DISPLAY) == DRIVER
        assert self.word(CONTEXT + 0x40) == 0x80029D9C
        assert self.word(CONTEXT + 0x54) == 0x80028A5C
        self.put(GLOBAL + 4, DISPLAY)
        self.execute(0x80025CE4, RETURN, ((UC_ARM_REG_R0, DISPLAY),))
        assert self.u.reg_read(UC_ARM_REG_R0) == 854
        cases = []
        for alpha_mode, top in ((0, 0), (0, 200), (1, 0), (1, 200)):
            self.u.mem_write(LAYER, bytes(0x2C))
            self.u.mem_write(LAYER, struct.pack("<4h", 0, 0, 853, 479))
            self.u.mem_write(LAYER + 8, struct.pack("<4h", 0, top, 853, top + 31))
            self.put(LAYER + 0x14, self.word(BUFFERS + 8))
            self.put(LAYER + 0x28, 64)
            self.u.mem_write(FRAME1, b"\xA5" * 128)
            self.execute(0x800442B0, 0x800442D0, (
                (UC_ARM_REG_R4, LAYER), (UC_ARM_REG_R8, CONTEXT), (UC_ARM_REG_R9, alpha_mode)))
            assert [self.word(CONTEXT + off) for off in (0, 4, 8)] == [FRAME1, LAYER + 8, LAYER + 8]
            assert self.word(DRIVER + 0x10) == (0x413C | (0x40 if alpha_mode else 0))
            assert self.word(LAYER + 0x28) == (64 | (0x80000000 if alpha_mode else 0))
            assert self.u.mem_read(FRAME1, 128) == (bytes(64) if alpha_mode else b"\xA5" * 64) + b"\xA5" * 64
            cases.append(dict(alpha_mode=alpha_mode, top=top,
                              buffer=hex(self.word(CONTEXT)), rectangle=list(struct.unpack("<4h", self.u.mem_read(LAYER + 8, 8))),
                              driver_flags=hex(self.word(DRIVER + 0x10)), clear_bytes=64 if alpha_mode else 0))
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
        assert len(raw) == item["size_bytes"] and digest == item["sha256"]
        images[item["version"]] = digest
        replay = SetupReplay(raw)
        cases = replay.run()
        observations.append((cases, replay.coverage, replay.writes))
    assert observations[0] == observations[1]
    cases, coverage, writes = observations[0]
    report = dict(schema="ys4470.display-refresh-setup.v1", images=images, cases=cases,
                  native_driver=hex(DRIVER), native_buffer_descriptor=hex(BUFFERS),
                  native_physical_dimensions=[480, 854], native_logical_horizontal_resolution=854,
                  native_buffer_capacity_pixels=96000, native_driver_flags="0x413c",
                  instruction_bytes={hex(pc): word for pc, word in sorted(coverage.items())},
                  writes=writes, limits=[
                      "Original display initialization and registration prefix execute through 0x80025ac4.",
                      "Panel hardware initialization and allocations are modeled.",
                      "Active-display selection, layer geometry, size and refresh entry registers are fixtures.",
                      "The native refresh window 0x800442b0..0x800442cc reaches original buffer initialization.",
                      "Full scheduler-driven refresh, live buffer contents and physical LCD transfer remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 2 native display setups and 8 refresh buffer bindings")


if __name__ == "__main__":
    main()
