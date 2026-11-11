"""Replay original timer refresh and publication after the AC checkbox configuration."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_uart import FSM_STEP, WIRE_SEND, CheckboxUartReplay
from trace_control_gui_events import MODE, QUEUE, RECORD_SIZE, TIMER
from trace_gauge_scheduled_service import GaugeReplay, SERVICE
from trace_refresh_publication import REFRESH, TIMER_CURSOR, TIMER_LIST, TIMER_STATE, WINDOWS as TIMER_WINDOWS
from trace_scheduler_delay_wake import BASE, SCHED
from trace_timer0_uart2_irq import CTRL, FSM, RESULT, STORED
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3

TIMER_HANDLER, DISPATCH_RESULT, RENDER = 0x8004092C, 0x800037C0, 0x8000326C
PRODUCER, QUEUE_SEND = 0x80006778, 0x80061ACC
TIMER_LIST_LEAVES = (0x8000A954, 0x8000A994)
DIVISION_WINDOWS = ((0x800019D0, 0x80001A00), (0x80000D50, 0x80000E68))


class RefreshAcReplay(CheckboxUartReplay):
    def code(self, u, pc, size, data):
        if self.phase == "refresh":
            r0, r1, r2, lr = (u.reg_read(reg) for reg in (
                UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_LR,
            ))
            if pc in TIMER_LIST_LEAVES:
                assert r0 == TIMER_LIST
                if pc == 0x8000A994:
                    assert r1 == TIMER
                self.return_leaf(u, lr, TIMER if pc == 0x8000A954 else 0)
                return
            if pc in (DISPATCH_RESULT, RENDER):
                assert lr == (0x8005D1A4 if pc == DISPATCH_RESULT else 0x8005D1AC)
                self.view_entries.append([hex(pc), list(self.result_words())])
                self.return_leaf(u, lr, r0)
                return
            if pc == REFRESH:
                assert r0 == TIMER and lr == 0x80040A10
                self.refresh_entries += 1
            if pc == PRODUCER:
                assert (r0, r1, r2, lr) == (3, 0, 0, 0x8005D134)
            if pc == QUEUE_SEND:
                assert r0 == QUEUE and (r2, u.reg_read(UC_ARM_REG_R3)) == (0, 0)
                self.refresh_records.append(bytes(u.mem_read(r1, RECORD_SIZE)))
            if any(lo <= pc < hi for lo, hi in (*TIMER_WINDOWS, *DIVISION_WINDOWS)):
                assert size == 4
                self.coverage[pc] = bytes(u.mem_read(pc, 4)).hex()
                return
        if self.phase == "measure" and pc == WIRE_SEND:
            self.measure_commands.append(self.read(FSM + 0x20))
        if self.phase in ("refresh", "measure"):
            return GaugeReplay.code(self, u, pc, size, data)
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "refresh":
            if TIMER_STATE <= address and address + size <= TIMER_STATE + 0x14:
                return
            if address in (TIMER_CURSOR, TIMER, TIMER + 4):
                assert size == 4
                return
            if address == MODE + 9:
                assert size == 1 and u.reg_read(UC_ARM_REG_PC) == 0x8005D190
                return
        super().write(u, access, address, size, value, data)

    def interrupt(self, u, number, data):
        if self.phase in ("refresh", "measure"):
            self.refresh_svc.append([number, hex(u.reg_read(UC_ARM_REG_PC))])
            return GaugeReplay.interrupt(self, u, number, data)
        super().interrupt(u, number, data)

    def result_words(self):
        return self.read(RESULT + 0x1C), self.read(RESULT + 0x20)

    def timer_refresh(self, expected_warmup):
        assert self.read(QUEUE + 0x38) == 0
        assert self.u.mem_read(FSM + 0x34, 1)[0] == 0
        period = self.read(TIMER)
        deadline = self.read(TIMER + 4) + period
        assert self.read(SCHED + 0xC) < deadline
        expected_raw = self.result_words()
        prior = self.refresh_entries
        calls = len(self.view_entries)
        records = len(self.refresh_records)
        self.phase = "refresh"
        try:
            self.put(SCHED + 0xC, deadline - 1)
            self.invoke_transport(TIMER_HANDLER)
            assert self.refresh_entries == prior and self.read(QUEUE + 0x38) == 0
            self.put(SCHED + 0xC, deadline)
            self.invoke_transport(TIMER_HANDLER)
        finally:
            self.phase = None
        assert self.refresh_entries == prior + 1 and self.read(TIMER + 4) == deadline
        assert self.read(QUEUE + 0x38) == 1
        assert len(self.refresh_records) == records + 1
        assert self.refresh_records[-1][:6] == bytes((3, 0, 0, 0, 0, 0))
        assert self.result_words() == expected_raw
        assert self.u.mem_read(MODE + 9, 1)[0] == min(2, expected_warmup + 1)
        assert self.read(TIMER) == (200 if expected_warmup == 2 else period)
        observed = self.view_entries[calls:]
        assert observed == ([[hex(DISPATCH_RESULT), list(expected_raw)], [hex(RENDER), list(expected_raw)]]
                            if expected_warmup == 2 else [])
        return dict(deadline=deadline, period=period, next_period=self.read(TIMER),
                    result_at_refresh=expected_raw, modeled_view_reads=observed,
                    warmup_before=expected_warmup, record_prefix=self.refresh_records[-1][:6].hex())

    def measurement(self, payload_raw, payload_selector, deliver):
        before = self.result_words()
        discard = self.u.mem_read(CTRL + 1, 1)[0]
        commands = len(self.measure_commands)
        tx_before = len(self.transport_events)
        start = self.read(SCHED + 0xC)
        packet = b"\x60" + payload_raw.to_bytes(3, "little") + bytes((payload_selector,))
        self.phase = "measure"
        try:
            self.invoke_transport(SERVICE)
            assert self.read(QUEUE + 0x38) == 0 and self.measure_commands[commands:] == [0x1D]
            if deliver:
                for byte in packet:
                    self.deliver(byte)
            for _ in range(420):
                self.tick()
                self.invoke_transport(FSM_STEP)
                if self.u.mem_read(FSM + 0x34, 1)[0] == 0:
                    break
        finally:
            self.phase = None
        assert self.u.mem_read(FSM + 0x34, 1)[0] == 0
        assert self.measure_commands[commands:] == ([0x1D] if deliver else [0x1D, 0x1D])
        rows = self.transport_events[tx_before:]
        assert bytes(r[1] for r in rows if r[0] == "tx") == b"\x60\x60" * (1 if deliver else 2)
        assert [r for r in rows if r[0] == "parse"] == ([["parse", 5, packet.hex()]] if deliver else [])
        published = deliver and discard == 0
        # The original command-0x1d parser sign-extends the wire sample and
        # clamps the selector before publishing either result word.
        sample_word = payload_raw | (0xFF000000 if payload_raw & 0x800000 else 0)
        expected = (sample_word, min(payload_selector, 6))
        assert self.result_words() == (expected if published else before)
        assert self.u.mem_read(CTRL + 1, 1)[0] == max(0, discard - int(deliver))
        return dict(reply=packet.hex() if deliver else None, offered_raw=payload_raw,
                    discard_before=discard, published=published, stored_after=self.result_words(),
                    elapsed_model_steps=self.read(SCHED + 0xC) - start)

    def prepare_refresh_state(self, initial, warmup):
        configured = self.consume(initial, True)
        assert self.result_words() == STORED and self.u.mem_read(CTRL + 1, 1)[0] == 1
        assert self.read(TIMER) == 2000
        # The release callback owns the period and selector. Seed the other
        # timer metadata and the pre-existing UI flags used by the refresh.
        self.put(TIMER + 4, self.read(SCHED + 0xC))
        self.put(TIMER + 8, REFRESH)
        self.put(TIMER + 0x10, 0xFFFFFFFF)
        self.u.mem_write(TIMER_STATE, b"\x01" + bytes(0x13))
        self.u.mem_write(MODE, b"\0\0\0\0\0\0\0")
        self.u.mem_write(MODE + 9, bytes((warmup,)))
        self.refresh_entries = 0
        self.refresh_records, self.view_entries, self.measure_commands, self.refresh_svc = [], [], [], []
        return configured

    def run_refreshes(self, initial, warmup, miss_first):
        configured = self.prepare_refresh_state(initial, warmup)
        rows = []
        for i in range(4):
            row = self.timer_refresh(min(2, warmup + i))
            row["measurement"] = self.measurement((i + 1) * 101, i + 2, deliver=not (i == 0 and miss_first))
            assert self.read(SCHED + 0xC) < row["deadline"] + row["next_period"]
            rows.append(row)
        first = next(i for i, row in enumerate(rows) if row["measurement"]["published"])
        assert first == (2 if miss_first else 1)
        assert rows[first + 1]["modeled_view_reads"][0][1] == list(rows[first]["measurement"]["stored_after"])
        return dict(initial_checkbox_state=initial, initial_warmup=warmup, missing_first_reply=miss_first,
                    configuration_wire=configured["uart_wire"], refreshes=rows, modeled_svc_calls=self.refresh_svc)


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
        coverage, cases = {}, []
        for case in product((0, 1), (0, 2), (False, True)):
            replay = RefreshAcReplay(raw)
            cases.append(replay.run_refreshes(*case))
            coverage.update(replay.coverage)
        results.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.ac-checkbox-refresh.v1", images=images, **results[0], limits=[
        "Starts from the native AC checkbox configuration. Its original timer period is retained. The harness seeds the timer callback metadata, UI flags and warmup and sets a model counter before each deadline.",
        "Original timer runner, refresh, queue, service, UART FSM and Timer0/UART2 handlers execute. Timer-list traversal and view functions are modeled, and SVC yields do not switch tasks.",
        "The view observations are stored-result reads at modeled renderer entry. Physical timer intervals, USB/ADC peer behavior, screen pixels and audio are outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 native AC refresh schedules per factory image, 16 total")


if __name__ == "__main__":
    main()
