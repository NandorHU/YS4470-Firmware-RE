"""Run complete original calibration buttons with the real queue and task scheduler."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_calibration_ui import DRAIN, STATUS_TEXT, TEXT, TIMER, restore_globals
from trace_calibration_ui_live import INIT_GLOBALS, LiveCalibrationReplay
from trace_gauge_scheduled_service import GaugeReplay, QUEUE, SCHED
from trace_timer0_uart2_irq import CTRL, FSM, RESULT
from unicorn.arm_const import UC_ARM_REG_R0

BUTTON = {0x28: 0x8000E4C8, 0x29: 0x8000E55C}
MEASUREMENT = "030000000019"
OLD_CONTROL = "010000002b19"
DRAIN_RETURN = 0x80003DA4


class ButtonReplay(LiveCalibrationReplay):
    def code(self, u, pc, size, data):
        if self.ui_active and self.reject_drain_alloc:
            if pc == 0x80042AA0:
                assert u.reg_read(UC_ARM_REG_R0) == 68
                self.return_value(u, 0)
                return
            assert pc != 0x80060F5C
        if self.ui_active and 0x800618DC <= pc < 0x80061CD4:
            # The older GUI harness models queue receive. Execute it here.
            GaugeReplay.code(self, u, pc, size, data)
            return
        if self.ui_active and pc == DRAIN_RETURN:
            result = u.reg_read(UC_ARM_REG_R0)
            assert result in (0, 1)
            self.drained.append(bytes(u.mem_read(DRAIN, 6)).hex() if result else None)
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.ui_active and DRAIN <= address and address + size <= DRAIN + 68:
            return
        super().write(u, access, address, size, value, data)

    def prepare_tasks(self, mixed, command):
        assert not mixed
        self.u.mem_write(INIT_GLOBALS, self.initial_globals)
        self.callbacks = self.instruction_count = 0
        self.label_inputs, self.status_reads, self.ui_rows = [], [], []
        self.one_before, self.reset_writes, self.drained = [], [], []
        self.after_reset = self.reject_drain_alloc = False
        self.stop, self.injection = 0, None
        self.timer_bound, self.bind_count = False, None
        GaugeReplay.prepare_tasks(self, mixed, command)

    def enqueue(self, kind, arg):
        assert kind == 1 and arg == self.variant
        self.bind_timer()
        GaugeReplay.enqueue(self, 3, 0)
        if self.variant_mode == "queued":
            GaugeReplay.enqueue(self, 1, 0x2B)
            self.fire(arg, [MEASUREMENT, OLD_CONTROL])

    def fire(self, command, expected_drained):
        before = self.read(SCHED + 0xC)
        assert self.read(QUEUE + 0x38) == len(expected_drained)
        self.invoke_ui(BUTTON[command])
        assert self.drained == [*expected_drained, None]
        assert self.read(QUEUE + 0x38) == 1
        assert self.trace[-1] == ["queue_send", f"01000000{command:02x}00"]
        assert self.read(TIMER) == 2000 and self.read(TIMER + 4) == before
        label = "Cal Circuit 1 mode" if command == 0x28 else "Cal Circuit 2 mode"
        assert self.label_inputs[-1] == self.cstring(TEXT) == label
        return dict(counter=before, callback=hex(BUTTON[command]), discarded=expected_drained,
                    record_prefix=f"01000000{command:02x}00", label=label, period=self.read(TIMER))

    def run_queued(self, command):
        self.variant_mode = "queued"
        writer = self.run_long(command)
        expected = 2 if command == 0x28 else 7
        assert self.drained == [MEASUREMENT, OLD_CONTROL, None]
        assert writer["phase"] == expected and writer["injected_ticks"] == 15103
        assert not any(e[0] == "parse" for e in self.transport_events)
        assert self.label_inputs[0] == ("Cal Circuit 1 mode" if command == 0x28 else "Cal Circuit 2 mode")
        waiting = [row for row in self.ui_rows if row["status"] == 0]
        visible = [row for row in self.ui_rows if row["status"] != 0]
        assert len(waiting) == len(visible) == 6
        assert visible[0]["counter"] == 14100 and visible[0]["label"] == STATUS_TEXT[expected]
        assert all(row["status"] == expected and row["label"] == STATUS_TEXT[expected] for row in visible)
        return dict(scenario="queued-measurement-and-control", command=hex(command), drained=self.drained,
                    button=hex(BUTTON[command]), button_label=self.label_inputs[0], writer=writer,
                    ui_callbacks=self.ui_rows, one_tick_early=self.one_before)

    def run_no_drain_buffer(self, command):
        self.variant_mode = "active"
        self.variant = command
        self.prepare_tasks(False, command)
        GaugeReplay.enqueue(self, 1, 0x2B)
        assert self.read(QUEUE + 0x38) == 2
        self.reject_drain_alloc = True
        self.invoke_ui(BUTTON[command])
        assert not self.drained and self.read(QUEUE + 0x38) == 3
        data = self.read(QUEUE)
        records = [bytes(self.u.mem_read(data + 68 * index, 6)).hex() for index in range(3)]
        assert records == [MEASUREMENT, OLD_CONTROL, f"01000000{command:02x}00"]
        label = "Cal Circuit 1 mode" if command == 0x28 else "Cal Circuit 2 mode"
        assert self.label_inputs[-1] == self.cstring(TEXT) == label
        assert self.read(TIMER) == 2000
        return dict(scenario="drain-allocation-failure-with-queue-space", command=hex(command),
                    button=hex(BUTTON[command]), record_prefixes=records, label=label,
                    drained=self.drained)

    def run_active(self, command):
        self.variant_mode = "active"
        self.variant = command
        self.prepare_tasks(False, command)
        self.waits, self.completed_waits, self.replies = [], [], []
        self.transport_active = self.executing_gauge = self.dispatch_svc = True
        try:
            self.enter_gauge()
            assert self.sent() == bytes((0x60, 0x60))
            assert self.u.mem_read(FSM + 0x34, 1)[0] == 1
            assert self.read(QUEUE + 0x38) == 0
            context = self.u.context_save()
            try:
                GaugeReplay.enqueue(self, 1, 0x2B)
            finally:
                self.u.context_restore(context)
                self.transport_active = True
            button = self.fire(command, [OLD_CONTROL])
            assert self.u.mem_read(FSM + 0x34, 1)[0] == 1
            self.advance(1)
            assert self.read(QUEUE + 0x38) == 0
            assert self.u.mem_read(CTRL, 1)[0] == self.u.mem_read(FSM + 0x34, 1)[0] == 1
            assert not any(e[0] == "fallback" for e in self.trace)
            for byte in bytes((0x60, 0x45, 0x23, 1, 3)):
                self.deliver(byte)
            for _ in range(8):
                self.advance(1)
                if any(e[0] == "fallback" for e in self.trace):
                    break
            fallbacks = [e for e in self.trace if e[0] == "fallback"]
            assert len(fallbacks) == 1 and fallbacks[0][2] == f"01000000{command:02x}00"
            assert self.waits[-1]["delay"] == 600
            assert self.u.mem_read(FSM + 0x34, 1)[0] == 0
            assert (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == (0x012345, 3)
            assert self.sent() == bytes((0x60, 0x60))
        finally:
            self.transport_active = self.executing_gauge = self.dispatch_svc = False
        return dict(scenario="active-measurement-with-queued-control", command=hex(command),
                    button=button, original_fallback=fallbacks[0], pending_fallback_wait=self.waits[-1],
                    wire=self.sent().hex(), measurement_raw=self.read(RESULT + 0x1C),
                    measurement_selector=self.read(RESULT + 0x20), trace=self.trace,
                    transport_events=self.transport_events)


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
        replay = ButtonReplay(raw, initial)
        replay.install_vectors(False)
        cases = [run(command) for command, run in product((0x28, 0x29), (replay.run_queued, replay.run_active, replay.run_no_drain_buffer))]
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        outcomes.append((cases, coverage))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=len(cases)))
    assert len(outcomes) == 2 and outcomes[0] == outcomes[1]
    report = dict(schema="ys4470.calibration-button-real-queue.v1", versions=versions,
                  init_globals_sha256=hashlib.sha256(initial).hexdigest(),
                  cases=outcomes[0][0], instruction_bytes=outcomes[0][1],
                  limits=["Both complete original button callbacks, queue drain and real queue operations execute.",
                          "Allocation, GUI leaves, task setup, timer runner and IRQ inputs use fixtures.",
                          "The active-measurement case stops at the initial 600-count fallback sleep.",
                          "Allocation failure is injected while the real queue has space for the new request.",
                          "The queued cases run through IRQ-fed calibration status and original timer/label logic.",
                          "No hardware arbitration, peer internals or physical timing is established."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
