"""Read IRQ-written calibration status with the original timer in the same RAM."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from trace_calibration_ui import (
    HANDLE, INIT, LABEL, RUN, STATUS_TEXT, TEXT, TIMER, TIMER_STATE, UI, WIDGET_POINTER,
    OriginalStatusUI, restore_globals,
)
from trace_gauge_long_fallback import FLAG, OTHER, OTHER_PC, PHASE, QUEUE, SCHED, LongGaugeReplay
from unicorn.arm_const import UC_ARM_REG_PC

INIT_GLOBALS = 0x805AAAB4
INIT_STOP = 0x8004C4F8
TIMER_CURSOR = 0x805ABD80
STATUS_READER = 0x8005DAC4
FLAG_READER = 0x8005DBFC
TICK_PENDING = 1 << 13


class LiveCalibrationReplay(LongGaugeReplay, OriginalStatusUI):
    def __init__(self, raw, initial_globals):
        super().__init__(raw)
        self.initial_globals = initial_globals
        self.ui_active = False

    def code(self, u, pc, size, data):
        if self.ui_active:
            if pc == INIT_STOP:
                u.emu_stop()
                return
            OriginalStatusUI.code(self, u, pc, size, data)
            return
        super().code(u, pc, size, data)

    def read_access(self, u, access, address, size, value, data):
        if self.ui_active and (u.reg_read(UC_ARM_REG_PC), address) in (
            (STATUS_READER, PHASE), (FLAG_READER, FLAG),
        ):
            assert size == 4
            self.status_reads.append([hex(u.reg_read(UC_ARM_REG_PC)), self.read(address)])
        super().read_access(u, access, address, size, value, data)

    def write(self, u, access, address, size, value, data):
        if self.ui_active and (
            address in (HANDLE, TIMER_CURSOR)
            or TIMER_STATE <= address and address + size <= TIMER_STATE + 0x14
            or TIMER <= address and address + size <= TEXT + 64
        ):
            return
        super().write(u, access, address, size, value, data)

    def invoke_ui(self, entry, **kwargs):
        u = self.u
        context = u.context_save()
        prior_gauge, prior_transport, prior_svc = self.executing_gauge, self.transport_active, self.dispatch_svc
        self.ui_active = True
        self.executing_gauge = self.transport_active = self.dispatch_svc = False
        try:
            self.invoke(entry, **kwargs)
        finally:
            u.context_restore(context)
            self.ui_active = False
            self.executing_gauge, self.transport_active, self.dispatch_svc = prior_gauge, prior_transport, prior_svc

    def bind_timer(self):
        u = self.u
        start = self.read(SCHED + 0xC)
        self.put(WIDGET_POINTER, LABEL)
        u.mem_write(TIMER, bytes(TEXT + 64 - TIMER))
        u.mem_write(TIMER_STATE, bytes((1,)) + bytes(0x13))
        self.invoke_ui(INIT, stop=INIT_STOP)
        assert self.read(HANDLE) == TIMER
        assert struct.unpack("<6I", u.mem_read(TIMER, 24)) == (2000, start, UI, 0, 0xFFFFFFFF, 0)
        self.timer_bound = True
        self.bind_count = start

    def prepare_tasks(self, mixed, command):
        self.u.mem_write(INIT_GLOBALS, self.initial_globals)
        self.callbacks = self.instruction_count = 0
        self.label_inputs, self.status_reads, self.ui_rows = [], [], []
        self.one_before = []
        self.stop = 0
        self.injection = None
        self.timer_bound = False
        self.bind_count = None
        super().prepare_tasks(mixed, command)
        if command == 0x28:
            self.bind_timer()

    def check_timer(self, count):
        period = self.read(TIMER)
        deadline = self.read(TIMER + 4) + period
        if count not in (deadline - 1, deadline):
            return
        before = self.callbacks
        read_start = len(self.status_reads)
        labels_before = len(self.label_inputs)
        status, flag = self.read(PHASE), self.read(FLAG)
        assert status in (0, 2, 7) and (status != 0 or flag == 1)
        queue_before = self.read(QUEUE + 0x38)
        self.invoke_ui(RUN)
        assert self.read(QUEUE + 0x38) == queue_before
        assert (self.read(PHASE), self.read(FLAG), self.read(SCHED + 0xC)) == (status, flag, count)
        if count == deadline - 1:
            assert self.callbacks == before and len(self.status_reads) == read_start
            assert len(self.label_inputs) == labels_before and self.read(TIMER) == period
            self.one_before.append(count)
            return
        assert self.callbacks == before + 1 and self.read(TIMER + 4) == count
        expected_reads = [[hex(STATUS_READER), status]]
        if status == 0:
            expected_reads.append([hex(FLAG_READER), flag])
        assert self.status_reads[read_start:] == expected_reads
        expected_text = STATUS_TEXT[status] if status else "Calibration ..."
        assert self.label_inputs[labels_before:] == [expected_text]
        assert self.cstring(TEXT) == expected_text and self.read(LABEL + 0x24) == TEXT
        assert self.read(TIMER) == (200 if status else 2000)
        self.ui_rows.append(dict(counter=count, status=status, flag=flag, period_before=period,
                                 period_after=self.read(TIMER), reads=expected_reads, label=expected_text))

    def enter(self, cpsr, return_pc, pending, slot):
        events = super().enter(cpsr, return_pc, pending, slot)
        if pending == TICK_PENDING:
            assert self.read(SCHED) == OTHER and self.u.reg_read(UC_ARM_REG_PC) == OTHER_PC
            count = self.read(SCHED + 0xC)
            if not self.timer_bound and count == 702:
                self.bind_timer()
            if self.timer_bound:
                self.check_timer(count)
        return events

    def run_live(self, command):
        writer = self.run_long(command)
        assert self.timer_bound and self.callbacks == len(self.ui_rows)
        assert self.one_before == [row["counter"] - 1 for row in self.ui_rows]
        waiting = [row for row in self.ui_rows if row["status"] == 0]
        finished = [row for row in self.ui_rows if row["status"] != 0]
        expected_waiting = 6 if command == 0x28 else 5
        assert len(waiting) == expected_waiting and len(finished) >= 2
        assert [row["counter"] for row in waiting] == [self.bind_count + 2000 * n for n in range(1, expected_waiting + 1)]
        assert all(row["flag"] == 1 and row["period_after"] == 2000 for row in waiting)
        status = 2 if command == 0x28 else 7
        first, *remaining = finished
        assert first["counter"] == (14100 if command == 0x28 else 12702)
        assert first["flag"] == int(command == 0x29)
        assert first["period_before"] == 2000
        assert all(row["status"] == status and row["period_after"] == 200 for row in finished)
        assert all(row["flag"] == 0 and row["period_before"] == 200 for row in remaining)
        assert [row["counter"] for row in finished] == list(
            range(first["counter"], writer["injected_ticks"] + 101, 200)
        )
        return dict(command=hex(command), timer_bound_at=self.bind_count, one_tick_early=self.one_before,
                    callbacks=self.ui_rows, original_writer=writer)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    images = [(item, (root / item["path"]).read_bytes()) for item in manifest["images"]]
    assert all(len(raw) == item["size_bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
               for item, raw in images)
    initial = restore_globals(next(raw for item, raw in images if item["version"] == "V3.8"))
    versions, outcomes = [], []
    for item, raw in images:
        replay = LiveCalibrationReplay(raw, initial)
        replay.install_vectors(False)
        cases = [replay.run_live(command) for command in (0x28, 0x29)]
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        outcomes.append((cases, coverage))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=len(cases),
                             ui_callbacks=sum(len(case["callbacks"]) for case in cases)))
    assert len(outcomes) == 2 and outcomes[0] == outcomes[1]
    report = dict(schema="ys4470.calibration-ui-live-scheduler.v1", versions=versions,
                  init_globals_sha256=hashlib.sha256(initial).hexdigest(), cases=outcomes[0][0],
                  instruction_bytes=outcomes[0][1],
                  limits=["Both tasks share the emulator and the IRQ-written status is read directly.",
                          "The host schedules the GUI timer runner at the edge after the original gauge code yields.",
                          "GUI objects, allocation/invalidation leaves and a one-item timer list are fixtures.",
                          "Timer/UART interrupt events are injected. Physical time, pixels and peer behavior are outside the replay."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
