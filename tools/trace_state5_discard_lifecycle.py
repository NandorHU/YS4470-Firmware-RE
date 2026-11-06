"""Trace and execute countdown producers followed by retained parser state.

Uses original V3.6/V3.8 bytes. The input dispatcher executes up to (but not
into) TransactionBuilder; the harness captures its command arguments. It
then invokes the state-5 slice with persistent control/result RAM. This is
not a transport, queue, scheduler, or complete task emulation.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import UC_PROT_EXEC, UC_PROT_READ, UC_PROT_WRITE
from unicorn.arm_const import (UC_ARM_REG_CPSR, UC_ARM_REG_R0, UC_ARM_REG_R1,
                               UC_ARM_REG_R2, UC_ARM_REG_PC, UC_ARM_REG_SP,
                               UC_ARM_REG_LR)

from emulate_state5_parser import (BASE, CONTROL, RESULT, EXPECTED_INPUTS,
                                   INITIAL_VALUE, INITIAL_SELECTOR,
                                   ParserMachine, reference)
from trace_arm_literal_object import analyze as trace_literals

DISPATCH = 0x80004390
BUILDER, RETURN = 0x8000489C, 0x800049FC
STACK_PAGE, RECORD, STACK_TOP = 0x10000000, 0x10001000, 0x10000FF0


class LifecycleMachine(ParserMachine):
    def __init__(self, image: bytes):
        self.phase = "parser"
        self.dispatch_addresses: set[int] = set()
        super().__init__(image)
        self.mu.mem_map(STACK_PAGE, 0x2000, UC_PROT_READ | UC_PROT_WRITE)
        self.mu.mem_map(0x80005000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
        self.mu.mem_write(0x80005000, image[0x80005000 - BASE:0x80006000 - BASE])

    def on_code(self, mu, address, size, user_data):
        if self.phase == "producer":
            if address == BUILDER:
                mu.emu_stop()
                return
            if not (DISPATCH <= address <= 0x80004488 and size == 4):
                raise RuntimeError(f"unexpected producer execution: {address:#x}")
            self.dispatch_addresses.add(address)
        elif self.phase == "task_guard":
            if address in (0x80005BD4, 0x80005BE4):
                mu.emu_stop()
                return
            if not (0x80005BB8 <= address <= 0x80005BD4 and size == 4):
                raise RuntimeError(f"unexpected task guard execution: {address:#x}")
        else:
            super().on_code(mu, address, size, user_data)

    def on_write(self, mu, access, address, size, value, user_data):
        if self.phase == "producer":
            if not (STACK_PAGE <= address and address + size <= STACK_PAGE + 0x1000
                    or (address, size) in ((CONTROL + 1, 1), (CONTROL + 8, 4))):
                raise RuntimeError(f"unexpected producer write {address:#x}/{size}")
            self.writes.append((address, size))
        elif self.phase == "task_guard":
            raise RuntimeError("task guard unexpectedly wrote memory")
        else:
            super().on_write(mu, access, address, size, value, user_data)

    def produce(self, case: int, config: int, secondary: int) -> dict:
        mu = self.mu
        mu.mem_write(CONTROL, b"\0" * 16)
        mu.mem_write(CONTROL + 1, b"\x55")
        mu.mem_write(CONTROL + 8, struct.pack("<I", 0x66))
        mu.mem_write(RESULT + 0x1C, struct.pack("<II", INITIAL_VALUE, INITIAL_SELECTOR))
        mu.mem_write(RECORD, struct.pack("<I", case) + bytes((config, secondary)))
        mu.reg_write(UC_ARM_REG_CPSR, 0x13)
        mu.reg_write(UC_ARM_REG_R0, RECORD)
        mu.reg_write(UC_ARM_REG_SP, STACK_TOP)
        mu.reg_write(UC_ARM_REG_LR, RETURN)
        self.writes.clear()
        self.phase = "producer"
        mu.emu_start(DISPATCH, RETURN, count=100)
        pc = mu.reg_read(UC_ARM_REG_PC)
        if pc not in (BUILDER, RETURN):
            raise RuntimeError("input dispatcher exceeded its 100-instruction bound")
        commands = []
        builder_kind = None
        if pc == BUILDER:
            count, pointer = mu.reg_read(UC_ARM_REG_R2), mu.reg_read(UC_ARM_REG_R1)
            if count not in (1, 3, 4) or not STACK_PAGE <= pointer < STACK_TOP:
                raise RuntimeError("unexpected TransactionBuilder argument contract")
            commands = list(struct.unpack("<" + "I" * count, mu.mem_read(pointer, count * 4)))
            builder_kind = mu.reg_read(UC_ARM_REG_R0)
        control_writes = [(hex(a), s) for a, s in self.writes if a >= CONTROL]
        self.phase = "parser"
        return {"countdown": mu.mem_read(CONTROL + 1, 1)[0],
                "control": struct.unpack("<I", mu.mem_read(CONTROL + 8, 4))[0],
                "commands": commands, "builder_kind": builder_kind,
                "control_writes": control_writes}

    def task_guard(self, case: int) -> str:
        mu = self.mu
        mu.mem_write(STACK_PAGE + 0x800, struct.pack("<I", case))
        mu.reg_write(UC_ARM_REG_CPSR, 0x13)
        mu.reg_write(UC_ARM_REG_SP, STACK_PAGE + 0x800)
        self.phase = "task_guard"
        mu.emu_start(0x80005BB8, 0x80005BE8, count=16)
        pc = mu.reg_read(UC_ARM_REG_PC)
        self.phase = "parser"
        if pc == 0x80005BD4:
            return "deferred_copy_call"
        if pc == 0x80005BE4:
            return "immediate_dispatch"
        raise RuntimeError("task guard did not reach a verified stop")


def expected_producer(case: int, config: int, secondary: int) -> dict:
    normalized = secondary if 19 <= secondary <= 24 else 25
    if case == 2:
        return {"countdown": 2, "control": config,
                "commands": [config, normalized, 29], "builder_kind": 3,
                "control_writes": [(hex(CONTROL + 8), 4), (hex(CONTROL + 1), 1)]}
    if case == 5:
        return {"countdown": 2, "control": 34,
                "commands": [12, 34, 19, 29], "builder_kind": 3,
                "control_writes": [(hex(CONTROL + 8), 4), (hex(CONTROL + 1), 1)]}
    return {"countdown": 85, "control": 102,
            "commands": {3: [29], 4: [27]}.get(case, []),
            "builder_kind": {3: 1, 4: 2}.get(case), "control_writes": []}


def collect(label: str, path: Path) -> dict:
    image = path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if EXPECTED_INPUTS.get(label) != digest:
        raise ValueError("only pinned original V3.6 and V3.8 inputs are accepted")
    machine = LifecycleMachine(image)
    vectors = list(itertools.product(range(8), (0, 9, 13, 14, 34, 255),
                                     (0, 18, 19, 20, 24, 25, 255)))
    vectors += [(2, 13, secondary) for secondary in range(256)]
    fingerprint = hashlib.sha256()
    for case in vectors:
        actual = machine.produce(*case)
        if actual != expected_producer(*case):
            raise AssertionError((case, actual, expected_producer(*case)))
        fingerprint.update(json.dumps([case, actual], sort_keys=True).encode())
    lifecycles = list(itertools.product((2, 5), (0, 13, 14, 34),
                                       (5000, 5001, 0xFFFFFF), (6, 7)))
    examples = []
    for case, config, raw, selector in lifecycles:
        setup = machine.produce(case, config, 19)
        prior_value, prior_selector = INITIAL_VALUE, INITIAL_SELECTOR
        steps = []
        for step in range(4):
            # Count from actual RAM, retaining the producer's control and result state.
            count = machine.mu.mem_read(CONTROL + 1, 1)[0]
            current_raw = raw if step < 3 else (raw + 1) & 0xFFFFFF
            actual = machine.execute(current_raw, setup["commands"][-1], selector,
                                     setup["control"], count, preserve_state=True)
            expected = reference(current_raw, 0x1D, selector, setup["control"], count)
            if count:
                expected.update(value_u32=prior_value, selector=prior_selector)
            if actual != expected:
                raise AssertionError((case, step, actual, expected))
            prior_value, prior_selector = actual["value_u32"], actual["selector"]
            steps.append(actual)
            fingerprint.update(json.dumps([case, config, raw, selector, step, actual], sort_keys=True).encode())
        if [s["published"] for s in steps] != [False, False, True, True]:
            raise AssertionError("countdown publication sequence changed")
        if selector == 7 and config == 13:
            examples.append({"software_case": case, "config": config,
                             "raw24": raw, "setup": setup, "four_parser_entries": steps})
    guard = {str(case): machine.task_guard(case) for case in range(8)}
    if guard != {str(c): "immediate_dispatch" if c in (3, 4) else "deferred_copy_call" for c in range(8)}:
        raise AssertionError("unexpected normal task-entry routing")
    windows = {}
    for name, start, end in (("input_dispatcher", DISPATCH, 0x80004490),
                             ("task_selection_and_deferred_call", 0x80005B70, 0x80005D24),
                             ("startup_alias_rejection", 0x80005E50, 0x80005E84)):
        blob = image[start - BASE:end - BASE]
        code_end = end - (4 if name == "input_dispatcher" else 12)
        windows[name] = {"start": hex(start), "end_exclusive": hex(end),
                         "sha256": hashlib.sha256(blob).hexdigest(),
                         "assembly": [{"address": hex(i.address), "assembly": f"{i.mnemonic} {i.op_str}"}
                                      for i in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(image[start - BASE:code_end - BASE], start)]}
    candidates = trace_literals(path, BASE, CONTROL, {1}, 256)
    startup_pointer = struct.unpack_from("<I", image, 0x80005E80 - BASE)[0]
    if startup_pointer == CONTROL:
        raise AssertionError("UART startup alias rejection is invalid")
    return {"version": label, "input_sha256": digest,
            "producer_cases_passed": len(vectors), "lifecycle_scenarios_passed": len(lifecycles),
            "persistent_parser_entries_passed": len(lifecycles) * 4,
            "task_guard_cases_passed": len(guard), "failed": 0,
            "results_sha256": fingerprint.hexdigest(), "task_guard_routing": guard,
            "producer_instruction_addresses_visited": sorted(hex(a) for a in machine.dispatch_addresses),
            "examples": examples, "raw_windows": windows,
            "uart_startup_r4_reload": {"instruction": "0x80005e50",
                                       "literal_address": "0x80005e80",
                                       "object_address": hex(startup_pointer)},
            "bounded_literal_candidates": candidates}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, metavar="VERSION=PATH")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = []
    for item in args.input:
        label, raw_path = item.split("=", 1)
        results.append(collect(label, Path(raw_path)))
    report = {"schema": "ys4470.state5-discard-lifecycle.v1",
              "cpu_model": "UC_CPU_ARM_926", "date": "2026-11-06",
              "findings": {"input_case_2": "control=input[4], discard count=2, commands=[input[4], normalize(input[5]), 0x1d]",
                           "input_case_5": "control=0x22, discard count=2, commands=[0x0c,0x22,0x13,0x1d]",
                           "publication": "first two admitted state-5 entries preserve result; third may publish",
                           "task_guard": "normal task selection defers cases 2/5; its direct 2/5 store blocks are not reached from this guard",
                           "alias_correction": "0x80005e60 is a UART startup-buffer write after r4 was reloaded at 0x80005e50, not a countdown producer"},
              "limits": ["Stops before TransactionBuilder and shared parser epilogue; neither queue nor UART transport is emulated.",
                         "Task guard is a bounded execution from 0x80005bb8 with synthetic stack input.",
                         "Literal scan candidates are not exhaustive alias analysis; whole-object resets and alternate entry points remain open.",
                         "No physical mode, measurement unit, cadence, or audible delay is established."],
              "versions": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"versions": len(results),
                      "producer_cases_passed": sum(r["producer_cases_passed"] for r in results),
                      "lifecycle_scenarios_passed": sum(r["lifecycle_scenarios_passed"] for r in results),
                      "persistent_parser_entries_passed": sum(r["persistent_parser_entries_passed"] for r in results),
                      "task_guard_cases_passed": sum(r["task_guard_cases_passed"] for r in results),
                      "all_outputs_equal": len({r["results_sha256"] for r in results}) == 1}))


if __name__ == "__main__":
    main()
