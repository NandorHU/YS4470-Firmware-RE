"""Replay the factory ARM926 channel-1 sender against a bounded USB register model."""

import argparse
import hashlib
import json
from pathlib import Path

from unicorn import UC_ARCH_ARM, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MODE_ARM, Uc
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_SP, UC_CPU_ARM_926,
)

BASE = 0x7FFFFFE0
SENDER = 0x8005FC08
LOG = 0x8004283C
CHANNEL_ENABLED, CHANNEL_LIMIT = 0x805AAC48, 0x805AAC68
USB = 0x01C13000
FIFO, INDEX, TXCSR = USB + 4, USB + 0x42, USB + 0x82
STACK, RETURN, PAYLOAD = 0x10013000, 0x10000000, 0x10010000
INITIAL_INDEX = 3
TIMEOUT_COUNT = 10_000_000
# Entry, post-guard and exit locations. The long timeout loop itself stays native
# and uninstrumented, with the modeled status held busy for every iteration.
MARKERS = (SENDER, 0x8005FC38, 0x8005FC64, 0x8005FC84, 0x8005FC9C, 0x8005FCBC,
           0x8005FCC8, 0x8005FCD8, 0x8005FCF0, 0x8005FD00, 0x800079D4, 0x80007BE4,
           0x80007C58, 0x80007C70, 0x800078DC, 0x800078E4)


class ChannelRegisters:
    """Model the indexed FIFO and status used by this particular channel."""

    def __init__(self, u, poll_schedule=None, initial_status=4):
        self.events = []
        self.polls = []
        self.schedule = iter(poll_schedule) if poll_schedule is not None else None
        u.mem_map(USB, 0x1000)
        u.mem_write(INDEX, bytes((INITIAL_INDEX,)))
        u.mem_write(TXCSR, initial_status.to_bytes(2, "little"))
        u.hook_add(UC_HOOK_MEM_WRITE, self.write, begin=USB, end=USB + 0xFFF)
        if self.schedule is not None:
            u.hook_add(UC_HOOK_MEM_READ, self.read, begin=TXCSR, end=TXCSR + 1)

    def read(self, u, _access, address, size, _value, _data):
        pc = u.reg_read(UC_ARM_REG_PC)
        assert address == TXCSR and size == 2
        assert bytes(u.mem_read(INDEX, 1)) == b"\x01"
        if pc == 0x800077C0:
            busy = next(self.schedule)
            self.polls.append(busy)
            u.mem_write(TXCSR, (4 | busy).to_bytes(2, "little"))
        else:
            assert pc == 0x800078DC, hex(pc)

    def write(self, u, _access, address, size, value, _data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if address == INDEX:
            assert pc == 0x80007BE4 and size == 1 and value in (1, INITIAL_INDEX)
            self.events.append(["index", value])
            return
        assert bytes(u.mem_read(INDEX, 1)) == b"\x01"
        if address == FIFO:
            assert (pc, size) in ((0x80007C58, 4), (0x80007C70, 1))
            self.events.append(["fifo", size, value.to_bytes(size, "little").hex()])
        elif address == TXCSR:
            assert (pc, size, value) == (0x800078B4, 2, 1)
            self.events.append(["txcsr", value])
        else:
            raise AssertionError((hex(pc), hex(address), size))


def reference_events(payload, chunks):
    events = [["index", 1]]
    pos = 0
    for count in chunks:
        word_limit = pos + (count & ~3)
        while pos < word_limit:
            events.append(["fifo", 4, payload[pos:pos + 4].hex()])
            pos += 4
        for _ in range(count % 4):
            events.append(["fifo", 1, payload[pos:pos + 1].hex()])
            pos += 1
        events.append(["txcsr", 1])
    events.append(["index", INITIAL_INDEX])
    return events


def run_case(raw, name, payload, enabled, limit, poll_schedule, chunks, expected_result):
    u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    u.ctl_set_cpu_model(UC_CPU_ARM_926)
    low, high = BASE & ~0xFFF, (BASE + len(raw) + 0xFFF) & ~0xFFF
    u.mem_map(low, high - low)
    u.mem_write(BASE, raw)
    u.mem_map(PAYLOAD, 0x4000)
    u.mem_write(PAYLOAD, payload)
    u.mem_write(CHANNEL_ENABLED, enabled.to_bytes(4, "little"))
    u.mem_write(CHANNEL_LIMIT, limit.to_bytes(4, "little"))
    hardware = ChannelRegisters(u, poll_schedule, initial_status=5 if poll_schedule is None else 4)
    marks, logs, coverage, counters_at_fifo = {}, [], {}, []

    def mark(uc, pc, size, _data):
        assert size == 4
        marks[pc] = marks.get(pc, 0) + 1
        coverage[pc] = bytes(uc.mem_read(pc, 4)).hex()
        if pc == 0x8005FC84:
            counters_at_fifo.append(int.from_bytes(uc.mem_read(uc.reg_read(UC_ARM_REG_SP), 4), "little"))

    def log(uc, _pc, _size, _data):
        lr = uc.reg_read(UC_ARM_REG_LR)
        assert lr in (0x8005FC48, 0x8005FCEC, 0x8005FCFC)
        logs.append(hex(lr))
        uc.reg_write(UC_ARM_REG_PC, lr)

    # An endpoint-transition marker at 0x8005fc64 is intentionally omitted for
    # timeout cases so no host callback runs inside its ten-million-poll loop.
    for pc in MARKERS:
        if poll_schedule is None and pc == 0x8005FC64:
            continue
        u.hook_add(UC_HOOK_CODE, mark, begin=pc, end=pc)
    u.hook_add(UC_HOOK_CODE, log, begin=LOG, end=LOG)
    for reg, value in ((UC_ARM_REG_CPSR, 0x13), (UC_ARM_REG_SP, STACK),
                       (UC_ARM_REG_LR, RETURN), (UC_ARM_REG_R0, 1),
                       (UC_ARM_REG_R1, PAYLOAD), (UC_ARM_REG_R2, len(payload))):
        u.reg_write(reg, value)
    u.emu_start(SENDER, RETURN, count=TIMEOUT_COUNT * 20 + 10_000)
    assert u.reg_read(UC_ARM_REG_PC) == RETURN and u.reg_read(UC_ARM_REG_SP) == STACK
    assert u.reg_read(UC_ARM_REG_R0) == expected_result
    assert bytes(u.mem_read(INDEX, 1)) == bytes((INITIAL_INDEX,))
    assert bytes(u.mem_read(PAYLOAD, len(payload))) == payload
    assert hardware.events == (reference_events(payload, chunks) if enabled else [])
    expected_logs = (["0x8005fc48"] if enabled else ["0x8005fcfc"])
    if enabled and expected_result:
        expected_logs.append("0x8005fcec")
    assert logs == expected_logs
    assert hardware.polls == (poll_schedule or [])
    expected_counters = []
    if poll_schedule is None:
        expected_counters = [0]
    elif enabled:
        remaining = TIMEOUT_COUNT
        for busy in poll_schedule:
            if busy:
                remaining -= 1
            else:
                expected_counters.append(remaining)
                remaining = TIMEOUT_COUNT
    assert counters_at_fifo == expected_counters
    exits = {0x8005FCD8: (1, 0), 0x8005FCF0: (1, 0xFFFFFFFF), 0x8005FD00: (0, 0xFFFFFFFF)}
    assert [exits[pc] for pc in exits if pc in marks] == [(enabled, expected_result)]
    return dict(name=name, input=payload.hex(), enabled=enabled, chunk_limit=limit,
                modeled_polls=hardware.polls, native_timeout_polls=TIMEOUT_COUNT if poll_schedule is None else None,
                poll_counters_before_fifo=counters_at_fifo,
                result=expected_result, events=hardware.events, log_return_sites=logs,
                coverage={hex(pc): coverage[pc] for pc in sorted(coverage)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, observations = {}, []
    frame = bytes.fromhex("001040020404ffff") + bytes(56)
    sequence = bytes(range(64))
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        assert int.from_bytes(raw[0x8005FD04 - BASE:0x8005FD08 - BASE], "little") == TIMEOUT_COUNT
        images[item["version"]] = digest
        observations.append([
            run_case(raw, "disabled", frame, 0, 64, [], [], 0xFFFFFFFF),
            run_case(raw, "ready", frame, 1, 64, [0], [64], 0),
            run_case(raw, "two_busy_polls", frame, 1, 64, [1, 1, 0], [64], 0),
            run_case(raw, "two_chunks_with_byte_tails", sequence[:11], 1, 7, [0, 1, 0], [7, 4], 0),
            run_case(raw, "three_chunks", sequence[:33], 1, 16, [0, 0, 0], [16, 16, 1], 0),
            run_case(raw, "native_poll_timeout", frame, 1, 64, None, [64], 0xFFFFFFFF),
        ])
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.secondary-channel1.v1", images=images, cases=observations[0], limits=[
        "Original ARM926 code performs selector stores, status polls, FIFO writes, ready-bit update and index restoration. Log calls are modeled.",
        "The indexed registers are an offline byte/halfword model. Inputs seed the channel gate, chunk limit, and poll status. The timeout holds the status busy through the unmodified 10,000,000-iteration loop.",
        "Register writes describe the CPU-visible trace. USB traffic, hardware response, physical timing and the later busy-clear producer remain outside this replay.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 6 native sender cases per factory image, 12 total")


if __name__ == "__main__":
    main()
