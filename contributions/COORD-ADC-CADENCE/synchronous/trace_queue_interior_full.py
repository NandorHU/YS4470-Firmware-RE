"""Bound queue entry aliases and exercise original full-queue sends."""

import argparse
import hashlib
import json
import struct
from bisect import bisect_left, bisect_right
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs
from trace_gauge_scheduled_service import GaugeReplay, QUEUE, SCHED, TASK, OTHER, NATIVE_PRODUCER, NATIVE_STOP
from trace_scheduler_delay_wake import CURRENT
from trace_scheduler_irq_context import FOREGROUND_SP, OTHER_PC, REGS, SELECT, SVC_ENTRY
from trace_timer0_uart2_irq import CTRL, TIMER_SLOT
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R2, UC_ARM_REG_R3,
)

BASE = 0x7FFFFFE0
PRODUCER = 0x80006778
SEND = 0x80061ACC
RECEIVE = 0x800618DC
HANDLE = CTRL + 4
DEFERRED = 0x805AC6D0
DRAIN = 0x10016800
CANDIDATE = 0x8009EF10
INTERIOR = 0x80061B18
REGIONS = ((0x800029DC, 0x800029FC), (PRODUCER, 0x800067C4), (0x80061838, 0x80061CD4))
ENTRIES = {0x800029DC, PRODUCER, 0x80061838, SEND, RECEIVE}
OBJECTS = {CTRL, HANDLE, DEFERRED}
EXTRA_WINDOWS = (
    (0x80042A00, 0x80042AA0), (0x80060FF8, 0x80061034), (0x80061184, 0x8006119C),
    (0x800612E0, 0x800612F4), (0x80061CD4, 0x80061D58), (0x80062178, 0x80062204),
)
SEND_ANCHORS = (SEND, 0x80061B0C, INTERIOR, 0x80061C1C, 0x80061C28, 0x80061C58,
                0x80061CA8, 0x80061CBC, 0x80061CC0, 0x80061C70, 0x80061C08)


def inside(target):
    return any(start <= target < end for start, end in REGIONS)


def crosses_region(pc, target):
    return inside(target) and not any(start <= pc < end and start <= target < end for start, end in REGIONS)


def signed(value, bits):
    pivot = 1 << (bits - 1)
    return (value ^ pivot) - pivot


def describe(decoder, raw, pc, size, target):
    code = raw[pc - BASE:pc - BASE + size]
    insn, = decoder.disasm(code, pc)
    assert insn.size == size
    return dict(pc=hex(pc), bytes=code.hex(), assembly=f"{insn.mnemonic} {insn.op_str}", target=hex(target))


def static_index(raw):
    arm, thumb = (Cs(CS_ARCH_ARM, mode) for mode in (CS_MODE_ARM, CS_MODE_THUMB))
    branch, aliases, pointers, incoming_candidate = [], [], [], []
    field_accesses = {}
    candidate_context = (CANDIDATE - 0x20, CANDIDATE + 0x24)
    end = BASE + len(raw)
    for n, (word,) in enumerate(struct.iter_unpack("<I", raw)):
        pc = BASE + n * 4
        register, field = (word >> 16) & 15, word & 0xFFF
        if (register not in (13, 15) and word >> 28 != 15
                and word & 0x0FE00000 == 0x05800000 and field in (0x38, 0x3C, 0x40)):
            field_accesses.setdefault(register, []).append((pc, field, bool(word & 0x100000)))
        if word >> 28 != 15 and word & 0x0E000000 == 0x0A000000:
            target = pc + 8 + 4 * signed(word & 0xFFFFFF, 24)
            if crosses_region(pc, target):
                branch.append(dict(isa="ARM", **describe(arm, raw, pc, 4, target)))
            if candidate_context[0] <= target < candidate_context[1]:
                incoming_candidate.append(dict(isa="ARM", **describe(arm, raw, pc, 4, target)))
        if word >> 28 != 15 and word & 0x0E0F0000 == 0x020F0000:
            opcode = (word >> 21) & 15
            if opcode in (2, 4):
                rotation = 2 * ((word >> 8) & 15)
                imm = ((word & 255) >> rotation | (word & 255) << (32 - rotation)) & 0xFFFFFFFF
                target = pc + 8 + (imm if opcode == 4 else -imm)
                if crosses_region(pc, target) or target in OBJECTS:
                    aliases.append(dict(isa="ARM", kind="adr", **describe(arm, raw, pc, 4, target)))
        if word & 0x0F7F0000 == 0x051F0000:
            literal = pc + 8 + (word & 0xFFF) * (1 if word & 0x800000 else -1)
            if BASE <= literal <= end - 4:
                target = struct.unpack_from("<I", raw, literal - BASE)[0]
                if crosses_region(pc, target & ~1) or target in OBJECTS:
                    aliases.append(dict(isa="ARM", kind="literal", literal=hex(literal),
                                        **describe(arm, raw, pc, 4, target)))
    for n, (hi,) in enumerate(struct.iter_unpack("<H", raw)):
        offset = n * 2
        pc = BASE + offset
        if hi & 0xF800 == 0xF000 and offset + 4 <= len(raw):
            lo = struct.unpack_from("<H", raw, offset + 2)[0]
            if lo & 0xF801 == 0xE800:
                disp = (signed(hi & 0x7FF, 11) << 12) + ((lo & 0x7FF) << 1)
                target = (pc + 4 + disp) & ~3
                if crosses_region(pc, target):
                    branch.append(dict(isa="Thumb", **describe(thumb, raw, pc, 4, target)))
                if candidate_context[0] <= target < candidate_context[1]:
                    incoming_candidate.append(dict(isa="Thumb", **describe(thumb, raw, pc, 4, target)))
        if hi & 0xF800 == 0xA000:
            target = ((pc + 4) & ~3) + 4 * (hi & 255)
            if crosses_region(pc, target) or target in OBJECTS:
                aliases.append(dict(isa="Thumb", kind="adr", **describe(thumb, raw, pc, 2, target)))
        if hi & 0xF800 == 0x4800:
            literal = ((pc + 4) & ~3) + 4 * (hi & 255)
            if BASE <= literal <= end - 4:
                target = struct.unpack_from("<I", raw, literal - BASE)[0]
                if crosses_region(pc, target & ~1) or target in OBJECTS:
                    aliases.append(dict(isa="Thumb", kind="literal", literal=hex(literal),
                                        **describe(thumb, raw, pc, 2, target)))
    for offset in range(4):
        extent = (len(raw) - offset) & ~3
        for n, (word,) in enumerate(struct.iter_unpack("<I", raw[offset:offset + extent])):
            target = word & ~1
            if target in ENTRIES or word in OBJECTS or candidate_context[0] <= target < candidate_context[1]:
                pointers.append(dict(pc=hex(BASE + offset + 4 * n), value=hex(word)))
    field_signatures = []
    for reg, accesses in field_accesses.items():
        pcs = [a[0] for a in accesses]
        for pc, field, is_load in accesses:
            if is_load or field != 0x38:
                continue
            nearby = accesses[bisect_left(pcs, pc - 0x200):bisect_right(pcs, pc + 0x200)]
            if {0x3C, 0x40} <= {offset for _, offset, load in nearby if load}:
                insn, = arm.disasm(raw[pc - BASE:pc - BASE + 4], pc)
                field_signatures.append(dict(pc=hex(pc), bytes=insn.bytes.hex(), base_register=reg,
                                             nearby=[[hex(a), hex(o), load] for a, o, load in nearby]))
    field_signatures.sort(key=lambda row: int(row["pc"], 16))
    assert [row["pc"] for row in field_signatures] == [
        "0x80046548", "0x8005d35c", "0x80061898", "0x8006197c", "0x80061bd4",
    ]
    task_event_init = {}
    for pc in (0x80061E14, 0x80061E1C, 0x80061E20):
        insn, = arm.disasm(raw[pc - BASE:pc - BASE + 4], pc)
        task_event_init[hex(pc)] = [insn.bytes.hex(), f"{insn.mnemonic} {insn.op_str}"]
    assert [value[1] for value in task_event_init.values()] == [
        "rsb r1, r5, #4", "str r1, [r4, #0x18]", "str r4, [r4, #0x24]",
    ]
    signature_context = {}
    for pc in (0x80046540, 0x80046548, 0x8004654C, 0x8005D27C, 0x8005D35C):
        insn, = arm.disasm(raw[pc - BASE:pc - BASE + 4], pc)
        signature_context[hex(pc)] = [insn.bytes.hex(), f"{insn.mnemonic} {insn.op_str}"]
    result_literal = struct.unpack_from("<I", raw, 0x8005D518 - BASE)[0]
    assert result_literal == 0x805AC714
    internal_targets = [row for row in branch if int(row["target"], 16) not in ENTRIES]
    assert any(row["pc"] == hex(CANDIDATE) and row["target"] == hex(INTERIOR) for row in internal_targets)
    assert any(row["pc"] == "0x800067b8" and row["target"] == hex(SEND) for row in branch)
    return dict(regions=[[hex(a), hex(b)] for a, b in REGIONS], external_immediate_branches=branch,
                interior_branch_candidates=internal_targets, address_materializations=aliases,
                unaligned_or_aligned_pointer_words=pointers, field_signatures=field_signatures,
                original_task_event_initializers=task_event_init,
                outside_signature_context=signature_context,
                outside_signature_result_literal={"0x8005d518": hex(result_literal)},
                raw_candidate_context=dict(start=hex(candidate_context[0]),
                                           bytes=raw[candidate_context[0] - BASE:candidate_context[1] - BASE].hex(),
                                           incoming_immediate_candidates=incoming_candidate))


class FullQueueReplay(GaugeReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.watched = []

    def code(self, u, pc, size, data):
        if pc in (*SEND_ANCHORS, SELECT, SVC_ENTRY):
            self.watched.append([hex(pc), self.read(SCHED + 0xC)])
        if any(start <= pc < stop for start, stop in EXTRA_WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        if DRAIN <= address and address + size <= DRAIN + 68:
            return
        super().write(u, access, address, size, value, data)

    def fill(self):
        self.prepare_tasks(False, 0x2B)
        for _ in range(9):
            self.enqueue(3, 0)
        assert self.read(QUEUE + 0x38) == 10
        # Original task creation writes the event-list owner and inverted priority.
        self.put(TASK + 0x18, 4 - self.read(TASK + 0x2C))
        self.put(TASK + 0x24, TASK)
        data = self.read(QUEUE)
        prefix = bytes(self.u.mem_read(data, 6))
        assert prefix.hex() == "010000002b19"
        self.watched.clear()
        return data, bytes(self.u.mem_read(data, 680))

    def run_full(self, scenario):
        u = self.u
        data, before = self.fill()
        if scenario == "zero-wait":
            u.reg_write(UC_ARM_REG_R2, 0)
            self.invoke_transport(PRODUCER, 3, 0)
            assert u.reg_read(UC_ARM_REG_R0) == 0
            assert bytes(u.mem_read(data, 680)) == before and self.read(QUEUE + 0x38) == 10
            assert [pc for pc, _ in self.watched] == [hex(SEND), "0x80061b0c", "0x80061c70"]
            return dict(scenario=scenario, return_value=0, elapsed=0, marks=self.watched[:])

        u.reg_write(UC_ARM_REG_CPSR, 0x1F)
        for reg, value in zip(REGS, [0x11110000 + i for i in range(13)] + [FOREGROUND_SP, 0x11223344]):
            u.reg_write(reg, value)
        self.transport_active = self.dispatch_svc = True
        try:
            u.emu_start(NATIVE_PRODUCER, 0, count=50000)
            assert u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER
            assert self.members(CURRENT) == [[hex(TASK + 4), 110]]
            assert self.read(QUEUE + 0x10) == 1 and self.read(QUEUE + 0x38) == 10
            assert bytes(u.mem_read(data, 680)) == before
            assert "0x80061c1c" in [pc for pc, _ in self.watched]
            assert "0x80061c28" in [pc for pc, _ in self.watched]
            assert "0x80061ca8" in [pc for pc, _ in self.watched]
            for counter in range(101, 111 if scenario == "timeout" else 104):
                events = self.enter(0x1F, OTHER_PC, 1 << 13, TIMER_SLOT)
                assert self.read(SCHED + 0xC) == counter
                if counter < 110:
                    assert u.reg_read(UC_ARM_REG_PC) == OTHER_PC and self.read(SCHED) == OTHER
                    assert ["pc", hex(SELECT)] not in events
                    assert self.read(QUEUE + 0x10) == 1
            if scenario == "space-available":
                for reg, value in zip((UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3),
                                      (QUEUE, DRAIN, 0, 0)):
                    u.reg_write(reg, value)
                u.reg_write(UC_ARM_REG_LR, OTHER_PC)
                u.emu_start(RECEIVE, 0, count=50000)
                assert bytes(u.mem_read(DRAIN, 6)).hex() == "010000002b19"
            assert u.reg_read(UC_ARM_REG_PC) == NATIVE_STOP and self.read(SCHED) == TASK
            assert not self.members(CURRENT) and self.read(QUEUE + 0x10) == 0
            value = u.reg_read(UC_ARM_REG_R0)
            assert value == int(scenario == "space-available")
            assert self.read(QUEUE + 0x38) == 10
            if value:
                assert bytes(u.mem_read(data, 6)).hex() == "010000002713"
                assert bytes(u.mem_read(data + 68, 612)) == before[68:]
            else:
                assert bytes(u.mem_read(data, 680)) == before
        finally:
            self.transport_active = self.dispatch_svc = False
        return dict(scenario=scenario, native_producer=hex(NATIVE_PRODUCER), return_value=value,
                    elapsed=self.read(SCHED + 0xC) - 100, marks=self.watched[:])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    results, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert len(raw) == item["size_bytes"] and hashlib.sha256(raw).hexdigest() == item["sha256"]
        replay = FullQueueReplay(raw)
        replay.install_vectors(False)
        cases = [replay.run_full(scenario) for scenario in ("zero-wait", "timeout", "space-available")]
        coverage = {hex(pc): value for pc, value in sorted(replay.coverage.items())}
        results.append((static_index(raw), cases, coverage))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=len(cases)))
    assert len(results) == 2 and results[0] == results[1]
    report = dict(schema="ys4470.queue-interior-and-full-sends.v1", versions=versions,
                  static_index=results[0][0], cases=results[0][1], instruction_bytes=results[0][2],
                  limits=["Raw encoding matches are candidates, including when a surrounding region resembles data.",
                          "Scan covers aligned ARM immediate B/BL, Thumb immediate BLX, immediate ADR and literal loads in both modes, and four byte phases for exact pointer words.",
                          "Field signatures only look for ARM immediate accesses using one base register within 512 bytes of a count store. They do not prove register provenance or enumerate all queue primitives.",
                          "Multi-instruction synthesized pointers, indirect branch flow and whole-program reachability remain open.",
                          "Queue allocation, initial task frames and IRQ inputs are controlled; original queue, timeout, scheduler and IRQ code execute."])
    output = json.dumps(report, indent=2) + "\n"
    if args.out is None:
        print(output, end="")
    else:
        args.out.write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
