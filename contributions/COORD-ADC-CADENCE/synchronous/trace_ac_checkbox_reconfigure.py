"""Exercise an AC checkbox reconfiguration while the original UART FSM is active."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_refresh import RefreshAcReplay
from trace_ac_checkbox_release import CHECKBOX, RELEASED, VALUE_CHANGED
from trace_ac_checkbox_uart import FSM_STEP, MEASUREMENT_REPLY
from trace_control_gui_events import EVENT_CURRENT, EVENT_SEND, INDIRECT, MODE, PREVIOUS_EVENT, QUEUE, TIMER
from trace_control_gui_second_final import FLAG_EVENT
from trace_dynamic_type2 import FRAMES
from trace_gauge_scheduled_service import DEFERRED, SERVICE
from trace_scheduler_delay_wake import BASE, SCHED, TASK
from trace_timer0_uart2_irq import CTRL, FSM, STORED
from unicorn.arm_const import UC_ARM_REG_R2

OLD_REPLY = bytes.fromhex("6056340202")
OLD_RESULT = (0x023456, 2)


class ReconfigureReplay(RefreshAcReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.live_release = False

    def dispatch(self):
        if not self.live_release:
            return super().dispatch()
        tick = self.read(SCHED + 0xC)
        self.phase, self.transport_active = "dispatch", True
        self.u.reg_write(UC_ARM_REG_R2, 0)
        try:
            assert self.invoke(EVENT_SEND, self.object, RELEASED) == 1
        finally:
            self.phase, self.transport_active = None, False
        assert self.read(EVENT_CURRENT) == PREVIOUS_EVENT and self.read(CTRL + 4) == QUEUE
        assert self.read(SCHED) == TASK and self.read(SCHED + 0xC) == tick

    def byte(self, address):
        return self.u.mem_read(address, 1)[0]

    def release_while_active(self, selector, queued_prefix=None):
        assert self.read(QUEUE + 0x38) == int(queued_prefix is not None) and self.byte(FSM + 0x34) == 1
        self.live_release = True
        self.producer_return = 0x8000F418 if selector == 10 else 0x8000F4A0
        self.calls, self.producer_args, self.drained = [], [], []
        self.copies, self.ui_leaves, self.timer_stores = [], [], []
        self.style, self.cells, self.events_seen, self.class_events, self.checkbox_writes = [], [], [], [], []
        try:
            self.dispatch()
        finally:
            self.live_release = False
        assert self.calls == [[hex(INDIRECT), hex(FLAG_EVENT)]]
        assert [event[0] for event in self.events_seen] == [RELEASED, VALUE_CHANGED]
        assert self.checkbox_writes == [int(selector == 10)]
        assert self.read(CHECKBOX + 0x20) == int(selector == 10)
        assert self.drained == ([queued_prefix, None] if queued_prefix is not None else [None])
        assert self.read(TIMER) == 2000
        assert self.producer_args == [[2, selector, 0x19]] and self.read(QUEUE + 0x38) == 1
        assert self.byte(MODE + 7) == selector and self.byte(FSM + 0x34) == 1
        self.queued_record, = self.copies
        expected = bytes((2, 0, 0, 0, selector, 0x19))
        assert self.queued_record[:6] == expected
        return dict(new_selector=selector, record=expected.hex(), checkbox_writes=self.checkbox_writes,
                    event_chain=self.events_seen, timer_writes=self.timer_stores, drained=self.drained)

    def finish_old_measurement(self, reply, prior_selector):
        self.phase = "measure"
        try:
            self.invoke_transport(SERVICE)
            assert self.read(QUEUE + 0x38) == 0 and self.byte(CTRL) == 1
            assert self.read(CTRL + 8) == prior_selector and self.byte(FSM + 0x34) == 1
            assert bytes(self.u.mem_read(DEFERRED, len(self.queued_record))) == self.queued_record
            initial_commands = len(self.measure_commands)
            if reply:
                for value in OLD_REPLY:
                    self.deliver(value)
            for _ in range(420):
                self.tick()
                self.invoke_transport(FSM_STEP)
                if self.byte(FSM + 0x34) == 0:
                    break
        finally:
            self.phase = None
        assert self.byte(FSM + 0x34) == 0 and self.byte(CTRL) == 1
        assert self.read(CTRL + 8) == prior_selector
        assert self.measure_commands[initial_commands:] == ([] if reply else [0x1D])
        assert self.result_words() == (OLD_RESULT if reply else STORED)
        return dict(reply=OLD_REPLY.hex() if reply else None, published_result=self.result_words(),
                    old_selector=prior_selector, new_record_pending=True)

    def configure_after_old(self, selector):
        sequence = [selector, 0x19, 0x1D]
        command_start, event_start = len(self.commands), len(self.transport_events)
        previous = self.result_words()
        self.phase = "consume"
        try:
            self.invoke_transport(SERVICE)
            assert self.byte(CTRL) == 0 and self.read(CTRL + 8) == selector
            assert self.dispatch_records[-1] == self.queued_record[:6].hex()
            assert self.builder_calls[-1] == [3, sequence, "0x80004480"]
            assert self.commands[command_start:] == [selector]
            assert self.byte(CTRL + 1) == 2
            delivered = 0
            for _ in range(420):
                if delivered < len(self.commands) - command_start:
                    cmd = self.commands[-1]
                    packet = MEASUREMENT_REPLY if cmd == 0x1D else FRAMES[cmd][:1]
                    for value in packet:
                        self.deliver(value)
                    delivered += 1
                self.tick()
                self.invoke_transport(FSM_STEP)
                if self.byte(FSM + 0x34) == 0:
                    break
        finally:
            self.phase = None
        assert self.byte(FSM + 0x34) == 0 and self.byte(CTRL + 1) == 1
        assert self.commands[command_start:] == sequence
        tx = bytes(row[1] for row in self.transport_events[event_start:] if row[0] == "tx")
        assert tx == b"".join(FRAMES[cmd] for cmd in sequence)
        assert self.result_words() == previous
        return dict(commands=sequence, wire=tx.hex(), discard_after=self.byte(CTRL + 1), stored_after=previous)

    def start_old_request(self, initial):
        self.prepare_refresh_state(initial, 2)
        old_selector, new_selector = (9, 10) if initial & 1 else (10, 9)
        self.timer_refresh(2)
        baseline = self.measurement(101, 3, deliver=True)
        assert not baseline["published"] and self.byte(CTRL + 1) == 0
        self.timer_refresh(2)
        self.phase = "measure"
        try:
            self.invoke_transport(SERVICE)
        finally:
            self.phase = None
        assert self.byte(FSM) == 3 and self.byte(FSM + 0x34) == 1
        assert self.read(CTRL + 8) == old_selector and self.measure_commands[-1] == 0x1D
        return baseline, old_selector, new_selector

    def run_reconfigure(self, initial, reply):
        baseline, old_selector, new_selector = self.start_old_request(initial)
        transition = self.release_while_active(new_selector)
        old_request = self.finish_old_measurement(reply, old_selector)
        new_configuration = self.configure_after_old(new_selector)
        rows = []
        for raw in (303, 404):
            row = self.timer_refresh(2)
            row["measurement"] = self.measurement(raw, 4, deliver=True)
            rows.append(row)
        assert not rows[0]["measurement"]["published"] and rows[1]["measurement"]["published"]
        assert rows[0]["result_at_refresh"] == rows[1]["result_at_refresh"] == old_request["published_result"]
        assert self.result_words() == (404, 4)
        return dict(initial_checkbox_state=initial, old_reply=reply, baseline=baseline,
                    release=transition, old_request=old_request, new_configuration=new_configuration,
                    new_refreshes=rows, final_result=self.result_words())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        cases, coverage = [], {}
        for case in product((0, 1), (False, True)):
            replay = ReconfigureReplay(raw)
            cases.append(replay.run_reconfigure(*case))
            coverage.update(replay.coverage)
        observations.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
        images[item["version"]] = digest
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.ac-checkbox-reconfigure.v1", images=images, **observations[0], limits=[
        "The harness injects a second checkbox release after the old original FSM enters its reply wait. The registered class and callback execute on the same state and queue without reinitializing the scheduler.",
        "Timer and UART IRQ handlers execute with controlled input. Timer-list and display calls are modeled. Original SVC yields do not switch tasks.",
        "The case covers one original in-flight type-3 measurement and one newly deferred type-2 configuration, with a complete or absent old reply. Real input ordering, timing and physical values are outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 4 in-flight AC reconfiguration cases per factory image, 8 total")


if __name__ == "__main__":
    main()
