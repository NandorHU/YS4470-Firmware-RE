"""Replay native highspeed configuration buttons through the real fallback waits."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_control_gui_events import BUTTONS, LITERALS, REGISTER, STOP, EventReplay
from trace_gauge_long_fallback import FLAG, GPIO, PHASE, TYPE0_FRAME, LongGaugeReplay
from trace_gauge_scheduled_service import CTRL, FSM, QUEUE, SCHED, STORED, GaugeReplay
from trace_scheduler_delay_wake import BASE
from trace_timer0_uart2_irq import RESULT
from unicorn.arm_const import UC_ARM_REG_R0

BUTTON_INDICES = (2, 3, 4, 5)
RETURN_SITES = (0x80003E98, 0x80003EA8, 0x80003EB0)
CONFIG_FRAMES = {9: bytes.fromhex("58035b"), 0xC: bytes.fromhex("58075f"), 0xF: bytes.fromhex("580b63")}
POST_FRAME = bytes.fromhex("5a5a")
SELECTION = 0x805AC08C


class NativeButtonsReplay(LongGaugeReplay, EventReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.raw = raw
        self.setting_up_button = False

    def code(self, u, pc, size, data):
        if self.executing_gauge and pc in RETURN_SITES:
            self.configuration_returns.append([hex(pc), u.reg_read(UC_ARM_REG_R0)])
        super().code(u, pc, size, data)

    def enqueue(self, kind, arg):
        if self.setting_up_button:
            return GaugeReplay.enqueue(self, kind, arg)
        assert kind == 1 and arg == self.variant
        self.setting_up_button = True
        try:
            bindings = [(offset, callback, 1) for offset, callback, *_ in BUTTONS]
            registered = self.register(REGISTER, STOP, LITERALS, bindings)
            self.button_binding = registered[self.button_index]
            self.button_event = self.run_event(self.button_index, 1)
        finally:
            self.setting_up_button = False
        assert bytes(self.u.mem_read(SELECTION, 2)) == bytes((arg, 0x19))
        assert bytes.fromhex(self.button_event["record_prefix"]) == struct.pack("<IBB", 1, arg, 0x19)
        # The setup invokes the native event on a queue with two pending
        # records. The event drains them before inserting its own record.
        self.trace.clear()

    def ack(self, value):
        self.deliver(value)
        self.advance(1)

    def case(self, button_index, reply_policy):
        self.button_index = button_index
        _, _, _, period, prefix = BUTTONS[button_index]
        self.variant = bytes.fromhex(prefix)[4]
        self.install_vectors(False)
        self.prepare_tasks(False, self.variant)
        self.put(PHASE, 0x99)
        self.put(FLAG, 0x99)
        self.put(GPIO, 0x80)
        self.waits, self.completed_waits, self.replies, self.configuration_returns = [], [], [], []
        config_frame = CONFIG_FRAMES[self.variant]
        self.transport_active = self.executing_gauge = self.dispatch_svc = True
        try:
            self.enter_gauge()
            assert self.read(QUEUE + 0x38) == 0 and self.sent() == TYPE0_FRAME
            self.ack(TYPE0_FRAME[0])
            assert self.sent() == TYPE0_FRAME
            self.advance(600)
            assert self.sent() == TYPE0_FRAME + config_frame
            if reply_policy != "first":
                if reply_policy == "wrong-before-retry":
                    self.deliver(0x59)
                for _ in range(500):
                    self.advance(1)
                assert self.sent() == TYPE0_FRAME + config_frame * 2
            if reply_policy == "missing-both":
                for _ in range(500):
                    self.advance(1)
            else:
                self.ack(config_frame[0])
            expected_wire = TYPE0_FRAME + config_frame * (1 if reply_policy == "first" else 2) + POST_FRAME
            assert self.sent() == expected_wire
            self.ack(POST_FRAME[0])
        finally:
            self.transport_active = self.executing_gauge = self.dispatch_svc = False
        expected_returns = (1, int(reply_policy != "missing-both"), 1)
        assert self.configuration_returns == [[hex(site), value] for site, value in zip(RETURN_SITES, expected_returns)]
        assert [e[2] for e in self.trace if e[0] == "helper"] == [0x26, self.variant, 0x19]
        assert [e[2] for e in self.trace if e[0] == "fallback"] == [prefix]
        assert self.waits[-1] == dict(start=self.read(SCHED + 0xC), delay=1, return_site="0x80003dd4")
        assert len(self.completed_waits) == 4 + (0 if reply_policy == "first" else 500) + (
            499 if reply_policy == "missing-both" else 0)
        assert self.svc_count == len(self.completed_waits) + 1 and self.select_count == 2 * self.svc_count - 1
        assert self.loop_count == 1 and self.back_edges == 0
        assert (self.read(PHASE), self.read(FLAG), self.read(GPIO)) == (0, 0, 0x80)
        assert self.u.mem_read(CTRL, 1) == self.u.mem_read(FSM + 0x34, 1) == b"\0"
        assert (self.read(RESULT + 0x1C), self.read(RESULT + 0x20)) == STORED
        assert bytes(self.u.mem_read(SELECTION, 2)) == bytes((self.variant, 0x19))
        return dict(binding=self.button_binding, input_event=self.button_event,
                    configuration=self.variant, timer_period=period, reply_policy=reply_policy,
                    wire_hex=expected_wire.hex(), helper_returns=self.configuration_returns,
                    selection=bytes(self.u.mem_read(SELECTION, 2)).hex(),
                    completed_waits=len(self.completed_waits), pending_wait=self.waits[-1],
                    relative_model_counter=self.read(SCHED + 0xC) - 100,
                    helper_calls=[row for row in self.trace if row[0] in ("helper", "fallback")])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    images, observations = {}, []
    for entry in manifest["images"]:
        raw = Path(entry["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry["sha256"] and len(raw) == entry["size_bytes"]
        images[entry["version"]] = digest
        cases, coverage = [], {}
        for index, policy in product(BUTTON_INDICES, ("first", "wrong-before-retry", "missing-both")):
            replay = NativeButtonsReplay(raw)
            cases.append(replay.case(index, policy))
            coverage.update(replay.coverage)
        observations.append((cases, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.native-highspeed-buttons.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["Original GUI registration, event callback, queue, fallback and scheduler execute.",
                          "The four checked buttons use type 1. Reply headers and Timer0/UART2 IRQs are supplied by the model.",
                          "The report ends at the first post-fallback gauge yield. No physical delays or ADC behavior are inferred."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {len(cases)} native highspeed button fallback cases per image, {2*len(cases)} total")


if __name__ == "__main__":
    main()
