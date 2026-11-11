"""Replay normal mode-1 USB RX reports through the original FIFO and echo path."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_secondary_channel1 import FIFO, INDEX, INITIAL_INDEX, LOG, TXCSR, USB, reference_events
from trace_secondary_usb_irq import BASE, BUSY, BUS_STATUS, IRQ, IRQ_LOG_RETURNS, MODE, RX_STATUS, Replay, STACK
from trace_secondary_usb_lifecycle import CHUNK, READY_A, READY_B, SENDER_WINDOWS
from unicorn import UC_HOOK_MEM_READ
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1

RX_ENDPOINT = 2
RX_FIFO, RXCSR, RXCOUNT = USB + RX_ENDPOINT * 4, USB + 0x86, USB + 0x88
RX_SIZE, RX_BUFFER, RECORD = 0x805AAC5C, 0x805AC5E0, 0x805AC640
RX_HANDLER, APP_RX, ECHO_BUILDER, SUBMIT = 0x800603F4, 0x8005E750, 0x8005F0EC, 0x80060CCC
RX_WINDOWS = (
    (RX_HANDLER, 0x800604DC), (0x800606E0, 0x800606EC), (APP_RX, 0x8005E89C),
    (ECHO_BUILDER, 0x8005F1A4), (0x80007770, 0x800077A4),
    (0x80007B64, 0x80007BE0), (0x800077F0, 0x80007858), (0x80000B0C, 0x80000BA8),
)
RX_LOG_RETURNS = (0x80060408, 0x80060468, 0x8005FC48)


class RxReplay(Replay):
    def __init__(self, raw, payload, packet_ready, busy):
        super().__init__(raw)
        self.payload = payload
        self.offset = 0
        self.reads, self.rx_calls, self.echo_calls, self.tx_events = [], [], [], []
        self.put(MODE, 1)
        self.put(BUSY, int(busy))
        self.put(CHUNK, 64, 4)
        self.put(READY_A, 0, 4)
        self.put(READY_B, 0, 4)
        self.put(RX_SIZE, 0xA5A5A5A5, 4)
        self.u.mem_map(RX_BUFFER & ~0xFFF, 0x1000)
        self.u.mem_write(RX_BUFFER, b"\xA5" * 64)
        self.u.mem_write(RECORD, b"\x5A" * 61)
        self.put(INDEX, INITIAL_INDEX)
        self.put(RX_STATUS, 1 << RX_ENDPOINT, 2)
        self.put(RXCSR, 0x0D if packet_ready else 0, 2)
        self.put(RXCOUNT, len(payload), 2)
        self.put(TXCSR, 4, 2)
        self.u.hook_add(UC_HOOK_MEM_READ, self.read_mmio, begin=USB, end=USB + 0xFFF)

    def code(self, u, pc, size, data):
        if pc == LOG:
            lr = u.reg_read(UC_ARM_REG_LR)
            assert lr in (*IRQ_LOG_RETURNS, *RX_LOG_RETURNS), hex(lr)
            self.logs.append(hex(lr))
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if any(lo <= pc < hi for lo, hi in (*RX_WINDOWS, *SENDER_WINDOWS)):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
            if pc == APP_RX:
                assert (u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)) == (RX_BUFFER, len(self.payload))
                self.rx_calls.append(bytes(u.mem_read(RX_BUFFER, len(self.payload))).hex())
            if pc == SUBMIT:
                start, length = u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)
                assert length == 64 and u.reg_read(UC_ARM_REG_LR) == 0x8005F198
                self.echo_calls.append(bytes(u.mem_read(start, length)).hex())
            return
        super().code(u, pc, size, data)

    def read_mmio(self, u, _access, address, size, _value, _data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if address == RX_FIFO:
            assert self.get(INDEX) == RX_ENDPOINT and (pc, size) in ((0x80007BAC, 4), (0x80007BC4, 1))
            part = self.payload[self.offset:self.offset + size]
            assert len(part) == size
            u.mem_write(address, part)
            self.offset += size
            self.reads.append([hex(address), size, part.hex()])
            return
        assert (pc, address, size) in (
            (0x800079D4, INDEX, 1), (0x80007B20, BUS_STATUS, 1),
            (0x80007B00, USB + 0x44, 2), (0x80007B0C, RX_STATUS, 2),
            (0x80007758, RXCSR, 2), (0x8000778C, RXCSR, 2), (0x80007B88, RXCOUNT, 2),
            (0x80007818, RXCSR, 2), (0x800077C0, TXCSR, 2), (0x800078DC, TXCSR, 2),
        ), (hex(pc), hex(address), size)
        if address in (RXCSR, RXCOUNT):
            assert self.get(INDEX) == RX_ENDPOINT
        if address == TXCSR:
            assert self.get(INDEX) == 1

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if STACK - 0x300 <= address and address + size <= STACK:
            return
        if RX_BUFFER <= address and address + size <= RX_BUFFER + 64:
            assert pc in (0x80007BB4, 0x80007BCC)
            return
        if RECORD <= address and address + size <= RECORD + 61:
            assert pc in (0x8005E844, 0x8005E850) or 0x800009C4 <= pc < 0x80000BA8
            return
        if address in (RX_SIZE, READY_A, READY_B, BUSY):
            assert (pc, address, size) in ((0x80060488, RX_SIZE, 4), (0x8005E760, READY_A, 4),
                                           (0x8005E76C, READY_B, 4), (0x80060D48, BUSY, 1))
            self.stores.append([hex(pc), hex(address), value])
            return
        if address in (RX_STATUS, RXCSR):
            assert (pc, size, value) == ((0x80007A34, 2, 1 << RX_ENDPOINT) if address == RX_STATUS
                                         else (0x80007820, 2, 0))
            self.mmio.append([hex(address), value])
            return
        if address in (FIFO, TXCSR):
            assert self.get(INDEX) == 1
            if address == FIFO:
                assert (pc, size) in ((0x80007C58, 4), (0x80007C70, 1))
                self.tx_events.append(["fifo", size, value.to_bytes(size, "little").hex()])
            else:
                assert (pc, size, value) == (0x800078B4, 2, 1)
                self.tx_events.append(["txcsr", value])
            return
        if address == INDEX and pc == 0x80007BE4 and (
            value == 1 or self.get(INDEX) == 1 and value == RX_ENDPOINT
        ):
            self.tx_events.append(["index", value])
        super().write(u, access, address, size, value, data)


def run_case(raw, variant, packet_ready, busy):
    record = bytes(((0x30 + variant), (0x40 + variant))) + bytes((i + variant) & 0x7F for i in range(59))
    payload = bytes((0, 3, 64)) + record
    replay = RxReplay(raw, payload, packet_ready, busy)
    replay.invoke(IRQ)
    initial_ack = [[hex(BUS_STATUS), value] for value in (0x80, 0x40, 0x10, 8)]
    initial_ack.extend([[hex(RX_STATUS), 1 << RX_ENDPOINT], [hex(INDEX), RX_ENDPOINT]])
    assert replay.get(INDEX) == INITIAL_INDEX
    assert replay.get(BUSY) == int(busy or packet_ready)
    if packet_ready:
        assert replay.offset == 64 and replay.rx_calls == [payload.hex()]
        assert replay.echo_calls == [payload.hex()]
        assert bytes(replay.u.mem_read(RECORD, 61)) == record
        assert bytes(replay.u.mem_read(RX_BUFFER, 64)) == payload
        expected_stores = [["0x80060488", hex(RX_SIZE), 64],
                           ["0x8005e760", hex(READY_A), 1], ["0x8005e76c", hex(READY_B), 1]]
        expected_tx = [] if busy else reference_events(payload, [64])
        if not busy:
            expected_tx[-1] = ["index", RX_ENDPOINT]
            initial_ack.extend([[hex(INDEX), 1], [hex(INDEX), RX_ENDPOINT]])
            expected_stores.append(["0x80060d48", hex(BUSY), 1])
        assert replay.tx_events == expected_tx
        assert replay.stores == expected_stores
        initial_ack.append([hex(RXCSR), 0])
    else:
        assert not any((replay.offset, replay.rx_calls, replay.echo_calls, replay.tx_events, replay.stores))
        assert bytes(replay.u.mem_read(RECORD, 61)) == b"\x5A" * 61
        assert bytes(replay.u.mem_read(RX_BUFFER, 64)) == b"\xA5" * 64
    assert replay.mmio == initial_ack + [[hex(INDEX), INITIAL_INDEX], [hex(INDEX), INITIAL_INDEX]]
    return dict(variant=variant, packet_ready=packet_ready, busy_before=busy,
                busy_after=replay.get(BUSY), fifo_reads=replay.reads, tx_events=replay.tx_events,
                delivered_reports=replay.rx_calls, echoed_frames=replay.echo_calls, **replay.report())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, results = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        results.append([run_case(raw, *case) for case in product((0, 1), (False, True), (False, True))])
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.secondary-usb-rx.v1", images=images, cases=results[0], limits=[
        "The original USB IRQ handler is invoked directly with modeled endpoint-2 RX interrupt status. The harness provides a normal-size 64-byte type-3 report or keeps RX packet-ready clear.",
        "Original RX FIFO copy, report processing, guard-word writes and echo builder execute. With the busy gate clear, the original sender writes the echo to the modeled channel-1 FIFO. Log calls are modeled.",
        "Only mode 1, type 3 and the indicated ready and busy states are covered. Physical USB delivery and application meaning of the record are outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 original USB RX/echo cases per factory image, 16 total")


if __name__ == "__main__":
    main()
