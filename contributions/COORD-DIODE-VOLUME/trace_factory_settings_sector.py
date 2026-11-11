"""Execute original settings sector and page-write paths with an in-memory flash model."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_factory_settings_roundtrip import BASE, FLASH_OFFSET, READ, RECORD_SIZE, SETTING, WRITE, SettingsReplay
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3

SECTOR_SIZE, PAGE_SIZE = 4096, 256
SCRATCH, ADDRESS_MODE = 0x805B421C, 0x805ABBB0
PROGRAM, TRANSFER = 0x80006598, 0x8005A7B0
FLASH_LEAVES = {
    0x80006228: (0x80006474, 0x80006618),
    0x800062EC: (0x8000647C, 0x800064A8, 0x80006620, 0x80006670),
    0x8005A790: (0x80006484, 0x80006628),
    0x8005A698: (0x800064A0, 0x80006668),
}


class SectorReplay(SettingsReplay):
    def __init__(self, raw, needs_erase, four_bytes):
        super().__init__(raw)
        self.width = 4 if four_bytes else 3
        initial = bytearray((i * 29 + 17) & 0xFF for i in range(SECTOR_SIZE))
        if not needs_erase:
            initial[:RECORD_SIZE] = b"\xFF" * RECORD_SIZE
        self.initial = bytes(initial)
        self.sector = bytearray(initial)
        self.program_header = None
        self.sector_reads, self.erase_commands, self.page_writes, self.program_calls = [], [], [], []
        self.put(ADDRESS_MODE, int(four_bytes))

    def accept_program_header(self, payload):
        self.program_header = payload
        return len(payload)

    def code(self, u, pc, size, data):
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if self.phase == "dispatch":
            if pc == WRITE:
                assert (r0, r1, r2, r3, lr) == (0, SETTING, FLASH_OFFSET, RECORD_SIZE, 0x8000832C)
                self.storage_record = bytes(u.mem_read(r1, r3))
                self.saved.append([hex(r2), r3, hashlib.sha256(self.storage_record).hexdigest()])
            if pc == READ:
                assert (r0, r1, r2, r3, lr) == (0, FLASH_OFFSET, SCRATCH, SECTOR_SIZE, 0x800063D8)
                u.mem_write(r2, bytes(self.sector))
                self.sector_reads.append([hex(r1), r3])
                self.return_leaf(u, lr, 0)
                return
            if pc in FLASH_LEAVES:
                assert r0 == 0 and lr in FLASH_LEAVES[pc], (hex(pc), hex(lr))
                self.return_leaf(u, lr, 0)
                return
            if pc == TRANSFER:
                assert (r0, r2) == (0, 0) and lr in (0x80006498, 0x80006644, 0x80006660)
                payload = bytes(u.mem_read(r1, r3))
                if lr == 0x80006498:
                    opcode = 0x21 if self.width == 4 else 0x20
                    assert payload == bytes((opcode,)) + FLASH_OFFSET.to_bytes(self.width, "big")
                    self.erase_commands.append(payload.hex())
                    self.sector[:] = b"\xFF" * SECTOR_SIZE
                elif lr == 0x80006644:
                    opcode = 0x12 if self.width == 4 else 2
                    assert r3 == self.width + 1 and payload[0] == opcode and self.program_header is None
                    self.return_leaf(u, lr, self.accept_program_header(payload))
                    return
                else:
                    assert self.program_header is not None and 0 < r3 <= PAGE_SIZE
                    address = int.from_bytes(self.program_header[1:], "big")
                    offset = address - FLASH_OFFSET
                    assert 0 <= offset <= SECTOR_SIZE - r3 and address % PAGE_SIZE + r3 <= PAGE_SIZE
                    for i, value in enumerate(payload, offset):
                        self.sector[i] &= value
                    self.page_writes.append([self.program_header.hex(), r3, hashlib.sha256(payload).hexdigest()])
                    self.program_header = None
                self.return_leaf(u, lr, r3)
                return
            if pc == PROGRAM:
                assert r0 == 0 and r2 == FLASH_OFFSET
                assert (lr, r1, r3) in ((0x80006508, SCRATCH, SECTOR_SIZE), (0x80006544, SETTING, RECORD_SIZE))
                self.program_calls.append([hex(lr), hex(r2), r3])
            if WRITE <= pc < 0x80006590 or PROGRAM <= pc < 0x800066E4:
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
                return
        if self.phase == "load" and pc == READ:
            assert bytes(self.sector[:RECORD_SIZE]) == self.storage_record
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if SCRATCH <= address < SCRATCH + SECTOR_SIZE:
            assert self.phase == "dispatch" and size == 1 and u.reg_read(UC_ARM_REG_PC) == 0x800064D0
            return
        super().write(u, access, address, size, value, data)

    def run_sector(self, flags, needs_erase):
        result = self.roundtrip(flags, 1)
        assert self.program_header is None
        assert self.sector_reads == [[hex(FLASH_OFFSET), SECTOR_SIZE]]
        assert bytes(self.sector[RECORD_SIZE:]) == self.initial[RECORD_SIZE:]
        if needs_erase:
            assert len(self.erase_commands) == 1 and len(self.page_writes) == SECTOR_SIZE // PAGE_SIZE
            assert self.program_calls == [["0x80006508", hex(FLASH_OFFSET), SECTOR_SIZE]]
            assert all(n == PAGE_SIZE for _, n, _ in self.page_writes)
        else:
            assert not self.erase_commands and len(self.page_writes) == 1
            assert self.program_calls == [["0x80006544", hex(FLASH_OFFSET), RECORD_SIZE]]
            assert self.page_writes[0][1] == RECORD_SIZE
        return dict(**result, address_bytes=self.width, prefix_initially_blank=not needs_erase,
                    original_read_sector=self.sector_reads, erase_commands=self.erase_commands,
                    page_programs=self.page_writes, adjacent_bytes_preserved=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        coverage, cases = {}, []
        for flags, needs_erase, four_bytes in product((0, 1), (False, True), (False, True)):
            replay = SectorReplay(raw, needs_erase, four_bytes)
            cases.append(replay.run_sector(flags, needs_erase))
            coverage.update(replay.coverage)
        images[item["version"]] = digest
        observations.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.factory-settings-sector.v1", images=images, **observations[0], limits=[
        "The original settings event, CRC, sector selection, scratch merge and page-program wrapper execute on both original images.",
        "Flash read, write-enable, busy wait, transfer and select boundaries are modeled in memory. Synthetic data covers an erased record prefix and a non-erased prefix.",
        "The original factory flash algorithms are observed without USB or physical hardware. Flash failure handling and a safe independent persistent volume field are outside this test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 factory settings sector cases per image, 16 total")


if __name__ == "__main__":
    main()
