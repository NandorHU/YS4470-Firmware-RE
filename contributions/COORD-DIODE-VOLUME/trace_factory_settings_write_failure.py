"""Check the factory save result when the offline storage model returns a short header."""

import argparse
import hashlib
import json
import zlib
from itertools import product
from pathlib import Path

from trace_factory_settings_roundtrip import BASE, CRC_LENGTH, FLASH_OFFSET, RECORD_SIZE
from trace_factory_settings_sector import PAGE_SIZE, SECTOR_SIZE, SectorReplay


class FailureReplay(SectorReplay):
    def __init__(self, raw, needs_erase, four_bytes, rejected_page):
        super().__init__(raw, needs_erase, four_bytes)
        self.rejected_page = rejected_page
        self.header_attempts = []

    def accept_program_header(self, payload):
        address = int.from_bytes(payload[1:], "big")
        page = (address - FLASH_OFFSET) // PAGE_SIZE
        accepted = page != self.rejected_page
        self.header_attempts.append([hex(address), payload.hex(), accepted])
        if accepted:
            return super().accept_program_header(payload)
        return len(payload) - 1

    def run_failure(self, erase):
        normalized, record_before = self.save_event(1, 1)
        assert normalized == 1 and self.storage_record is not None
        crc = zlib.crc32(record_before[:CRC_LENGTH])
        assert self.storage_record == record_before[:CRC_LENGTH] + crc.to_bytes(4, "little")
        assert self.checksum_writes == [crc]
        assert self.logs == [["dispatch", "0x80008340"]]
        assert self.sector_reads == [[hex(FLASH_OFFSET), SECTOR_SIZE]]
        assert sum(not accepted for _, _, accepted in self.header_attempts) == 1
        assert self.program_header is None and not self.loaded

        expected = bytearray(self.initial)
        if erase:
            assert len(self.erase_commands) == 1
            assert len(self.header_attempts) == SECTOR_SIZE // PAGE_SIZE
            expected[:RECORD_SIZE] = self.storage_record
            start = self.rejected_page * PAGE_SIZE
            expected[start:start + PAGE_SIZE] = b"\xFF" * PAGE_SIZE
        else:
            assert not self.erase_commands
            assert len(self.header_attempts) == 1
        assert bytes(self.sector) == bytes(expected)
        assert len(self.page_writes) == (15 if erase else 0)
        assert (bytes(self.sector[:RECORD_SIZE]) == self.storage_record) == (self.rejected_page > 0)
        return dict(address_bytes=self.width, erase_path=erase, rejected_page=self.rejected_page,
                    header_attempts=self.header_attempts, program_payloads=len(self.page_writes),
                    read_count=len(self.sector_reads), completion_log=self.logs[0][1],
                    attempted_record_crc32=hex(crc), final_record_matches=self.rejected_page > 0,
                    modeled_sector_sha256=hashlib.sha256(self.sector).hexdigest())


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
        end = 0x80008340 - BASE + len("参数保存完成！\r\n".encode())
        assert raw[0x80008340 - BASE:end] == "参数保存完成！\r\n".encode()
        coverage, cases = {}, []
        for (erase, rejected_page), width in product(((False, 0), (True, 0), (True, 3)), (False, True)):
            replay = FailureReplay(raw, erase, width, rejected_page)
            cases.append(replay.run_failure(erase))
            coverage.update(replay.coverage)
        images[item["version"]] = digest
        observations.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.factory-settings-write-failure.v1", images=images, **observations[0], limits=[
        "The in-memory SPI boundary returns one fewer byte than requested for a page-program header. It supplies full lengths for other transfers.",
        "Original save and page-program code executes. A short header skips that payload in the model. No second sector read, retry of the short page, or change to the completion message occurs in these cases.",
        "These are controlled storage failure fixtures. The original lower-level hardware transfer and real-world failure rate remain outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 6 factory settings short-transfer cases per image, 12 total")


if __name__ == "__main__":
    main()
