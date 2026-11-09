"""Execute four original producer-to-idle-service synchronous command paths."""

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "uart"))
from trace_uart_correlation import (
    BASE, COUNT, CTRL, FSM, RET, RX, OriginalUART, sha,
)
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0,
    UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
)

SERVICE = 0x80005B6C
HANDLER = 0x80003DD8
HELPER = 0x80005F14
PRODUCER = 0x80006778
DEFERRED = 0x805AC6D0
SELECTION = 0x805AC08C
QUEUE = 0x1001F000
RECORD_SIZE = 68
# Start immediately after the caller's queue-drain call.
# Each row specifies the original caller suffix and independently expected data.
CASES = (
    (0x8000E61C, 0x8000E634, (0, 9, 0x13), (9, 0x13), 0x26, b"\xc0\x00", 0x80005D04),
    (0x8000E6AC, 0x8000E6C4, (1, 0x2B, 0), (0x2B, 0), 0x2B, b"\xc4", 0x80003EB0),
    (0x8000E738, 0x8000E750, (1, 0x2A, 0), (0x2A, 0), 0x2A, b"\xc3", 0x80003EB0),
    (0x8000E7C4, 0x8000E7E0, (1, 0x27, 0x13), (9, 0x13), 0x27, b"\xc0\x55", 0x80003EB0),
)
WINDOWS = (
    (0x80003DD8, 0x80004050),
    (0x80004390, 0x80004490),
    (0x80005B6C, 0x80005D18),
    (0x80005F14, 0x80006090),
    (0x80006778, 0x800067C4),
)


class DeferredReplay(OriginalUART):
    def model_return(self, u, value):
        u.reg_write(UC_ARM_REG_R0, value)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    def code(self, u, pc, size, data):
        if not self.in_isr:
            if pc == self.callsite + 4:
                u.reg_write(UC_ARM_REG_PC, RET)
                return
            if pc == PRODUCER:
                self.producer_args = tuple(u.reg_read(r) for r in (
                    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
                ))
            if pc in (0x80061ACC, 0x800618DC):
                assert u.reg_read(UC_ARM_REG_R0) == QUEUE
                buffer = u.reg_read(UC_ARM_REG_R1)
                assert u.reg_read(UC_ARM_REG_R3) == 0
                if pc == 0x80061ACC:
                    assert u.reg_read(UC_ARM_REG_R2) == 10 and self.queued is None
                    self.record = self.queued = bytes(u.mem_read(buffer, RECORD_SIZE))
                    self.model_return(u, 1)
                else:
                    assert u.reg_read(UC_ARM_REG_R2) == 0
                    present = self.queued is not None
                    if present:
                        u.mem_write(buffer, self.queued)
                        self.queued = None
                    self.receives.append(present)
                    self.model_return(u, int(present))
                return
            if pc == HANDLER:
                assert self.byte(FSM + 0x34) == self.byte(CTRL) == 0
                assert bytes(u.mem_read(DEFERRED, RECORD_SIZE)) == self.record
                assert bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), RECORD_SIZE)) == self.record
                self.handler_entries += 1
            if pc == HELPER:
                assert self.byte(FSM + 0x34) == 0
                self.helper_entries.append((u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_LR)))
            if pc == self.helper_return and self.helper_entries and self.helper_result is None:
                self.helper_result = u.reg_read(UC_ARM_REG_R0)
            if pc == 0x80060FBC:
                self.sleeps.append(u.reg_read(UC_ARM_REG_R0))
                u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
                return
            if self.injection and pc == self.injection["site"] and not self.injection["done"]:
                assert not (u.reg_read(UC_ARM_REG_CPSR) & 0x80)
                self.pause = True
                u.emu_stop()
                return
        if any(lo <= pc < hi for lo, hi in WINDOWS) or self.start <= pc <= self.callsite:
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and address == CTRL and size == 1:
            self.pending_writes.append((u.reg_read(UC_ARM_REG_PC), value))
        if access == UC_MEM_WRITE and (
            (address == CTRL and size == 1)
            or (address in (SELECTION, SELECTION + 1) and size == 1)
            or (DEFERRED <= address and address + size <= DEFERRED + RECORD_SIZE)
        ):
            return
        super().memory(u, access, address, size, value, data)

    def replay(self, case, ack):
        self.reset()
        self.start, self.callsite, args, selection, command, payload, self.helper_return = case
        self.queued = self.record = self.helper_result = None
        self.producer_args = None
        self.handler_entries = 0
        self.receives, self.sleeps, self.helper_entries = [], [], []
        self.pending_writes = []
        self.put(CTRL + 4, QUEUE)
        self.u.mem_write(0x10010000, bytes(0x10000))
        self.invoke(self.start)
        assert self.producer_args == args
        assert self.record[:6] == struct.pack("<IBB", *args)
        assert bytes(self.u.mem_read(SELECTION, 2)) == bytes(selection)

        pointer, size = struct.unpack_from("<IB", self.raw, 0x8006367C - BASE + command * 8)
        assert size == len(payload) and self.raw[pointer - BASE:pointer - BASE + size] == payload
        frame = payload + bytes([sum(payload) & 255])
        if ack:
            self.injection = dict(site=0x80005FCC, packet=payload[:1], done=False)
        self.invoke(SERVICE)
        assert self.receives == [True, False] and self.handler_entries == 1
        assert self.pending_writes == [(0x80005BDC, 1), (0x80005CEC, 0)]
        assert self.helper_entries == [(command, self.helper_return)]
        assert self.helper_result == int(ack)
        assert self.sleeps == ([200] if args[0] == 0 else []) + [1] * (1 if ack else 1001)
        assert bytes(self.wire) == frame * (1 if ack else 2)
        assert self.rd(COUNT) == int(ack)
        if ack:
            assert self.injection["done"] and self.byte(RX) == payload[0]
        assert self.byte(CTRL) == self.byte(FSM + 0x34) == 0
        assert self.rd(0x01C208C4) & 0xC == 0
        return dict(
            caller_start=hex(self.start), producer_call=hex(self.callsite),
            record_prefix_hex=self.record[:6].hex(), copied_record_bytes=RECORD_SIZE,
            pending_writes=[(hex(pc), value) for pc, value in self.pending_writes],
            selection_hex=bytes(selection).hex(), command=hex(command),
            descriptor_pointer=hex(pointer), descriptor_payload=payload.hex(),
            helper_return_site=hex(self.helper_return), helper_result=self.helper_result,
            scenario="first-check-header" if ack else "no-reply",
            wire_hex=bytes(self.wire).hex(), sleep_calls=len(self.sleeps),
            caller_sleep_units=200 if args[0] == 0 else 0,
            helper_sleep_calls=0 if ack else 1000, service_sleep_calls=1,
            rx_count=self.rd(COUNT), instruction_count=self.instruction_count,
        )


def main():
    repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    versions = []
    manifest = json.loads((repo / "original-firmware/manifest.json").read_text())
    for item in manifest["images"]:
        raw = (repo / item["path"]).read_bytes()
        digest = sha(raw)
        assert digest == item["sha256"] and len(raw) == 5943296
        replay = DeferredReplay(raw)
        cases = [replay.replay(case, ack) for case in CASES for ack in (True, False)]
        versions.append(dict(
            version=item["version"], input_sha256=digest, cases=cases,
            observed_instructions={hex(pc): value for pc, value in sorted(replay.coverage.items())},
        ))
        print(item["version"], "PASS", len(cases), "deferred producer cases")
    assert versions[0]["cases"] == versions[1]["cases"]
    assert versions[0]["observed_instructions"] == versions[1]["observed_instructions"]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.deferred-producer-execution.v1",
        source_sha256=sha(Path(__file__).read_bytes()),
        uart_harness_sha256=sha((repo / "contributions/COORD-ADC-CADENCE/uart/trace_uart_correlation.py").read_bytes()),
        cases=sum(len(v["cases"]) for v in versions), versions=versions,
        models=[
            "One-record queue send/receive at 0x80061acc/0x800618dc.",
            "UART status and explicit one-byte arrival through original ISR.",
            "Return-only requested sleep at 0x80060fbc.",
        ],
        scope="Starts after each original caller's drain call; UI dispatch, RTOS queue and scheduling, external peer, and physical timing are outside replay.",
    ), indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
