"""Link original configuration, timer/refresh, queue, UART and first publication."""

import argparse
import json
from pathlib import Path

from trace_deferred_producers import CTRL, FSM, SERVICE
from trace_dynamic_type2 import DynamicReplay, ENTRY, FRAMES, TIMER, UI
from trace_type6_queue import QUEUE, RealQueueReplay
from trace_uart_correlation import COUNTER, RESULT, RET, sha
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R6, UC_ARM_REG_R7,
)

REFRESH = 0x8005D048
HANDLE = 0x805ABEB8
TIMER_STATE = 0x805ABDAC
TIMER_CURSOR = 0x805ABD80
TIMER_LIST = 0x807B531C
INITIAL = (0x3456, 3)
WINDOWS = (
    (0x8004078C, 0x800407A4), (0x80040894, 0x800408F0), (0x8004092C, 0x80040B8C),
    (0x80041E68, 0x80041E6C), (0x800518BC, 0x800518D8), (REFRESH, 0x8005D254),
)


class RefreshReplay(DynamicReplay):
    def code(self, u, pc, size, data):
        r0, r1, lr = (u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
        if pc == 0x800518D8:
            u.reg_write(UC_ARM_REG_PC, RET)
            return
        if pc in (0x8000A9D8, 0x8000A954, 0x8000A994):
            assert r0 == TIMER_LIST
            if pc == 0x8000A994:
                assert r1 == TIMER
            u.reg_write(UC_ARM_REG_R0, 0 if pc == 0x8000A994 else TIMER)
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc in (0x800037C0, 0x8000326C):
            if pc == 0x800037C0:
                self.presented.append(self.result())
            u.reg_write(UC_ARM_REG_PC, lr)
            return
        if pc == 0x8000489C and lr == 0x80005C54:
            RealQueueReplay.code(self, u, pc, size, data)
            return
        if pc == REFRESH:
            assert r0 == TIMER
            self.refresh_entries += 1
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if access == UC_MEM_WRITE and (
            address in (HANDLE, TIMER_CURSOR, UI + 9)
            or TIMER_STATE <= address and address + size <= TIMER_STATE + 0x14
        ):
            return
        super().memory(u, access, address, size, value, data)

    def result(self):
        return self.rd(RESULT + 0x1C), self.rd(RESULT + 0x20)

    def set_tick(self, tick):
        self.now = tick
        self.put(COUNTER, tick)

    def setup_run(self, event_type):
        self.prepare()
        self.measurement_starts, self.presented = [], []
        self.refresh_entries = 0
        self.put(RESULT + 0x1C, INITIAL[0])
        self.put(RESULT + 0x20, INITIAL[1])
        self.u.mem_write(TIMER_STATE, b"\1" + bytes(0x13))
        self.u.reg_write(UC_ARM_REG_R6, UI)
        self.u.reg_write(UC_ARM_REG_R7, HANDLE)
        self.invoke(0x800518BC)
        assert self.rd(HANDLE) == TIMER and self.rd(TIMER) == 100
        assert self.rd(TIMER + 8) == REFRESH and self.rd(TIMER + 0x10) == 0xFFFFFFFF

        self.u.mem_write(UI, bytes((1, 1, int(event_type == 3), 0, 0, 0, 0, 0x09, 0x13)))
        result = self.configure(event_type, 0)
        assert self.result() == INITIAL and self.now < 99
        return result

    def configure(self, event_type, start):
        self.set_tick(start)
        send_start = len(self.sent)
        wire_start = len(self.wire)
        build_start = len(self.builder_calls)
        stored = self.result()
        self.invoke(ENTRY)
        primary = 0x0C if event_type == 3 else 0x22
        sequence = (primary, 0x15, 0x1D)
        self.invoke(SERVICE)
        assert self.builder_calls[build_start:] == [(3, sequence, 0x80004480)]
        assert self.rd(CTRL + 8) == primary and self.byte(CTRL + 1) == 2
        delivered = 0
        for tick in range(start + 1, start + 100):
            self.set_tick(tick)
            if delivered < len(self.sent) - send_start:
                cmd = self.sent[-1]
                for value in (b"\x60\x32\x00\x00\x03" if cmd == 0x1D else FRAMES[cmd][:1]):
                    self.receive(value)
                delivered += 1
            self.step(tick)
            if self.byte(FSM + 0x34) == 0:
                break
        assert self.byte(FSM + 0x34) == 0 and tuple(self.sent[send_start:]) == sequence
        assert bytes(self.wire[wire_start:]) == b"".join(FRAMES[cmd] for cmd in sequence)
        assert self.result() == stored and self.byte(CTRL + 1) == 1
        return dict(configuration_commands=list(sequence), configuration_idle_tick=self.now,
                    discard_after_configuration=1, stored_after_configuration=self.result())

    def refresh_at(self, tick, event_type):
        # A count one unit short of the actual timer deadline never dispatches.
        previous = self.refresh_entries
        stored = self.result()
        displayed_before = len(self.presented)
        queued_before = len(self.enqueued)
        assert tick - self.rd(TIMER + 4) == self.rd(TIMER)
        self.set_tick(tick - 1)
        self.invoke(0x8004092C)
        assert self.refresh_entries == previous
        self.set_tick(tick)
        self.invoke(0x8004092C)
        assert self.refresh_entries == previous + 1 and self.rd(TIMER + 4) == tick
        assert len(self.enqueued) == queued_before + 1
        assert self.enqueued[-1][:6] == bytes((event_type, 0, 0, 0, 0, 0))
        assert self.result() == stored
        reads = self.presented[displayed_before:]
        assert reads == ([stored] if previous >= 2 else [])
        return dict(refresh_tick=tick, result_at_refresh=stored, dispatch_read=reads,
                    timer_period_after=self.rd(TIMER), record_type=event_type)

    def finish_request(self, tick, event_type, raw, selector, fault):
        command = 0x1D if event_type == 3 else 0x1B
        header = 0x60 if event_type == 3 else 0x5E
        self.set_tick(tick)
        sends_before = len(self.sent)
        parses_before = sum(e["kind"] == "parse" for e in self.events)
        discard_before = self.byte(CTRL + 1)
        stored = self.result()
        self.invoke(SERVICE)
        assert self.rd(QUEUE + 0x38) == 0 and self.sent[sends_before:] == [command]
        replied = 0
        for now in range(tick + 1, tick + 90):
            self.now = now
            if fault != "missing" and replied < len(self.sent) - sends_before:
                data = bytes((header ^ int(fault == "wrong"),)) + raw.to_bytes(3, "little") + bytes((selector,))
                for byte in data:
                    self.receive(byte)
                replied += 1
            self.step(now)
            if self.byte(FSM + 0x34) == 0:
                break
        assert self.byte(FSM + 0x34) == 0
        good = fault == "none"
        publish = good and not discard_before
        assert self.sent[sends_before:] == ([command] if good else [command, command])
        assert sum(e["kind"] == "parse" for e in self.events) - parses_before == int(good)
        assert self.byte(CTRL + 1) == (discard_before - 1 if good and discard_before else discard_before)
        assert self.result() == ((raw, min(selector, 6) if event_type == 3 else 0) if publish else stored)
        return dict(command=hex(command), fault=fault, offered_raw=raw, offered_selector=selector,
                    finished_tick=now, discard_before=discard_before, discard_after=self.byte(CTRL + 1),
                    published=publish, stored_after=self.result())

    def run_sequence(self, event_type, first_fault):
        setup = self.setup_run(event_type)
        rows = []
        tick = 100
        for index, (raw, selector) in enumerate(((101, 2), (202, 8), (303, 1), (404, 4))):
            row = self.refresh_at(tick, event_type)
            row.update(self.finish_request(tick, event_type, raw, selector, first_fault if index == 0 else "none"))
            rows.append(row)
            tick += self.rd(TIMER)
            assert row["finished_tick"] < tick
        assert next(i for i, row in enumerate(rows, 1) if row["published"]) == (2 if first_fault == "none" else 3)
        assert self.measurement_starts == [(1, 0x1D) if event_type == 3 else (2, 0x1B)] * 4
        return dict(setup=setup, event_type=event_type, first_fault=first_fault, refreshes=rows,
                    wire_hex=bytes(self.wire).hex())

    def run_overlap(self):
        setup = self.setup_run(4)
        for tick, raw in ((100, 101), (200, 202)):
            self.refresh_at(tick, 4)
            self.finish_request(tick, 4, raw, 2, "none")
        first = self.refresh_at(300, 4)
        assert self.rd(TIMER) == 25
        self.invoke(SERVICE)
        assert self.byte(FSM + 0x34) == 1 and self.sent[-1] == 0x1B
        sends_before = len(self.sent)
        starts_before = len(self.measurement_starts)
        overlap = self.refresh_at(325, 4)
        self.invoke(SERVICE)
        assert self.rd(QUEUE + 0x38) == 0 and self.byte(FSM + 0x34) == 1
        assert len(self.sent) == sends_before and len(self.measurement_starts) == starts_before
        assert self.result() == (202, 0)
        self.set_tick(327)
        for value in b"\x5e\x2f\x01\x00\x04":
            self.receive(value)
        for tick in range(327, 332):
            self.step(tick)
            if self.byte(FSM + 0x34) == 0:
                break
        assert self.byte(FSM + 0x34) == 0 and self.result() == (303, 0)
        publish = [event for event in self.events if event["kind"] == "publish"][-1]
        assert publish["raw"] == 303 and publish["t"] == 328
        following = self.refresh_at(350, 4)
        assert first["dispatch_read"] == overlap["dispatch_read"] == [(202, 0)]
        assert following["dispatch_read"] == [(303, 0)]
        return dict(setup=setup, active_request_refresh=first, overlapping_refresh=overlap,
                    overlap_enqueued_then_skipped=True, delayed_frame_published_at_model_tick=publish["t"],
                    after_publication=following, wire_hex=bytes(self.wire).hex())

    def run_reconfigure(self, initial_type):
        setup = self.setup_run(initial_type)
        for tick, raw in ((100, 101), (200, 202)):
            self.refresh_at(tick, initial_type)
            self.finish_request(tick, initial_type, raw, 2, "none")
        prior = (202, 2 if initial_type == 3 else 0)
        assert self.result() == prior and self.byte(CTRL + 1) == 0
        new_type = 7 - initial_type
        second_setup = self.configure(new_type, 210)
        assert self.result() == prior and self.now < 299
        first = self.refresh_at(300, new_type)
        first.update(self.finish_request(300, new_type, 303, 1, "none"))
        assert first["dispatch_read"] == [prior] and not first["published"]
        tick = 300 + self.rd(TIMER)
        second = self.refresh_at(tick, new_type)
        second.update(self.finish_request(tick, new_type, 404, 4, "none"))
        assert second["dispatch_read"] == [prior] and second["published"]
        following = self.refresh_at(tick + self.rd(TIMER), new_type)
        assert following["dispatch_read"] == [(404, 4 if new_type == 3 else 0)]
        return dict(initial_event_type=initial_type, setup=setup, new_event_type=new_type,
                    second_setup=second_setup, after_switch=[first, second, following])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    rows, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        replay = RefreshReplay(raw)
        sequential = [replay.run_sequence(event, fault) for event in (3, 4)
                      for fault in ("none", "missing", "wrong")]
        overlap = replay.run_overlap()
        reconfigured = [replay.run_reconfigure(event) for event in (3, 4)]
        rows.append((sequential, overlap, reconfigured,
                     {hex(pc): value for pc, value in sorted(replay.coverage.items())}))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"],
                             cases=len(sequential)+1+len(reconfigured)))
    assert rows[0] == rows[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.refresh-publication.v1", versions=versions,
        source_sha256=sha(Path(__file__).read_text(encoding="utf-8").encode("utf-8")),
        source_hash_rule="UTF-8 source with LF line endings",
        reused_sources_sha256={
            name: sha((Path(__file__).parent / name).read_text(encoding="utf-8").encode("utf-8"))
            for name in ("trace_dynamic_type2.py", "trace_deferred_measurement.py",
                         "trace_type6_queue.py", "trace_deferred_producers.py", "../uart/trace_uart_correlation.py")
        },
        shared_sequences=rows[0][0], shared_overlap=rows[0][1], shared_reconfiguration=rows[0][2],
        instruction_bytes=rows[0][3],
        limits=[
            "Original UI configuration, timer constructor/due dispatch, refresh, queue, FSM, UART TX and ISR execute.",
            "UI style, feedback, allocation, single timer list, ResultDispatch/renderer leaves, counter steps and reply arrivals are fixtures.",
            "ResultDispatch entry receives the observed stored result; downstream formatting and physical timing are outside this replay.",
        ],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS", sum(v["cases"] for v in versions), "original configuration-to-publication sequences")


if __name__ == "__main__":
    main()
