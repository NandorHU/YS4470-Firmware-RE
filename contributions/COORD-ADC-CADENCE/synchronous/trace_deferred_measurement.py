"""Execute original type-2/5 caller selection, real queue and measurement FSM."""

import argparse
import json
import struct
from pathlib import Path

from trace_deferred_producers import CTRL, DEFERRED, FSM, SERVICE
from trace_type6_queue import QUEUE, RealQueueReplay
from trace_uart_correlation import RESULT, RET, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

CHOICE = 0x805AC788
CALLS = {2: (0x8000D0CC, 0x0E, 0x19), 5: (0x8000D0A4, 0x22, 0x13)}
LISTS = {2: (0x0E, 0x19, 0x1D), 5: (0x0C, 0x22, 0x13, 0x1D)}
FRAMES = {
    0x0C: b"\x58\x07\x5f", 0x0E: b"\x58\x0a\x62", 0x13: b"\x59\x00\x59",
    0x19: b"\x5a\x5a", 0x1D: b"\x60\x60", 0x22: b"\x68\x07\x6f",
}


class DispatcherReplay(RealQueueReplay):
    def code(self, u, pc, size, data):
        if pc in (0x8000D0A4, 0x8000D0CC):
            self.producer_returns.append(pc)
            u.reg_write(UC_ARM_REG_PC, RET)
            return
        if 0x8000D084 <= pc <= 0x8000D0A0 or 0x8000D0BC <= pc <= 0x8000D0C8:
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        if pc == 0x80004390:
            assert self.byte(FSM + 0x34) == self.byte(CTRL) == 0
            record = bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), 68))
            assert record == bytes(u.mem_read(DEFERRED, 68)) == self.enqueued[-1]
            self.dispatch_records.append(record[:6].hex())
        if pc == 0x8000489C:
            mode, pointer, n, lr = (u.reg_read(r) for r in (
                UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR,
            ))
            assert n in (3, 4)
            self.builder_calls.append((mode, tuple(struct.unpack(f"<{n}I", u.mem_read(pointer, 4*n))), lr))
        if pc == 0x80005E84:
            self.sent.append(self.rd(FSM + 0x20))
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and address == CTRL + 8:
            assert size == 4 and u.reg_read(UC_ARM_REG_PC) in (0x800043E8, 0x80004464)
            return
        super().memory(u, access, address, size, value, data)

    def run_dispatch(self, settings, replies):
        self.reset()
        self.configuring = False
        self.enqueued, self.receives, self.delays, self.handled = [], [], [], []
        self.producer_returns, self.dispatch_records, self.builder_calls, self.sent = [], [], [], []
        self.u.mem_write(0x10010000, bytes(0x10000))
        self.invoke(0x800418A4)
        assert self.rd(CTRL + 4) == QUEUE
        expected_kinds = [5 if value == 1 else 2 for value in settings]
        for value, kind in zip(settings, expected_kinds):
            self.put(CHOICE, value)
            self.invoke(0x8000D084)
            return_site, primary, secondary = CALLS[kind]
            assert self.producer_returns[-1] == return_site
            assert self.enqueued[-1][:6] == struct.pack("<IBB", kind, primary, secondary)
            assert self.rd(QUEUE + 0x38) == len(self.enqueued)
        active = expected_kinds[-1]
        sequence = LISTS[active]
        self.invoke(SERVICE)
        assert self.rd(QUEUE + 0x38) == self.byte(CTRL) == 0
        assert self.receives == list(range(len(settings), -1, -1))
        assert self.dispatch_records == [self.enqueued[-1][:6].hex()] and not self.handled
        assert self.builder_calls == [(3, sequence, 0x80004480 if active == 2 else 0x80004414)]
        assert self.rd(CTRL + 8) == CALLS[active][1] and self.byte(CTRL + 1) == 2
        assert self.byte(FSM) == 2 and self.byte(FSM + 0x34) == 1 and self.sent == [sequence[0]]
        assert bytes(self.wire) == FRAMES[sequence[0]]
        delivered = []
        for tick in range(1, 400):
            self.now = tick
            if replies and len(delivered) < len(self.sent):
                cmd = self.sent[-1]
                assert self.byte(FSM) == (3 if cmd == 0x1D else 2)
                packet = b"\x60\x32\x00\x00\x03" if cmd == 0x1D else FRAMES[cmd][:1]
                for value in packet:
                    self.receive(value)
                delivered.append((cmd, packet.hex(), tick))
            self.step(tick)
            if self.byte(FSM + 0x34) == 0:
                break
        assert self.byte(FSM + 0x34) == 0
        sends = sequence if replies else (sequence[0], sequence[0])
        assert self.sent == list(sends)
        assert bytes(self.wire) == b"".join(FRAMES[cmd] for cmd in sends)
        assert self.byte(CTRL + 1) == (1 if replies else 2)
        assert self.rd(RESULT + 0x1C) == 0x7FFFFF
        parser_frames = [event["frame"] for event in self.events if event["kind"] == "parse"]
        assert parser_frames == (["6032000003"] if replies else [])
        return dict(settings=settings, record_types=expected_kinds, producer_returns=[hex(x) for x in self.producer_returns],
                    dispatch_records=self.dispatch_records, builder_calls=self.builder_calls,
                    wire_hex=bytes(self.wire).hex(), commands_sent=self.sent, reply_fixtures=delivered,
                    parser_frames=parser_frames, discard_after=self.byte(CTRL + 1), idle_model_tick=tick)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo / "original-firmware/manifest.json").read_text())
    rows, versions = [], []
    for item in manifest["images"]:
        raw = (repo / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        m = DispatcherReplay(raw)
        cases = [m.run_dispatch(settings, replies) for settings in ((0,), (1,), (2,), (0, 1), (1, 0))
                 for replies in (False, True)]
        rows.append((cases, {hex(pc): value for pc, value in sorted(m.coverage.items())}))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=len(cases)))
    assert rows[0] == rows[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.deferred-measurement.v1", source_sha256=sha(Path(__file__).read_bytes()),
        reused_sources_sha256={name: sha((Path(__file__).parent / name).read_bytes())
                               for name in ("trace_type6_queue.py", "trace_deferred_producers.py",
                                            "../uart/trace_uart_correlation.py")},
        versions=versions, shared_cases=rows[0][0], shared_instruction_bytes=rows[0][1],
        limits=[
            "Executes the original choice suffix after its queue-drain call; repeated choice calls model accumulated records.",
            "Original queue, dispatcher, builder, FSM, UART TX and RX ISR execute with fixture allocation, replies and ticks.",
            "A successful measurement frame consumes one discard slot. Physical timing and peer semantics remain open.",
        ],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS", sum(v["cases"] for v in versions), "deferred measurement cases")


if __name__ == "__main__":
    main()
