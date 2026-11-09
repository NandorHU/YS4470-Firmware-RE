"""Execute the original dynamic type-2 producer and exhaust the dispatcher byte."""

import argparse
import json
import struct
from itertools import product
from pathlib import Path

from trace_deferred_measurement import DispatcherReplay
from trace_deferred_producers import BASE, CTRL, FSM, PRODUCER, SERVICE
from trace_uart_correlation import RET, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

UI = 0x805ABEFC
WIDGET = 0x10017000
ADJACENT_WIDGET = 0x10017040
OTHER_WIDGET = 0x10017080
TIMER = 0x10017100
DRAIN = 0x10017200
ENTRY = 0x8000D294
ADJACENT = 0x8000D648
FRAMES = {
    9: bytes.fromhex("58035b"), 0x0A: bytes.fromhex("58045c"),
    0x0C: bytes.fromhex("58075f"), 0x22: bytes.fromhex("68076f"),
    0x19: bytes.fromhex("5a5a"), 0x1D: bytes.fromhex("6060"),
    **{cmd: bytes((0x59, cmd - 0x13, 0x59 + cmd - 0x13)) for cmd in range(0x13, 0x19)},
}


class DynamicReplay(DispatcherReplay):
    def code(self, u, pc, size, data):
        r0, r1, r2, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR,
        ))
        if pc in (0x80003D74, 0x80006778) and lr in (
            0x8000D33C, 0x8000D378, 0x8000D354, 0x8000D3A0, 0x8000D6A0, 0x8000D6D4, 0x8000D71C,
        ):
            self.ui_calls.append((hex(pc), hex(lr)))
        if pc == 0x80042AA0 and r0 == 68:
            assert lr == 0x80003D88
            u.reg_write(UC_ARM_REG_R0, DRAIN)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc in (0x80060F5C, 0x8003A718, 0x80006E4C):
            if pc == 0x80060F5C:
                assert r0 == DRAIN
            elif pc == 0x8003A718:
                assert r0 in (WIDGET, ADJACENT_WIDGET, OTHER_WIDGET) and r2 == 0
                self.style_values.append(r1)
            else:
                assert (r0, r1, lr) == (5, 1, RET)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if any(lo <= pc < hi for lo, hi in (
            (ENTRY, 0x8000D3B0), (0x80003D74, 0x80003DB8), (0x80024CA4, 0x80024CD8),
            (ADJACENT, 0x8000D72C), (0x8000299C, 0x800029D4),
            (0x80040B4C, 0x80040B58), (0x80040B78, 0x80040B8C),
        )):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and address in (UI + 1, UI + 2, UI + 7, UI + 8):
            assert size == 1
            return
        super().memory(u, access, address, size, value, data)

    def prepare(self):
        self.reset()
        self.configuring = False
        self.enqueued, self.receives, self.delays, self.handled = [], [], [], []
        self.producer_returns, self.dispatch_records, self.builder_calls, self.sent = [], [], [], []
        self.ui_calls, self.style_values = [], []
        self.u.mem_write(0x10010000, bytes(0x10000))
        self.put(0x805ABEB8, TIMER)
        self.put(TIMER, 777)
        self.put(0x805AC380, WIDGET)
        self.put(0x805AC368, ADJACENT_WIDGET)
        self.put(0x805AC360, OTHER_WIDGET)
        self.invoke(0x800418A4)

    def verify_dispatch(self, primary, secondary):
        expected = (primary, secondary, 0x1D)
        self.invoke(SERVICE)
        assert self.dispatch_records == [self.enqueued[-1][:6].hex()] and not self.handled
        assert self.builder_calls == [(3, expected, 0x80004480)]
        assert self.rd(CTRL + 8) == primary and self.byte(CTRL + 1) == 2
        assert self.sent == [primary] and bytes(self.wire) == FRAMES[primary]
        return expected

    def progress(self, expected):
        delivered = 0
        for tick in range(1, 320):
            self.now = tick
            if delivered < len(self.sent):
                cmd = self.sent[-1]
                for byte in (b"\x60\x32\x00\x00\x03" if cmd == 0x1D else FRAMES[cmd][:1]):
                    self.receive(byte)
                delivered += 1
            self.step(tick)
            if self.byte(FSM + 0x34) == 0:
                break
        assert self.byte(FSM + 0x34) == 0 and tuple(self.sent) == expected
        assert bytes(self.wire) == b"".join(FRAMES[cmd] for cmd in expected)
        assert self.byte(CTRL + 1) == 1

    def native_case(self, mode, aux, latch):
        self.prepare()
        self.u.mem_write(UI, bytes((mode, aux, latch, 0, 0, 0, 0, 0x91, 0x92)))
        self.invoke(ENTRY)
        assert self.byte(UI + 2) == 1 - latch and len(self.style_values) == 1
        expected = None
        if mode == 1 and latch:
            expected = (0x0C, 0x15 if aux == 1 else 0x19)
        elif mode == 1 and aux == 1:
            expected = (0x22, 0x15)
        if expected:
            assert self.rd(TIMER) == 100 and self.receives == [0]
            assert tuple(self.u.mem_read(UI + 7, 2)) == expected
            assert len(self.enqueued) == 1 and self.enqueued[0][:6] == struct.pack("<IBB", 2, *expected)
            assert len(self.ui_calls) == 2
            sequence = self.verify_dispatch(*expected)
            self.progress(sequence)
        else:
            assert self.rd(TIMER) == 777 and not self.enqueued and not self.ui_calls
            assert tuple(self.u.mem_read(UI + 7, 2)) == (0x91, 0x92)
        return dict(initial_mode=mode, initial_aux=aux, initial_latch=latch, final_latch=1-latch,
                    queue_record_prefix=self.enqueued[0][:6].hex() if self.enqueued else None,
                    call_sites=self.ui_calls, commands_sent=self.sent, wire_hex=bytes(self.wire).hex())

    def clamp_case(self, raw):
        self.prepare()
        assert self.invoke(PRODUCER, (2, 0x0C, raw)) == 1
        assert self.enqueued[0][:6] == struct.pack("<IBB", 2, 0x0C, raw)
        selected = raw if 0x13 <= raw <= 0x18 else 0x19
        self.verify_dispatch(0x0C, selected)
        self.receive(0x58)
        assert self.step(1) == 4
        assert self.step(50) == 4 and self.sent == [0x0C]
        assert self.step(51) == 1
        assert self.step(52) == 2 and self.sent == [0x0C, selected]
        assert bytes(self.wire) == FRAMES[0x0C] + FRAMES[selected]
        return [raw, selected, FRAMES[selected].hex()]

    def adjacent_case(self, primary, chain):
        self.prepare()
        self.u.mem_write(UI, bytes((1, 0, 1, 0, 0, 0, 0, primary, 0x92)))
        self.invoke(ADJACENT)
        assert self.byte(UI + 1) == 1 and self.rd(TIMER) == 100 and self.receives == [0]
        expected = None
        if primary in (9, 0x0A):
            expected = (primary, 0x13)
        elif primary in (0x0C, 0x22):
            expected = (0x0C, 0x15)
        assert self.byte(UI + 2) == int(primary not in (0x0C, 0x22))
        assert len(self.enqueued) == int(expected is not None)
        if expected:
            assert self.enqueued[0][:6] == struct.pack("<IBB", 2, *expected)
        if chain:
            self.invoke(ENTRY)
            assert self.receives == ([0, 1, 0] if expected else [0, 0])
            expected = (0x22 if primary in (0x0C, 0x22) else 0x0C, 0x15)
            assert self.enqueued[-1][:6] == struct.pack("<IBB", 2, *expected)
        if expected:
            sequence = self.verify_dispatch(*expected)
            self.progress(sequence)
        return dict(initial_primary=primary, followed_by_second_callback=chain,
                    ui_after=list(self.u.mem_read(UI, 9)), calls=self.ui_calls,
                    queue_records=[item[:6].hex() for item in self.enqueued], receive_counts=self.receives,
                    commands_sent=self.sent, wire_hex=bytes(self.wire).hex())


def bindings(raw):
    rows = []
    for load, literal, call, callback in (
        (0x80051808, 0x80051998, 0x80051818, ADJACENT),
        (0x8005181C, 0x8005199C, 0x8005182C, ENTRY),
    ):
        word, = struct.unpack_from("<I", raw, load - BASE)
        assert word & 0xFFFFF000 == 0xE59F1000 and load + 8 + (word & 0xFFF) == literal
        assert struct.unpack_from("<I", raw, literal - BASE)[0] == callback
        branch, = struct.unpack_from("<I", raw, call - BASE)
        assert branch >> 24 == 0xEB
        disp = (((branch & 0xFFFFFF) ^ 0x800000) - 0x800000) * 4
        assert call + 8 + disp == 0x800338DC
        rows.append(dict(callback=hex(callback), literal=hex(literal), registration_call=hex(call),
                         bytes=raw[load-BASE:call-BASE+4].hex()))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    results, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        m = DynamicReplay(raw)
        native = [m.native_case(*values) for values in product((0, 1, 2), (0, 1, 2), (0, 1))]
        clamp = [m.clamp_case(value) for value in range(256)]
        adjacent = [m.adjacent_case(primary, chain)
                    for primary, chain in product((9, 0x0A, 0x0C, 0x22, 0x0E), (False, True))]
        versions.append(dict(version=item["version"], input_sha256=item["sha256"],
                             callback_cases=len(native), clamp_cases=len(clamp), adjacent_cases=len(adjacent)))
        results.append((native, clamp, adjacent, bindings(raw),
                        {hex(pc): value for pc, value in sorted(m.coverage.items())}))
    assert results[0] == results[1]
    def source_hash(path):
        return sha(path.read_text(encoding="utf-8").encode("utf-8"))

    args.out.write_text(json.dumps(dict(
        schema="ys4470.dynamic-type2.v1", versions=versions, source_sha256=source_hash(Path(__file__)),
        source_hash_rule="UTF-8 source with LF line endings",
        reused_sources_sha256={name: source_hash(Path(__file__).parent / name)
                               for name in ("trace_deferred_measurement.py", "trace_type6_queue.py",
                                            "trace_deferred_producers.py", "../uart/trace_uart_correlation.py")},
        callback_cases=results[0][0], clamp_columns=["record_byte", "selected_descriptor", "wire_hex"],
        clamp_cases=results[0][1], adjacent_cases=results[0][2], static_button_bindings=results[0][3],
        instruction_bytes=results[0][4],
        limits=[
            "Original callback receives controlled UI states. Widget style, feedback and allocation are fixtures.",
            "Exhaustive clamp tests use host-supplied bytes at the original producer API and stop after the second send.",
            "Queue, dispatcher, builder, UART TX and RX ISR execute. Counter progression and replies are fixtures.",
        ],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS 36 callback cases, 20 adjacent/paired cases, and 512 exhaustive clamp/second-send cases")


if __name__ == "__main__":
    main()
