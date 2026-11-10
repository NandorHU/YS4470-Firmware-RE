"""Replay the first Fast CONT refreshes after the original mode callback."""

import argparse
import json
import struct
from itertools import product
from pathlib import Path

from trace_native_fast_cont import (
    ACTIVE, ENTRY, FILTER_BYTES, FSM, HISTORY, HISTORY_BYTES, PWM, RESULT, SETTING, STORED,
    TIMER, UI, ModeReplay, SoundCountdown, sha,
)
from trace_refresh_rendering import (
    INIT_BASE, PRIMARY_WIDGET, TABLE_SIZE, UNIT_TABLE, UNIT_WIDGET, restore_globals,
)
from unicorn.arm_const import UC_ARM_REG_R4, UC_ARM_REG_R6


class NativeRefresh(ModeReplay, SoundCountdown):
    def prepare(self):
        self.presented, self.rendered, self.boundary = [], [], []
        self.filter_inputs, self.audio = [], []
        self.audio_enabled = False
        self.refresh_entries = 0
        super().prepare()
        offset = UNIT_TABLE - INIT_BASE
        self.u.mem_write(UNIT_TABLE, self.initialized_globals[offset:offset + TABLE_SIZE])
        self.put(0x805AC38C, PRIMARY_WIDGET)
        self.put(0x805AC390, UNIT_WIDGET)
        self.put(SETTING - 4, 0)
        self.put(SETTING - 8, 1)
        self.put(SETTING - 12, 90)
        self.put(ACTIVE, int(self.initial_active))
        self.put(RESULT + 0x50, int(self.initial_active))
        self.put(PWM, 0x7F if self.initial_active else 0)
        self.put(PWM + 4, 0x176F0A8C if self.initial_active else 0)
        self.audio_enabled = True

    def sound_state(self):
        return dict(active=self.rd(ACTIVE), countdown=self.rd(RESULT + 0x50),
                    ring=[self.rd(HISTORY + off) for off in (0, 4, 8)],
                    index=self.rd(ACTIVE + 4), fill=self.rd(ACTIVE + 8), median=self.rd(ACTIVE + 12),
                    pwm_control=hex(self.rd(PWM)), pwm_period=hex(self.rd(PWM + 4)))

    def native_refresh(self):
        previous = self.refresh_entries
        warmup = self.byte(UI + 9)
        stored = self.result()
        assert self.byte(FSM + 0x34) == 0
        assert self.byte(UI) == 4 and self.byte(UI + 7) == 0x22
        queued, rendered, dispatched = len(self.enqueued), len(self.boundary), len(self.presented)
        audio, filter_calls = len(self.audio), len(self.filter_inputs)
        tick = self.rd(TIMER + 4) + self.rd(TIMER)
        self.set_tick(tick - 1)
        self.invoke(0x8004092C)
        assert self.refresh_entries == previous and len(self.enqueued) == queued
        self.set_tick(tick)
        self.invoke(0x8004092C)
        assert self.refresh_entries == previous + 1 and self.rd(TIMER + 4) == tick
        assert len(self.enqueued) == queued + 1
        assert self.enqueued[-1][:6] == bytes((4, 0, 0, 0, 0, 0))
        assert self.result() == stored
        assert self.byte(UI + 9) == 2 and warmup == (1 if previous == 0 else 2)
        assert self.presented[dispatched:] == ([stored] if previous else [])
        records = self.boundary[rendered:]
        assert [row["raw"] for row in records] == ([stored] if previous else [])
        return dict(tick=tick, period_after=self.rd(TIMER), warmup=[warmup, self.byte(UI + 9)],
                    stored_at_entry=stored, render_records=records, filter_inputs=self.filter_inputs[filter_calls:],
                    sound_gate_calls=self.audio[audio:], sound_after_callback=self.sound_state())

    def run_native(self, missing_first, initial_active, retained_history):
        self.initial_active = initial_active
        history = HISTORY_BYTES if retained_history else struct.pack("<3I", 1000, 1000, 1000)
        filter_state = FILTER_BYTES if retained_history else struct.pack("<3I", 0, 0, 0xFFFFFFFF)
        mode = self.run_case(1, 1, 0, history=history, filter_state=filter_state)
        before_expiry = self.sound_state()
        assert before_expiry["active"] == int(initial_active)
        if initial_active:
            self.u.reg_write(UC_ARM_REG_R4, RESULT)
            self.u.reg_write(UC_ARM_REG_R6, ACTIVE)
            self.invoke(0x8000553C)
        expiry = list(self.audio)
        assert expiry == ([["0x80005568", 5, 0]] if initial_active else [])
        after_expiry = self.sound_state()
        assert after_expiry["active"] == 0 and after_expiry["countdown"] == 0
        assert after_expiry["ring"] == before_expiry["ring"]
        assert after_expiry["median"] == before_expiry["median"]
        assert after_expiry["index"] == before_expiry["index"]
        assert after_expiry["fill"] == before_expiry["fill"]
        rows = []
        for i, raw in enumerate((10001, 20002, 30003, 40004)):
            row = self.native_refresh()
            fault = "missing" if i == 0 and missing_first else "none"
            row["request"] = self.finish_request(row["tick"], 4, raw, 3, fault)
            assert row["request"]["finished_tick"] < row["tick"] + row["period_after"]
            rows.append(row)
        first, second = rows[:2]
        assert first["period_after"] == 100 and second["period_after"] == 25
        assert first["filter_inputs"] == first["sound_gate_calls"] == []
        assert first["sound_after_callback"] == after_expiry
        assert second["stored_at_entry"] == STORED and second["filter_inputs"] == [5]
        sound = second["sound_after_callback"]
        if retained_history:
            assert second["sound_gate_calls"] == [["0x80003970", 10, 1]]
            assert sound["ring"] == [5, 6, 5] and sound["index"] == 0 and sound["fill"] == 3
            assert sound["median"] == 5 and sound["active"] == 1 and sound["countdown"] == 3
            assert sound["pwm_control"] == "0x7f" and sound["pwm_period"] == "0x176f0a8c"
        else:
            assert second["sound_gate_calls"] == [["0x80003970", 0, 0]]
            assert sound["ring"] == [5, 1000, 1000] and sound["index"] == 1 and sound["fill"] == 1
            assert sound["median"] == 0xFFFFFFFF and sound["active"] == 0 and sound["countdown"] == 0
            assert int(sound["pwm_period"], 16) & 0xFFFF == 0
        first_publication = 2 if missing_first else 1
        assert next(i for i, row in enumerate(rows) if row["request"]["published"]) == first_publication
        assert rows[first_publication + 1]["render_records"][0]["raw"] == rows[first_publication]["request"]["stored_after"]
        return dict(missing_first_reply=missing_first, initially_active=initial_active,
                    retained_history=retained_history, mode=mode,
                    before_expiry=before_expiry, expiry_calls=expiry, after_expiry=after_expiry,
                    first_published_after_request=first_publication + 1, refreshes=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="Write JSON to this path, or to stdout when omitted")
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    originals = [(item, (root / item["path"]).read_bytes()) for item in manifest["images"]]
    assert all(sha(raw) == item["sha256"] and len(raw) == item["size_bytes"] for item, raw in originals)
    init = restore_globals(next(raw for item, raw in originals if item["version"] == "V3.8"))
    results, versions = [], []
    for item, raw in originals:
        replay = NativeRefresh(raw)
        replay.initialized_globals = init
        rows = [replay.run_native(*case) for case in product((False, True), repeat=3)]
        results.append((rows, {hex(pc): value for pc, value in sorted(replay.coverage.items())}))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], schedules=len(rows)))
    assert results[0] == results[1]
    payload = dict(schema="ys4470.native-fast-cont-first-refresh.v1", versions=versions,
                   init_globals_sha256=sha(init), mode_entry=hex(ENTRY), refresh_entry="0x8005d048",
                   renderer="0x8000326c", filter_entry="0x80007c88", sound_gate="0x80006e4c",
                   schedules=results[0][0], instruction_bytes={
                       pc: value for pc, value in results[0][1].items()
                       if int(pc, 16) in (ENTRY, 0x8004092C, 0x8000553C, 0x80005568, 0x800037C0,
                                          0x8000326C, 0x80003970, 0x80007C88, 0x80006E4C, 0x80042D40,
                                          0x80005B6C, 0x80004490)
                       or 0x8005D048 <= int(pc, 16) < 0x8005D254
                   },
                   limits=["Original mode callback, timer, refresh, queue, UART, FSM, renderer, filter and sound/PWM code execute.",
                           "Stored raw result, populated or empty filter, optional prior active sound, GUI leaves, UART arrivals and counter advances are fixtures.",
                           "Active sound expiry enters the original task suffix, with no surrounding watchdog or outer loop.",
                           "Numeric formatting, timer list, heap and peripheral access use the existing controlled models. Timer counts are not physical time."])
    output = json.dumps(payload, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
