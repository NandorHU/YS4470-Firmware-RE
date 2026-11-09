"""Replay original deferred commands 0x28 and 0x29 and their later status loop."""

import argparse
import json
import struct
from dataclasses import dataclass
from itertools import groupby
from pathlib import Path

from trace_deferred_producers import (
    BASE, COUNT, CTRL, FSM, HELPER, QUEUE, RX, SERVICE, DeferredReplay, sha,
)
from trace_uart_correlation import NEST
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import UC_ARM_REG_CPSR, UC_ARM_REG_PC, UC_ARM_REG_R0

PRODUCERS = ((0x28, 0x8000E4F4, 0x8000E50C), (0x29, 0x8000E588, 0x8000E5A0))
STATUS = 0x805AB920
FLAG = 0x805AB91C
GPIO = 0x01C208C4
FIRST_CHECK = 0x80005FCC
STATUS_CHECK = 0x80003F68
AFTER_CLEAR = (0x80003F38, 0x80003F58)
PAYLOADS = {0x26: b"\xc0\x00", 0x27: b"\xc0\x55", 0x28: b"\xc1", 0x29: b"\xc2"}


@dataclass(frozen=True)
class Scenario:
    name: str
    initial_ack: bool = True
    command_ack: bool = True
    final_ack: bool = True
    ack_suffix: bytes = b""
    before_second_clear: bytes = b""
    arrivals: tuple[tuple[int, bytes], ...] = ()
    recognized_poll: int = 0
    result: int = 0


SCENARIOS = (
    Scenario("command-ack-missing", command_ack=False),
    Scenario("ack-only"),
    Scenario("status-behind-ack", ack_suffix=b"\xa0\x01"),
    Scenario("status-between-clears", before_second_clear=b"\xa1\x04"),
    Scenario("a0-01", arrivals=((1, b"\xa0\x01"),), recognized_poll=1, result=1),
    Scenario("a0-02", arrivals=((1, b"\xa0\x02"),), recognized_poll=1, result=2),
    Scenario("a0-03", arrivals=((1, b"\xa0\x03"),), recognized_poll=1, result=3),
    Scenario("a0-invalid", arrivals=((1, b"\xa0\x04"),), recognized_poll=1),
    Scenario("a0-header-only", arrivals=((1, b"\xa0"),), recognized_poll=1),
    Scenario("a1-01", arrivals=((1, b"\xa1\x01"),), recognized_poll=1, result=4),
    Scenario("a1-02", arrivals=((1, b"\xa1\x02"),), recognized_poll=1, result=5),
    Scenario("a1-03", arrivals=((1, b"\xa1\x03"),), recognized_poll=1, result=6),
    Scenario("a1-04-last-poll", arrivals=((230, b"\xa1\x04"),), recognized_poll=230, result=7),
    Scenario("a1-invalid", arrivals=((1, b"\xa1\x05"),), recognized_poll=1),
    Scenario("unknown-first-byte", arrivals=((1, b"\x99"), (2, b"\xa0\x01"))),
    Scenario("initial-and-final-ack-missing", initial_ack=False, final_ack=False,
             arrivals=((1, b"\xa0\x01"),), recognized_poll=1, result=1),
)


class ExtendedReplay(DeferredReplay):
    def deliver(self, key, pc, packet):
        if packet and key not in self.delivered:
            self.delivered[key] = packet.hex()
            self.injection = dict(site=pc, packet=packet, done=False)

    def code(self, u, pc, size, data):
        if not self.in_isr:
            if pc == HELPER:
                self.active_command = u.reg_read(UC_ARM_REG_R0)
            if pc in (0x80003EC8, 0x80003F14, 0x80003FEC):
                self.helper_returns.append(u.reg_read(UC_ARM_REG_R0))
            if pc == FIRST_CHECK:
                command = self.active_command
                packet = self.ack_packets[command]
                self.deliver(f"ack-{command:02x}", pc, packet)
            if pc == 0x80003F40:
                self.deliver("between-clears", pc, self.scenario.before_second_clear)
            if pc in AFTER_CLEAR:
                assert bytes(u.mem_read(RX, 200)) == bytes(200)
                self.clears.append((hex(pc), self.rd(COUNT), self.byte(RX), self.byte(RX + 1)))
            if pc == STATUS_CHECK:
                poll = self.sleeps.count(1000)
                self.deliver(f"poll-{poll}", pc, self.arrivals.get(poll, b""))
                if not self.injection or self.injection["done"]:
                    self.polls.append((poll, self.rd(COUNT), self.byte(RX), self.byte(RX + 1)))
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE:
            pc = u.reg_read(UC_ARM_REG_PC)
            if address == COUNT and pc in (0x80003F24, 0x80003F44):
                assert u.reg_read(UC_ARM_REG_CPSR) & 0x80 and self.rd(NEST) > 0
                self.clear_counts.append(self.rd(COUNT))
            if address in (STATUS, FLAG):
                assert size == 4
                self.status_writes.append((pc, address, value))
            if address == GPIO:
                assert size == 4
                self.gpio_writes.append(value)
        super().memory(u, access, address, size, value, data)

    def run_case(self, producer, scenario):
        self.reset()
        command, self.start, self.callsite = producer
        self.scenario = scenario
        self.arrivals = dict(scenario.arrivals)
        self.ack_packets = {
            0x27: b"\xc0" if scenario.initial_ack else b"",
            command: PAYLOADS[command][:1] + scenario.ack_suffix if scenario.command_ack else b"",
            0x26: b"\xc0" if scenario.final_ack else b"",
        }
        self.delivered = {}
        self.clears, self.clear_counts, self.polls, self.status_writes = [], [], [], []
        self.helper_returns = []
        self.gpio_writes = []
        self.helper_return = 0x80003EC8
        self.queued = self.record = self.helper_result = self.producer_args = None
        self.handler_entries = 0
        self.receives, self.sleeps, self.helper_entries, self.pending_writes = [], [], [], []
        self.put(CTRL + 4, QUEUE)
        self.put(STATUS, 0x99)
        self.put(FLAG, 0x99)
        self.put(GPIO, 0x80)
        self.u.mem_write(0x10010000, bytes(0x10000))
        self.invoke(self.start)
        assert self.producer_args == (1, command, 0)
        assert self.record[:6] == struct.pack("<IBB", 1, command, 0)
        self.invoke(SERVICE)

        assert self.receives == [True, False] and self.handler_entries == 1
        assert self.pending_writes == [(0x80005BDC, 1), (0x80005CEC, 0)]
        expected_helpers = [(0x27, 0x80003EC8), (command, 0x80003F14)]
        expected_returns = [int(scenario.initial_ack), int(scenario.command_ack)]
        if scenario.recognized_poll:
            expected_helpers.append((0x26, 0x80003FEC))
            expected_returns.append(int(scenario.final_ack))
        assert self.helper_entries == expected_helpers and self.helper_returns == expected_returns
        assert self.rd(STATUS) == scenario.result and self.rd(FLAG) == 0
        assert self.byte(CTRL) == self.byte(FSM + 0x34) == 0
        assert self.rd(GPIO) == 0x80
        if scenario.recognized_poll:
            assert self.gpio_writes[-4:] == [0x80, 0x84, 0x84, 0x80]

        poll_count = (scenario.recognized_poll or 230) if scenario.command_ack else 0
        expected_sleeps = ([600] + [1] * (0 if scenario.initial_ack else 1000)
                           + [500, 500] + [1] * (0 if scenario.command_ack else 1000))
        if scenario.command_ack:
            expected_sleeps += [10000] + [1000] * poll_count
        if scenario.recognized_poll:
            expected_sleeps += [1] * (0 if scenario.final_ack else 1000) + [2000, 500]
        assert self.sleeps == expected_sleeps + [1]
        assert [p[0] for p in self.polls] == list(range(1, poll_count + 1))

        if scenario.command_ack:
            assert self.clears == [(hex(pc), 0, 0, 0) for pc in AFTER_CLEAR]
            assert self.clear_counts == [1 + len(scenario.ack_suffix), len(scenario.before_second_clear)]
        else:
            assert self.clears == self.clear_counts == []
        expected_status_write = [(0x80003E60, STATUS, 0)]
        expected_flag_write = [
            (0x80003E58, FLAG, 1),
            (0x80003FF0 if scenario.recognized_poll else 0x80003EB0, FLAG, 0),
        ]
        if scenario.result:
            write_pc = 0x80003F94 if scenario.result == 1 else 0x80003FA8
            expected_status_write.append((write_pc, STATUS, scenario.result))
        assert [w for w in self.status_writes if w[1] == STATUS] == expected_status_write
        assert [w for w in self.status_writes if w[1] == FLAG] == expected_flag_write

        # Verify the complete sampled RX prefix at every original poll.
        received = b""
        for poll, count, first, second in self.polls:
            received += self.arrivals.get(poll, b"")
            expected = (received + b"\0\0")[:2]
            assert (count, first, second) == (len(received), *expected)

        wire = b""
        for (descriptor, _), ack in zip(expected_helpers, expected_returns):
            payload = PAYLOADS[descriptor]
            pointer, length = struct.unpack_from("<IB", self.raw, 0x8006367C - BASE + descriptor * 8)
            assert self.raw[pointer - BASE:pointer - BASE + length] == payload
            wire += (payload + bytes([sum(payload) & 255])) * (1 if ack else 2)
        assert bytes(self.wire) == wire
        poll_samples = list(dict.fromkeys(self.polls[:2] + self.polls[-2:]))
        return dict(
            command=hex(command), producer=hex(self.callsite), case=scenario.name,
            record_prefix_hex=self.record[:6].hex(),
            helpers=[dict(id=hex(cid), return_site=hex(site), result=value)
                     for (cid, site), value in zip(self.helper_entries, self.helper_returns)],
            deliveries=self.delivered, counts_before_critical_clear=self.clear_counts,
            critical_clears=self.clears, status_polls=poll_count, poll_samples=poll_samples,
            status_writes=[dict(pc=hex(pc), address=hex(address), value=value)
                           for pc, address, value in self.status_writes],
            wire_hex=wire.hex(), requested_sleep_calls=len(self.sleeps),
            requested_sleep_runs=[(units, len(list(run))) for units, run in groupby(self.sleeps)],
            gpio_shadow_writes=self.gpio_writes,
            original_instructions=self.instruction_count,
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo / "original-firmware/manifest.json").read_text())
    versions = []
    shared_rows = shared_bytes = None
    for item in manifest["images"]:
        raw = (repo / item["path"]).read_bytes()
        digest = sha(raw)
        assert digest == item["sha256"] and len(raw) == 5943296
        replay = ExtendedReplay(raw)
        rows = [replay.run_case(producer, case) for producer in PRODUCERS for case in SCENARIOS]
        executed = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        if shared_rows is None:
            shared_rows, shared_bytes = rows, executed
        assert rows == shared_rows and executed == shared_bytes
        versions.append(dict(version=item["version"], input_sha256=digest, cases=len(rows)))
        print(item["version"], "PASS", len(rows), "extended status cases")
    args.out.write_text(json.dumps(dict(
        schema="ys4470.extended-deferred-status.v1",
        source_sha256=sha(Path(__file__).read_bytes()),
        producer_harness_sha256=sha(Path(__file__).with_name("trace_deferred_producers.py").read_bytes()),
        uart_harness_sha256=sha((repo / "contributions/COORD-ADC-CADENCE/uart/trace_uart_correlation.py").read_bytes()),
        versions=versions, total_cases=sum(v["cases"] for v in versions),
        cases_identical_across_versions=shared_rows,
        observed_instructions_identical_across_versions=shared_bytes,
        models=[
            "One-record RTOS queue handoff, requested sleep returns, UART status and explicit byte delivery.",
            "Original UART ISR executed with controlled nested context after each scheduled injection.",
            "Original caller suffixes start after their queue-drain call; peer and physical timing are outside replay.",
        ],
    ), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
