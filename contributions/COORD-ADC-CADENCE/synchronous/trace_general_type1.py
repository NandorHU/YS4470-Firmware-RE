"""Execute original general type-1 control records with independent ACK outcomes."""

import argparse
import json
import struct
from itertools import product
from pathlib import Path

from trace_deferred_producers import CTRL, HELPER, QUEUE, SERVICE, SELECTION, sha
from trace_extended_status import FLAG, STATUS, ExtendedReplay
from unicorn.arm_const import UC_ARM_REG_R0

PRODUCERS = (
    (0x8000E2C4, 0x8000E2DC, 9),
    (0x8000E354, 0x8000E36C, 0x0C),
    (0x8000E3DC, 0x8000E3F4, 0x0F),
    (0x8000E468, 0x8000E480, 0x0F),
)
RETURN_SITES = (0x80003E98, 0x80003EA8, 0x80003EB0)
FRAMES = {9: b"\x58\x03\x5b", 0x0C: b"\x58\x07\x5f", 0x0F: b"\x58\x0b\x63",
          0x19: b"\x5a\x5a", 0x26: b"\xc0\x00\xc0"}


class GeneralType1Replay(ExtendedReplay):
    def code(self, u, pc, size, data):
        if not self.in_isr:
            if pc == HELPER:
                self.entry_words.append((self.rd(STATUS), self.rd(FLAG)))
            if pc in RETURN_SITES:
                self.helper_returns.append(u.reg_read(UC_ARM_REG_R0))
        super().code(u, pc, size, data)

    def replay_general(self, producer, acknowledgements):
        self.reset()
        self.start, self.callsite, command = producer
        expected_ids = (0x26, command, 0x19)
        self.ack_packets = {cmd: FRAMES[cmd][:1] if ack else b""
                            for cmd, ack in zip(expected_ids, acknowledgements)}
        self.delivered = {}
        self.queued = self.record = self.helper_result = self.producer_args = None
        self.helper_return = RETURN_SITES[0]
        self.handler_entries = 0
        self.sleeps, self.receives, self.pending_writes, self.entry_words = [], [], [], []
        self.helper_entries, self.helper_returns, self.status_writes, self.gpio_writes = [], [], [], []
        self.put(CTRL + 4, QUEUE)
        self.put(STATUS, 0x99)
        self.put(FLAG, 0x99)
        self.u.mem_write(0x10010000, bytes(0x10000))
        self.invoke(self.start)
        assert self.producer_args == (1, command, 0x19)
        assert self.record[:6] == struct.pack("<IBB", 1, command, 0x19)
        assert bytes(self.u.mem_read(SELECTION, 2)) == bytes((command, 0x19))
        self.invoke(SERVICE)

        assert self.handler_entries == 1 and self.receives == [True, False]
        assert self.pending_writes == [(0x80005BDC, 1), (0x80005CEC, 0)]
        assert self.helper_entries == list(zip(expected_ids, RETURN_SITES))
        assert self.helper_returns == [int(ack) for ack in acknowledgements]
        assert self.entry_words == [(0, 0)] * 3
        assert self.status_writes == [
            (0x80003E58, FLAG, 1), (0x80003E60, STATUS, 0),
            (0x80003E90, FLAG, 0), (0x80003EB0, FLAG, 0),
        ]
        assert self.rd(STATUS) == self.rd(FLAG) == 0
        expected_sleeps = [1] * (0 if acknowledgements[0] else 1000) + [600]
        for ack in acknowledgements[1:]:
            expected_sleeps += [1] * (0 if ack else 1000)
        assert self.sleeps == expected_sleeps + [1]
        wire = b"".join(FRAMES[cmd] * (1 if ack else 2)
                        for cmd, ack in zip(expected_ids, acknowledgements))
        assert bytes(self.wire) == wire
        assert self.rd(0x01C208C4) & 0xC == 0
        return dict(producer=hex(self.callsite), record_prefix=self.record[:6].hex(),
                    helper_ids=[hex(cmd) for cmd in expected_ids], helper_results=self.helper_returns,
                    status_words_at_helper_entries=self.entry_words, wire_hex=wire.hex(),
                    requested_sleep_calls=len(self.sleeps))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    repo = here.parents[2]
    manifest = json.loads((repo / "original-firmware/manifest.json").read_text())
    versions, results = [], []
    for item in manifest["images"]:
        raw = (repo / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        emulator = GeneralType1Replay(raw)
        cases = [emulator.replay_general(producer, acks) for producer in PRODUCERS
                 for acks in product((False, True), repeat=3)]
        versions.append(dict(version=item["version"], sha256=item["sha256"], cases=len(cases)))
        instructions = {hex(pc): value for pc, value in sorted(emulator.coverage.items())}
        results.append((cases, instructions))
    assert results[0] == results[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.general-type1.v1", versions=versions,
        source_sha256=sha(Path(__file__).read_bytes()),
        reused_sources_sha256={name: sha((here / name).read_bytes())
                               for name in ("trace_extended_status.py", "trace_deferred_producers.py",
                                            "../uart/trace_uart_correlation.py")},
        cases_identical_across_versions=results[0][0], instruction_bytes=results[0][1],
        scope="Original caller suffix after queue drain, modeled queue/sleep/UART arrival, original helper and ISR. No peer or concurrency claim.",
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS", sum(v["cases"] for v in versions), "general type-1 cases")


if __name__ == "__main__":
    main()
