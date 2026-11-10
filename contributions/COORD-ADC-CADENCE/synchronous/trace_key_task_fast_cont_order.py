"""Replay KeyTask countdown and native Fast CONT refresh in both orders."""

import argparse
import json
from itertools import product
from pathlib import Path

from trace_native_fast_cont import ACTIVE, PWM, RESULT, RET, STORED, sha
from trace_native_fast_cont_refresh import NativeRefresh, restore_globals
from trace_uart_correlation import NEST, TOP
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
)

KEY_TASK = 0x8000551C
KEY_LOOP = 0x80005528
KEY_WORD = 0x805ABB9C
WATCHDOG = 0x01C20CB0
KEY_SAMPLE = 0x123


class OrderingReplay(NativeRefresh):
    def code(self, u, pc, size, data):
        if pc == 0x800059DC:
            args = [u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
            self.registration = args
            u.reg_write(UC_ARM_REG_PC, RET)
            return
        if pc == KEY_LOOP:
            if self.iteration_entered:
                u.reg_write(UC_ARM_REG_PC, RET)
                return
            self.iteration_entered = True
        if (pc, u.reg_read(UC_ARM_REG_LR)) in ((0x8000241C, 0x8000552C), (0x80060FBC, 0x80005538)):
            value = u.reg_read(UC_ARM_REG_R0)
            if pc == 0x8000241C:
                self.modeled_calls.append(["key_sample", KEY_SAMPLE])
                u.reg_write(UC_ARM_REG_R0, KEY_SAMPLE)
            else:
                self.modeled_calls.append(["delay_argument", value])
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if (
            KEY_TASK <= pc <= 0x80005578 or 0x800085C4 <= pc < 0x800085DC
            or 0x800059C0 <= pc < 0x800059DC
        ):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            self.instruction_count += 1
            return
        super().code(u, pc, size, data)

    def memory(self, u, access, address, size, value, data):
        if address in (WATCHDOG, KEY_WORD):
            assert size == 4
            return
        super().memory(u, access, address, size, value, data)

    def iteration(self):
        self.modeled_calls = []
        self.iteration_entered = False
        sample_counter = self.rd(RESULT + 0x18)
        sound_index = len(self.audio)
        before = self.sound_state()
        watchdog_before = self.rd(WATCHDOG)
        u = self.u
        context = u.context_save()
        try:
            u.reg_write(UC_ARM_REG_CPSR, 0x13)
            u.reg_write(UC_ARM_REG_SP, TOP)
            u.reg_write(UC_ARM_REG_LR, RET)
            u.emu_start(KEY_TASK, 0, count=50000)
            assert u.reg_read(UC_ARM_REG_PC) == RET and u.reg_read(UC_ARM_REG_SP) == TOP
            assert [u.reg_read(reg) for reg in (UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6)] == [
                RESULT, KEY_WORD, ACTIVE,
            ]
            assert self.rd(NEST) == 0
        finally:
            u.context_restore(context)
        assert self.iteration_entered and self.modeled_calls == [["key_sample", KEY_SAMPLE], ["delay_argument", 50]]
        assert self.rd(KEY_WORD) == KEY_SAMPLE and self.rd(WATCHDOG) == watchdog_before | 0x14AF
        assert self.rd(RESULT + 0x18) == sample_counter + 1
        assert self.result() == STORED
        after = self.sound_state()
        assert all(after[k] == before[k] for k in ("ring", "fill", "index", "median"))
        assert after["countdown"] == max(before["countdown"] - 1, 0)
        off = before["active"] == 1 and after["countdown"] == 0
        assert after["active"] == (0 if off else before["active"])
        assert self.audio[sound_index:] == ([["0x80005568", 5, 0]] if off else [])
        if off:
            assert int(after["pwm_period"], 16) & 0xFFFF == 0
        return dict(key_sample=KEY_SAMPLE, delay_argument=50, watchdog_after=hex(self.rd(WATCHDOG)),
                    sample_counter_after=self.rd(RESULT + 0x18),
                    sound_gate_calls=self.audio[sound_index:], sound_after=after)

    def run_order(self, loop_first, initial_countdown):
        self.initial_active = True
        self.run_case(1, 1, 0)
        self.u.reg_write(UC_ARM_REG_R4, 1)
        self.invoke(0x800059C0)
        assert self.registration == [KEY_TASK, 0x80005A68, 0x800, 0]
        assert bytes(self.u.mem_read(self.registration[1], 8)) == b"KeyTask\0"
        first = self.native_refresh()
        assert first["warmup"] == [1, 2] and not first["render_records"]
        self.finish_request(first["tick"], 4, 10001, 3, "none")
        assert self.result() == STORED
        self.put(RESULT + 0x50, initial_countdown)
        self.put(RESULT + 0x18, 0)
        self.put(WATCHDOG, 0x10000)
        before = self.sound_state()
        if loop_first:
            first_loop = self.iteration()
            refresh = self.native_refresh()
        else:
            refresh = self.native_refresh()
            first_loop = self.iteration()
        assert refresh["stored_at_entry"] == STORED and refresh["filter_inputs"] == [5]
        assert refresh["sound_gate_calls"] == [["0x80003970", 10, 1]]
        assert refresh["sound_after_callback"]["countdown"] == 3
        assert refresh["sound_after_callback"]["pwm_period"] == "0x176f0a8c"
        assert bool(first_loop["sound_gate_calls"]) == (loop_first and initial_countdown == 1)
        combined = self.sound_state()
        assert combined["active"] == 1 and combined["countdown"] == (3 if loop_first else 2)
        followup = [self.iteration() for _ in range(combined["countdown"])]
        assert all(not step["sound_gate_calls"] for step in followup[:-1])
        assert followup[-1]["sound_gate_calls"] == [["0x80005568", 5, 0]]
        assert self.rd(ACTIVE) == 0 and self.result() == STORED
        assert not any(event["kind"] == "publish" for event in self.events)
        return dict(loop_first=loop_first, initial_countdown=initial_countdown, before=before,
                    first_loop=first_loop, refresh=refresh, after_both=combined,
                    followup_without_refresh=followup)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    images = [(item, (root / item["path"]).read_bytes()) for item in manifest["images"]]
    assert all(len(raw) == item["size_bytes"] and sha(raw) == item["sha256"] for item, raw in images)
    initialized = restore_globals(next(raw for item, raw in images if item["version"] == "V3.8"))
    results, versions = [], []
    for item, raw in images:
        replay = OrderingReplay(raw)
        replay.initialized_globals = initialized
        cases = [replay.run_order(*pair) for pair in product((False, True), (1, 2))]
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())
                    if KEY_TASK <= pc <= 0x80005578 or 0x800059C0 <= pc < 0x800059DC
                    or 0x800085C4 <= pc < 0x800085DC or pc in (0x80006EB8, 0x80006EF0, 0x8005D248)}
        assert coverage["0x80006eb8"] == "500085e5" and coverage["0x80005578"] == "eaffffea"
        results.append((cases, coverage))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], schedules=len(cases)))
    assert results[0] == results[1]
    payload = dict(schema="ys4470.key-task-fast-cont-ordering.v1", versions=versions,
                   key_task_entry=hex(KEY_TASK), registration_site="0x800059dc", registration_name="KeyTask",
                   registration_args=["0x8000551c", "0x80005a68", "0x800", "0x0"],
                   schedules=results[0][0], instruction_bytes=results[0][1],
                   limits=["Original registration argument setup, KeyTask loop, watchdog helper, timer/refresh and sound paths execute.",
                           "Task creation is observed at its call boundary; key sampling and delay scheduling are modeled.",
                           "Each loop runs through its backward branch. The host chooses callback ordering between whole loop iterations.",
                           "Hardware state is a register shadow. There is no measured time unit or physical timing."])
    output = json.dumps(payload, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
