"""Distinguish GUI queue drain from service-slot replacement on repeated AC toggles."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_reconfigure import ReconfigureReplay
from trace_control_gui_events import QUEUE
from trace_gauge_scheduled_service import DEFERRED, SERVICE
from trace_scheduler_delay_wake import BASE
from trace_timer0_uart2_irq import CTRL, FSM


class RapidReplay(ReconfigureReplay):
    def run_twice(self, initial, first_dequeued, reply):
        baseline, old_selector, intermediate = self.start_old_request(initial)
        first = self.release_while_active(intermediate)
        first_record = self.queued_record
        if first_dequeued:
            self.phase = "measure"
            try:
                self.invoke_transport(SERVICE)
            finally:
                self.phase = None
            assert self.byte(CTRL) == 1 and self.byte(FSM + 0x34) == 1
            assert self.read(QUEUE + 0x38) == 0
            assert bytes(self.u.mem_read(DEFERRED, len(first_record))) == first_record
        second = self.release_while_active(old_selector, queued_prefix=None if first_dequeued else first["record"])
        if first_dequeued:
            assert bytes(self.u.mem_read(DEFERRED, len(first_record))) == first_record
            assert self.byte(CTRL) == 1
        else:
            assert self.byte(CTRL) == 0
        old_request = self.finish_old_measurement(reply, old_selector)
        assert bytes(self.u.mem_read(DEFERRED, len(first_record))) == self.queued_record != first_record
        before = len(self.commands)
        configuration = self.configure_after_old(old_selector)
        assert intermediate not in self.commands[before:]
        assert self.commands[before:] == [old_selector, 0x19, 0x1D]
        return dict(initial_checkbox_state=initial, first_dequeued_before_second=first_dequeued,
                    old_reply=reply, baseline=baseline, first_release=first, second_release=second,
                    old_request=old_request, only_configuration=configuration)


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
        coverage, cases = {}, []
        for case in product((0, 1), (False, True), (False, True)):
            replay = RapidReplay(raw)
            cases.append(replay.run_twice(*case))
            coverage.update(replay.coverage)
        images[item["version"]] = digest
        results.append(dict(cases=cases, instruction_bytes={hex(pc): v for pc, v in sorted(coverage.items())}))
    assert images.keys() == {"V3.6", "V3.8"} and results[0] == results[1]
    report = dict(schema="ys4470.ac-checkbox-rapid-toggle.v1", images=images, **results[0], limits=[
        "Two additional original checkbox releases occur while the same original measurement waits for a reply. Each uses the registered class and callback on shared state.",
        "The harness orders the two releases and optionally invokes the original service between them. No event is injected midway through a firmware instruction sequence.",
        "UART replies and timer counts are controlled. Timer-list and view calls are modeled. Physical input frequency, timing and the measurement peer are outside the test.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 8 repeated AC toggle cases per factory image, 16 total")


if __name__ == "__main__":
    main()
