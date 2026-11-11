"""Compare the original highspeed AC label with the regular result dispatcher."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_ac_checkbox_refresh import (
    DIVISION_WINDOWS, PRODUCER, QUEUE_SEND, TIMER_HANDLER, TIMER_LIST_LEAVES, TIMER_WINDOWS, RefreshAcReplay,
)
from trace_ac_checkbox_renderer import BASE, INIT_BASE, SETTINGS, TABLE_SIZE, UNIT_TABLE, restore_globals
from trace_control_gui_events import LABEL, QUEUE, RECORD_SIZE, TIMER, UI
from trace_extended_status import FLAG as CALIBRATION_FLAG, STATUS as CALIBRATION_STATUS
from trace_gauge_scheduled_service import GaugeReplay
from trace_refresh_rendering import WIDGET_TEXT, WINDOWS as RENDER_WINDOWS, RenderingReplay, f32
from trace_refresh_publication import TIMER_LIST, TIMER_STATE, TIMER_CURSOR
from trace_scheduler_delay_wake import SCHED
from trace_timer0_uart2_irq import FSM
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
)

CALLBACK, RESULT_BRANCH = 0x8005DA88, 0x8005DC3C
SELECTION = 0x805AC08C
UNIT_COPY, OVERLOAD_COPY = 0x8005DC78, 0x8005DC98
UNCLAMPED_10, SIGNED_9, CLAMPED_10 = 0x8005DCF0, 0x8005DD30, 0x8005DD5C
SAMPLES = ((-12345, 0), (-1, 3), (0, 0), (2499, 0), (2500, 0), (2501, 0),
           (549, 1), (550, 1), (551, 1), (4, 3), (5, 6), (6, 7), (0x7FFFFF, 255))


class HighspeedReplay(RefreshAcReplay):
    string = RenderingReplay.string

    def code(self, u, pc, size, data):
        if self.phase != "highspeed":
            return super().code(u, pc, size, data)
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc in TIMER_LIST_LEAVES:
            assert r0 == TIMER_LIST
            if pc == 0x8000A994:
                assert r1 == TIMER
            self.return_leaf(u, lr, TIMER if pc == 0x8000A954 else 0)
            return
        if pc == CALLBACK:
            assert r0 == TIMER and lr == 0x80040A10
            self.callbacks += 1
        if pc in (0x8005DAC4, 0x8005DBFC):
            assert r0 == (CALIBRATION_STATUS if pc == 0x8005DAC4 else CALIBRATION_FLAG)
            assert self.read(r0) == 0
        if pc == PRODUCER:
            assert (r0, r1, r2, lr) == (3, 0, 0, RESULT_BRANCH)
        if pc == QUEUE_SEND:
            assert (r0, r2, r3) == (QUEUE, 0, 0)
            assert bytes(u.mem_read(r1, RECORD_SIZE))[:6] == bytes((3, 0, 0, 0, 0, 0))
            self.queue_sends += 1
        if pc == 0x80000544:
            assert size == 2
            spec = self.string(r1, 8)
            if lr in (UNIT_COPY, OVERLOAD_COPY):
                assert spec == "%s"
                text = self.string(r2, 32)
            else:
                assert (lr, spec) in ((SIGNED_9, "%+.3f"), (UNCLAMPED_10, "%.3f"), (CLAMPED_10, "%.3f"))
                value, = struct.unpack("<d", struct.pack("<II", r2, r3))
                text = format(value, spec[1:])
            assert len(text) < 0x32
            self.formats.append([hex(lr), spec, text])
            u.mem_write(r0, text.encode("ascii") + b"\0")
            self.return_leaf(u, lr, len(text))
            return
        if pc == WIDGET_TEXT:
            assert (r0, lr) == (LABEL, 0x8005DDF4)
            self.texts.append(self.string(r1))
            self.return_leaf(u, lr, 0)
            return
        if any(lo <= pc < hi for lo, hi in ((CALLBACK, 0x8005DE44), *TIMER_WINDOWS, *DIVISION_WINDOWS, *RENDER_WINDOWS)):
            assert size in (2, 4)
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        GaugeReplay.code(self, u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if self.phase == "highspeed":
            if TIMER_STATE <= address and address + size <= TIMER_STATE + 0x14:
                return
            if address in (TIMER_CURSOR, TIMER, TIMER + 4):
                assert size == 4
                return
        super().write(u, access, address, size, value, data)

    def interrupt(self, u, number, data):
        if self.phase == "highspeed":
            return GaugeReplay.interrupt(self, u, number, data)
        super().interrupt(u, number, data)

    def highspeed_refresh(self):
        assert self.read(QUEUE + 0x38) == 0 and self.u.mem_read(FSM + 0x34, 1) == b"\0"
        deadline = self.read(TIMER + 4) + self.read(TIMER)
        assert self.read(SCHED + 0xC) < deadline
        callbacks, queue_sends = self.callbacks, self.queue_sends
        self.formats, self.texts = [], []
        self.phase = "highspeed"
        try:
            self.put(SCHED + 0xC, deadline - 1)
            self.invoke_transport(TIMER_HANDLER)
            assert (self.callbacks, self.queue_sends) == (callbacks, queue_sends)
            self.put(SCHED + 0xC, deadline)
            self.invoke_transport(TIMER_HANDLER)
        finally:
            self.phase = None
        assert (self.callbacks, self.queue_sends) == (callbacks + 1, queue_sends + 1)
        assert self.read(QUEUE + 0x38) == 1 and self.read(TIMER + 4) == deadline
        assert self.read(TIMER) == 200 and len(self.texts) == 1
        return dict(formats=self.formats, label=self.texts[0])

    def run(self, configuration, filter_setting, unit_table, normal_cases):
        self.prepare_refresh_state(int(configuration == 9), 2)
        self.u.mem_write(UNIT_TABLE, unit_table)
        self.put(SETTINGS + 0x14, filter_setting)
        self.put(UI + 0x4A8, LABEL)
        self.put(CALIBRATION_FLAG, 0)
        self.put(CALIBRATION_STATUS, 0)
        self.put(SELECTION, configuration)
        self.put(TIMER + 8, CALLBACK)
        self.callbacks = self.queue_sends = 0
        self.highspeed_refresh()
        assert not self.measurement(100, 0, True)["published"]
        self.highspeed_refresh()
        cases = []
        for sample, selector in SAMPLES:
            packet = self.measurement(sample & 0xFFFFFF, selector, True)
            assert packet["published"]
            result = self.highspeed_refresh()
            normal = normal_cases[sample, selector]
            if sample == 0x7FFFFF:
                assert result["formats"] == [[hex(UNIT_COPY), "%s", "V"], [hex(OVERLOAD_COPY), "%s", ".OL"]]
                expected = ".OL"
            else:
                divisor = (1000, 100, 10, 1, 1, 1, 1)[min(selector, 6)]
                value = f32(f32(sample) / divisor)
                if configuration == 9:
                    expected = f"{value:+.3f}"
                    assert result["formats"] == [[hex(UNIT_COPY), "%s", "V"], [hex(SIGNED_9), "%+.3f", expected]]
                else:
                    expected = f"{0.0 if value < 2.5 else value:.3f}"
                    assert result["formats"] == [[hex(UNIT_COPY), "%s", "V"],
                                                 [hex(UNCLAMPED_10), "%.3f", f"{value:.3f}"],
                                                 [hex(CLAMPED_10), "%.3f", expected]]
            assert result["label"] == expected
            cases.append(dict(signed_sample=sample, selector=selector, highspeed=result,
                              regular_label=normal, differs=result["label"] != normal))
        return dict(configuration=configuration, filter_word=filter_setting, cases=cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert int(manifest["linked_base"], 16) == BASE
    regular = json.loads(Path(__file__).with_name("ac-result-boundaries-validation.json").read_bytes())
    paths = {(path["configuration"], path["cutoff_setting"]): {(row[0], row[1]): row[6] for row in path["cases"]}
             for path in regular["paths"]}
    images, observations = {}, []
    for entry in manifest["images"]:
        raw = Path(entry["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry["sha256"] and len(raw) == entry["size_bytes"]
        images[entry["version"]] = digest
        offset = UNIT_TABLE - INIT_BASE
        table = restore_globals(raw)[offset:offset + TABLE_SIZE]
        assert len(table) == TABLE_SIZE
        results, coverage = [], {}
        for configuration, filter_word in product((9, 10), (0, 1)):
            replay = HighspeedReplay(raw)
            result = replay.run(configuration, filter_word, table, paths[configuration, filter_word])
            expected_difference = configuration == 10 and filter_word == 1
            assert any(case["differs"] for case in result["cases"]) == expected_difference
            results.append(result)
            coverage.update(replay.coverage)
        observations.append((results, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1] and images == regular["images"]
    results, coverage = observations[0]
    report = dict(schema="ys4470.ac-highspeed-result.v1", images=images, paths=results,
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["The original highspeed callback runs at the native timer deadline and enqueues the real type-3 request.",
                          "The highspeed selector and Filter word are seeded. Formatter, timer-list and label sink are modeled.",
                          "Regular labels are from the independent native AC boundary replay using the same image hashes.",
                          "UART replies are synthetic. Physical voltage, display pixels and clock intervals are outside this test."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    count = len(SAMPLES) * len(results)
    print(f"PASS {count} highspeed AC cases per factory image, {2*count} total")


if __name__ == "__main__":
    main()
