"""Recover GUI -> event-record -> dispatcher evidence from original ARM bytes.

Executions stop at API boundaries: no queue function, GUI framework,
TransactionBuilder, shared FSM epilogue, or physical peripheral is emulated.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_READ, UC_PROT_WRITE,
                     UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_R4, UC_ARM_REG_R6, UC_ARM_REG_SP,
                               UC_ARM_REG_LR, UC_ARM_REG_PC)

from emulate_state5_parser import BASE, CONTROL, EXPECTED_INPUTS, reference
from trace_state5_discard_lifecycle import LifecycleMachine, expected_producer

HELPER, QUEUE = 0x80006778, 0x80061ACC
GUI, STATE, SETTINGS = 0x805AC098, 0x805ABEFC, 0x805AC770
STACK, TOP, RETURN = 0x10000000, 0x10000FF0, 0x80006800
QUEUE_HANDLE = 0x10002000  # opaque synthetic handle; never dereferenced
LABELS = (
    ("Voltage", 0x80051710, 0x2A4),
    ("Resistance", 0x80051720, 0x2AC),
    ("Capacitance", 0x8005172C, 0x2B4),
    ("Diode", 0x80051738, 0x2C0),
    ("Buzzer", 0x80051744, 0x2C4),
)


def word(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - BASE)[0]


def arm_callers(image: bytes) -> list[int]:
    """Aligned direct ARM BL candidates across the whole raw image.

    This is not a Thumb/indirect-call or data-versus-code proof.
    """
    sites = []
    for offset in range(0, len(image) - 3, 4):
        raw = struct.unpack_from("<I", image, offset)[0]
        if raw >> 28 == 15 or raw & 0x0F000000 != 0x0B000000:
            continue
        displacement = ((raw & 0xFFFFFF) ^ 0x800000) - 0x800000
        if (BASE + offset + 8 + displacement * 4) & 0xFFFFFFFF == HELPER:
            sites.append(BASE + offset)
    return sites


class EventMachine:
    def __init__(self, image: bytes):
        self.image = image
        self.mu = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.mu.ctl_set_cpu_model(UC_CPU_ARM_926)
        pages = {0x80006000, 0x8000D000, 0x80044000, 0x80045000,
                 0x80051000, QUEUE & ~0xFFF, 0x80032000, 0x80033000,
                 0x80024000}
        for page in sorted(pages):
            self.mu.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
            self.mu.mem_write(page, image[page - BASE:page - BASE + 0x1000])
        for page in {CONTROL & ~0xFFF, GUI & ~0xFFF, STATE & ~0xFFF, STACK}:
            self.mu.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
        self.stops: set[int] = set()
        self.allowed: list[tuple[int, int]] = []
        self.writes: list[tuple[int, int]] = []
        self.mu.hook_add(UC_HOOK_CODE, self.on_code)
        self.mu.hook_add(UC_HOOK_MEM_WRITE, self.on_write)

    def on_code(self, mu, address, size, user_data):
        if address in self.stops:
            mu.emu_stop()
        elif size != 4 or not any(start <= address < end for start, end in self.allowed):
            raise RuntimeError(f"execution escaped bounded regions at {address:#x}")

    def on_write(self, mu, access, address, size, value, user_data):
        if not (STACK <= address and address + size <= STACK + 0x1000
                or (address, size) == (STATE, 1)):
            raise RuntimeError(f"unexpected guest write {address:#x}/{size}")
        self.writes.append((address, size))

    def reset(self, queue_handle=QUEUE_HANDLE):
        self.mu.mem_write(STACK, b"\xcc" * 0x1000)
        self.mu.mem_write(CONTROL + 4, struct.pack("<I", queue_handle))
        self.mu.reg_write(UC_ARM_REG_CPSR, 0x13)
        self.mu.reg_write(UC_ARM_REG_SP, TOP)
        self.mu.reg_write(UC_ARM_REG_LR, RETURN)
        self.writes.clear()

    def run(self, start, stops, allowed):
        self.stops, self.allowed = set(stops), allowed
        self.mu.emu_start(start, 0x80006FFC, count=128)
        pc = self.mu.reg_read(UC_ARM_REG_PC)
        if pc not in self.stops:
            raise RuntimeError("experiment exceeded its instruction bound")
        return pc

    def capture_record(self, pc):
        if pc != QUEUE:
            return None
        pointer = self.mu.reg_read(UC_ARM_REG_R1)
        if pointer != TOP - 0x48:
            raise AssertionError("unexpected event-record stack layout")
        record = bytes(self.mu.mem_read(pointer, 0x44))
        if record[6:] != b"\xcc" * 62:
            raise AssertionError("helper changed bytes beyond record fields 0..5")
        return {"case": struct.unpack_from("<I", record)[0],
                "byte4": record[4], "byte5": record[5],
                "queue_r0": self.mu.reg_read(UC_ARM_REG_R0),
                "queue_r2": self.mu.reg_read(UC_ARM_REG_R2),
                "queue_r3": self.mu.reg_read(UC_ARM_REG_R3)}

    def helper(self, case, byte4, byte5, enabled):
        self.reset(QUEUE_HANDLE if enabled else 0)
        for reg, value in ((UC_ARM_REG_R0, case), (UC_ARM_REG_R1, byte4), (UC_ARM_REG_R2, byte5)):
            self.mu.reg_write(reg, value)
        pc = self.run(HELPER, (QUEUE, RETURN), [(HELPER, 0x800067C4)])
        if pc == RETURN and self.mu.reg_read(UC_ARM_REG_SP) != TOP:
            raise AssertionError("null-handle early return failed to restore SP")
        return self.capture_record(pc)

    def gui_branch(self, branch, setting, enabled):
        self.reset(QUEUE_HANDLE if enabled else 0)
        self.mu.mem_write(SETTINGS + 0x18, struct.pack("<I", setting))
        definitions = {
            "buzzer_callback": (0x8000D084, [(0x8000D084, 0x8000D0CC)], (0x8000D0A4, 0x8000D0CC)),
            "buzzer_selector": (0x800450B4, [(0x800450B4, 0x80045140)], (0x800450D4, 0x80045140)),
            "diode_callback_tail": (0x8000D19C, [(0x8000D19C, 0x8000D1A0), (0x8000D0BC, 0x8000D0CC)], (0x8000D0CC,)),
            "diode_selector": (0x80045044, [(0x80045044, 0x80045054)], (0x80045054,)),
        }
        start, regions, returns = definitions[branch]
        pc = self.run(start, (QUEUE, *returns), regions + [(HELPER, 0x800067C4)])
        return self.capture_record(pc)

    def labels_and_callback(self):
        rows = []
        for text, entry, offset in LABELS:
            self.reset()
            handle = 0x20000000 + offset
            self.mu.mem_write(GUI + offset, struct.pack("<I", handle))
            self.mu.reg_write(UC_ARM_REG_R4, GUI)
            self.run(entry, (0x80032038,), [(entry, entry + 20)])
            if self.mu.reg_read(UC_ARM_REG_R0) != handle:
                raise AssertionError("label target mismatch")
            address = self.mu.reg_read(UC_ARM_REG_R1)
            literal = self.image[address - BASE:].split(b"\0", 1)[0].decode("ascii")
            if literal != text:
                raise AssertionError((text, literal))
            rows.append({"text": text, "text_address": hex(address),
                         "object_offset": hex(offset), "setter_call_from_slice": hex(entry)})
        self.reset()
        self.mu.mem_write(GUI + 0x2B8, struct.pack("<I", 0x200002B8))
        self.mu.reg_write(UC_ARM_REG_R4, GUI)
        self.run(0x80051894, (0x800338DC,), [(0x80051894, 0x800518A8)])
        callback = [self.mu.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        if callback != [0x200002B8, 0x8000CFD0, 1, 0]:
            raise AssertionError("GUI callback registration contract mismatch")
        return {"label_assignments": rows, "callback_registration": {
            "object_offset": "0x2b8", "callback": hex(callback[1]),
            "event_argument": callback[2], "user_data": callback[3]}}

    def mode_switch(self, index):
        self.reset()
        self.mu.mem_write(STATE, b"\x99")
        self.mu.reg_write(UC_ARM_REG_R4, GUI)
        self.mu.reg_write(UC_ARM_REG_R6, index)
        pc = self.run(0x80044EA8, (0x80024CA4, 0x800339BC, 0x80045158),
                      [(0x80044EA8, 0x8004515C)])
        actual = self.mu.mem_read(STATE, 1)[0]
        if actual != (index if index < 5 else 0x99):
            raise AssertionError("mode switch state mismatch")
        return {"index": index, "mode_byte": actual, "stop_before": hex(pc)}


def collect(label: str, path: Path):
    image = path.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if EXPECTED_INPUTS.get(label) != digest:
        raise ValueError("only pinned originals are accepted")
    machine = EventMachine(image)
    fingerprint = hashlib.sha256()
    values4, values5 = (0, 13, 34, 0x10E, 0xFFFFFFFF), (0, 19, 25, 0x115, 0xFFFFFFFF)
    cases = list(itertools.product((*range(8), 0x103), values4, values5, (False, True)))
    for case, p4, p5, enabled in cases:
        actual = machine.helper(case, p4, p5, enabled)
        expected = {"case": case, "byte4": p4 & 255, "byte5": p5 & 255,
                    "queue_r0": QUEUE_HANDLE, "queue_r2": 0 if case == 3 else 10, "queue_r3": 0} if enabled else None
        if actual != expected:
            raise AssertionError((case, p4, p5, enabled, actual))
        fingerprint.update(json.dumps([case, p4, p5, enabled, actual], sort_keys=True).encode())
    gui_cases = list(itertools.product(("buzzer_callback", "buzzer_selector", "diode_callback_tail", "diode_selector"),
                                      (0, 1, 2, 0xFFFFFFFF), (False, True)))
    pipeline = LifecycleMachine(image)
    examples, parser_entries = [], 0
    for branch, setting, enabled in gui_cases:
        actual = machine.gui_branch(branch, setting, enabled)
        special = branch.startswith("buzzer") and setting == 1
        expected = {"case": 5 if special else 2,
                    "byte4": 34 if special else 14,
                    "byte5": 19 if special else 25,
                    "queue_r0": QUEUE_HANDLE, "queue_r2": 10, "queue_r3": 0} if enabled else None
        if actual != expected:
            raise AssertionError((branch, setting, enabled, actual))
        row = {"branch": branch, "setting": setting, "queue_enabled": enabled, "event": actual}
        if actual is not None:
            decoded = actual["case"], actual["byte4"], actual["byte5"]
            setup = pipeline.produce(*decoded)
            if setup != expected_producer(*decoded):
                raise AssertionError("observed event/dispatcher mismatch")
            steps = []
            for _ in range(3):
                count = pipeline.mu.mem_read(CONTROL + 1, 1)[0]
                observed = pipeline.execute(5001, 0x1D, 7, setup["control"], count, preserve_state=True)
                if observed != reference(5001, 0x1D, 7, setup["control"], count):
                    raise AssertionError("event/dispatcher/parser mismatch")
                steps.append(observed)
                parser_entries += 1
            row.update(dispatch=setup, three_parser_entries=steps)
        if setting in (0, 1) and (enabled or setting == 1 and branch.startswith("buzzer")):
            examples.append(row)
        fingerprint.update(json.dumps(row, sort_keys=True).encode())
    gui = machine.labels_and_callback()
    switches = [machine.mode_switch(index) for index in (*range(7), 255, 0xFFFFFFFF)]
    callers = arm_callers(image)
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    def window(start, end):
        blob = image[start - BASE:end - BASE]
        return {"start": hex(start), "end_exclusive": hex(end), "sha256": hashlib.sha256(blob).hexdigest(),
                "listing_scope": "Per-word decode; includes literal pools and jump tables, not a whole-window code classification",
                "assembly": [{"address": hex(i.address), "assembly": f"{i.mnemonic} {i.op_str}"}
                             for address in range(start, end, 4)
                             for i in md.disasm(image[address - BASE:address - BASE + 4], address)]}
    return {"version": label, "input_sha256": digest, "cpu_model": "UC_CPU_ARM_926",
            "helper_cases_passed": len(cases), "gui_branch_cases_passed": len(gui_cases),
            "pipeline_parser_entries_passed": parser_entries,
            "gui_binding_slices_passed": 6, "mode_switch_cases_passed": len(switches), "failed": 0,
            "results_sha256": fingerprint.hexdigest(), "gui_bindings": gui,
            "mode_switch": switches, "gui_branch_examples": examples,
            "aligned_direct_arm_bl_candidates": [hex(a) for a in callers],
            "caller_windows": [window(a - 12, a + 4) for a in callers],
            "windows": {"event_builder": window(HELPER, 0x800067C8),
                        "callback": window(0x8000CFD0, 0x8000D1C0),
                        "selector": window(0x80044E54, 0x80045180),
                        "gui_labels_and_registration": window(0x80051710, 0x800518A8)},
            "settings_word": hex(SETTINGS + 0x18)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", required=True, metavar="VERSION=PATH")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    results = [collect(label, Path(path)) for label, path in (item.split("=", 1) for item in args.input)]
    shared = {}
    if results and all({name: w["sha256"] for name, w in r["windows"].items()} ==
                       {name: w["sha256"] for name, w in results[0]["windows"].items()}
                       for r in results):
        shared = results[0]["windows"]
        for r in results:
            r["windows"] = {name: {"start": w["start"], "end_exclusive": w["end_exclusive"],
                                    "sha256": w["sha256"], "assembly_reference": "shared_assembly_windows." + name}
                            for name, w in r["windows"].items()}
    report = {"schema": "ys4470.measurement-event-sources.v1", "date": "2026-11-06",
              "scope": "bounded GUI label/registration, event-record construction, selector branch and parser linkage",
              "limits": ["Direct ARM BL scan does not cover Thumb or indirect calls and can include data candidates.",
                         "Per-word disassembly windows also contain literal pools and jump tables; only bounded execution paths are verified code.",
                         "GUI text/color associations do not validate analog measurement semantics.",
                         "Full GUI callbacks are not executed; only documented slices are executed to API boundaries.",
                         "Queue submission, transport, actual UI event dispatch and shared parser epilogue are not emulated.",
                         "Setting word 0x805ac788 semantics are not yet named; queue r2=10 has no assigned time unit."],
              "shared_assembly_windows": shared, "versions": results}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"versions": len(results), "helper_cases_passed": sum(r["helper_cases_passed"] for r in results),
                      "gui_branch_cases_passed": sum(r["gui_branch_cases_passed"] for r in results),
                      "pipeline_parser_entries_passed": sum(r["pipeline_parser_entries_passed"] for r in results),
                      "gui_binding_slices_passed": sum(r["gui_binding_slices_passed"] for r in results),
                      "mode_switch_cases_passed": sum(r["mode_switch_cases_passed"] for r in results),
                      "call_candidates_per_version": [len(r["aligned_direct_arm_bl_candidates"]) for r in results],
                      "version_outputs_equal": len({r["results_sha256"] for r in results}) == 1}))


if __name__ == "__main__":
    main()
