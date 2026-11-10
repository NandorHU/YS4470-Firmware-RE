"""Trace the original GUI field at 0x80046548 with guarded GUI fixtures."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from trace_gauge_scheduled_service import CTRL, QUEUE, GaugeReplay
from trace_scheduler_delay_wake import BASE, RET, STACK, DelayReplay
from unicorn import UC_HOOK_MEM_READ
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_SP,
    UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R4,
)

ENTRY = 0x80057948
STOP = 0x800466C4
PANEL = 0x10017800
SCREEN = 0x10017900
PARENT = 0x10017000
LABEL_CLASS = 0x80068EE0
BASE_CLASS = 0x80063B0C
LABEL_CTOR = 0x800309F0
TEXT_SET = 0x80032038
ALLOCATE = 0x80032800
STORES = {
    0x80045F54: 0x18, 0x800460CC: 0x20, 0x80046240: 0x28,
    0x800463D8: 0x30, 0x80046548: 0x38, 0x800466BC: 0x40,
}
WINDOWS = (
    (ENTRY, 0x800579BC), (0x80045EA8, 0x800462E8), (0x8004630C, STOP),
    (LABEL_CTOR, 0x80030AC0), (0x80030AD0, 0x80030AF0),
    (0x80034760, 0x800348DC), (0x800348DC, 0x800349D0),
    (TEXT_SET, 0x800320E8), (0x80032E14, 0x80032EA4),
)
THUMB_WINDOWS = ((0x80000934, 0x8000097C), (0x80000980, 0x800009BE))
# Unrelated UI properties and display/layout services. The object creation,
# child list, descriptor dispatch, text setter and string primitives execute.
UI_LEAVES = {
    0x80025C94, 0x80025D44, 0x800338DC, 0x800339BC,
    0x80024C08, 0x80031F94, 0x80033B7C,
    0x8003A160, 0x8003A288, 0x8003A2C8, 0x8003A718, 0x8003A738,
    0x8003A748, 0x8003A758, 0x8003A768, 0x8003A778, 0x8003A788,
    0x8003A7A8, 0x8003A7B8, 0x8003A7C8, 0x8003A8A8,
    0x8003AA08, 0x8003AA18, 0x8003AA28, 0x8003AA38, 0x8003AA58,
    0x8003AA88, 0x8003AAC8,
    0x80038130, 0x80035418, 0x800405D8, 0x800392D0, 0x8003924C,
    0x80034A50, 0x800206F4, 0x800316FC, 0x80037F3C,
}


def in_span(address, size, start, end):
    return start <= address and address + size <= end


class FieldReplay(GaugeReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.gui = False

    def emulate_leaf(self, u, pc, lr, r0):
        if pc == ALLOCATE:
            assert r0 in (1, 4, 5, 0x4C) and self.heap + r0 < self.heap_end, (hex(lr), r0)
            address = self.heap
            self.heap += (r0 + 7) & ~7
            self.allocations[address] = r0
            self.allocation_log.append([hex(lr), hex(address), r0])
            return address
        if pc == 0x80032A80:
            assert self.allocations[r0] in (1, 5)
            self.frees.append(r0)
            return r0
        if pc == 0x800305A8:
            assert lr == 0x80057984
            return SCREEN
        if pc == 0x80034C10:
            assert lr == 0x80045EB8 and r0 == 0
            return PANEL
        if pc == 0x80021F3C:
            assert r0 == PANEL
            idx = len(self.parents)
            assert idx < len(STORES)
            parent = PARENT + idx * 0x80
            self.parents.append(parent)
            return parent
        if pc == 0x80034B18:
            assert self.read(r0) == BASE_CLASS and self.allocations[r0] == 0x4C
            return r0
        if pc in (0x8002D9AC, 0x80035EB4):
            return 0
        assert pc in UI_LEAVES, (hex(pc), hex(lr))
        return r0

    def code(self, u, pc, size, data):
        if not self.gui:
            return super().code(u, pc, size, data)
        if pc == STOP:
            u.emu_stop()
            return
        r0 = u.reg_read(UC_ARM_REG_R0)
        lr = u.reg_read(UC_ARM_REG_LR)
        if any(a <= pc < b for a, b in WINDOWS):
            assert size == 4
        elif any(a <= pc < b for a, b in THUMB_WINDOWS):
            assert size == 2 and u.reg_read(UC_ARM_REG_CPSR) & 0x20
        else:
            u.reg_write(UC_ARM_REG_R0, self.emulate_leaf(u, pc, lr, r0))
            u.reg_write(UC_ARM_REG_PC, lr)
            self.leaves[pc] = self.leaves.get(pc, 0) + 1
            return
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
        if pc == 0x80045EA8:
            assert r0 == self.context and lr == 0x800579BC
        elif pc == 0x80034928:
            obj = u.reg_read(UC_ARM_REG_R1)
            assert r0 == LABEL_CLASS and self.read(obj) == LABEL_CLASS
            assert u.reg_read(UC_ARM_REG_R2) == LABEL_CTOR
            assert self.allocations[obj] == 0x4C
            self.labels.append(obj)
        elif pc == 0x80030AD0:
            assert r0 == self.parents[-1]
        elif pc == TEXT_SET:
            assert r0 == self.labels[-1]
            address = u.reg_read(UC_ARM_REG_R1)
            value = bytes(u.mem_read(address, 32)).split(b"\0", 1)[0]
            self.text_calls.append([hex(lr), hex(r0), hex(address), value.decode("ascii")])

    def write(self, u, access, address, size, value, data):
        if not self.gui:
            return super().write(u, access, address, size, value, data)
        pc = u.reg_read(UC_ARM_REG_PC)
        if pc in STORES:
            assert address == self.context + STORES[pc] and size == 4 and value == self.labels[-1]
            self.stores.append([hex(pc), hex(address), hex(value)])
        assert (
            in_span(address, size, self.context, self.context + 0x4C8)
            or in_span(address, size, PARENT, PARENT + 6 * 0x80)
            or in_span(address, size, STACK - 0x300, STACK)
            or any(in_span(address, size, a, a + length) for a, length in self.allocations.items())
        ), (hex(pc), hex(address), size)

    def interrupt(self, u, number, data):
        assert not self.gui, number
        super().interrupt(u, number, data)

    def run_fields(self, raw, context, heap, occupied):
        self.context = context
        self.heap, self.heap_end = heap, heap + 0x800
        self.allocations, self.leaves = {}, {}
        self.allocation_log, self.parents, self.labels = [], [], []
        self.stores, self.text_calls, self.frees = [], [], []
        self.seed("idle")
        u = self.u
        u.mem_write(CTRL, bytes(16))
        u.mem_write(QUEUE, b"\xA5" * 760)
        self.invoke_transport(0x800029DC)
        for i in range(occupied):
            self.enqueue(3, i)
        assert self.read(CTRL + 4) == QUEUE and self.read(QUEUE + 0x38) == occupied
        watched = ((CTRL, 16), (QUEUE, 760))
        before = [bytes(u.mem_read(a, n)) for a, n in watched]
        u.mem_write(context - 4, b"\xA5" * 4 + bytes(0x4C8) + b"\x5A" * 4)
        u.mem_write(heap, b"\xA5" * 0x800)
        u.mem_write(PARENT, bytes(6 * 0x80))
        for idx in range(6):
            parent = PARENT + idx * 0x80
            self.put(parent + 8, parent + 0x50)
        u.reg_write(UC_ARM_REG_CPSR, 0x13)
        u.reg_write(UC_ARM_REG_SP, STACK)
        u.reg_write(UC_ARM_REG_LR, RET)
        u.reg_write(UC_ARM_REG_R0, context)
        self.coverage.clear()
        self.gui = True
        try:
            u.emu_start(ENTRY, 0, count=30000)
        finally:
            self.gui = False
        assert u.reg_read(UC_ARM_REG_PC) == STOP and u.reg_read(UC_ARM_REG_R4) == context
        assert u.reg_read(UC_ARM_REG_SP) == STACK - 32
        assert self.read(context - 4) == 0xA5A5A5A5 and self.read(context + 0x4C8) == 0x5A5A5A5A
        assert self.read(context + 0x4C4) == SCREEN and self.read(context + 0xC) == PANEL
        assert [int(pc, 16) for pc, _, _ in self.stores] == list(STORES)
        assert len(self.labels) == len(set(self.labels)) == len(self.parents) == 6
        for parent, label, offset in zip(self.parents, self.labels, STORES.values()):
            child_list = self.read(parent + 0x50)
            assert self.read(label + 4) == parent and self.read(label) == LABEL_CLASS
            assert self.read(parent + 0x54) == 1 and self.read(child_list) == label
            assert self.read(context + offset) == label
        assert self.read(context + 0x34) == self.parents[-2]
        assert self.read(context + 0x3C) == self.parents[-1]
        assert self.text_calls[-4:] == [
            ["0x8003492c", hex(self.labels[-2]), "0x80030ac8", "Text"],
            ["0x80046550", hex(self.labels[-2]), "0x800462f0", ""],
            ["0x8003492c", hex(self.labels[-1]), "0x80030ac8", "Text"],
            ["0x800466c4", hex(self.labels[-1]), "0x800462f0", ""],
        ]
        for label in self.labels[-2:]:
            text_address = self.read(label + 0x24)
            assert self.allocations[text_address] == 1 and bytes(u.mem_read(text_address, 1)) == b"\0"
        after = [bytes(u.mem_read(a, n)) for a, n in watched]
        assert after == before
        descriptor = raw[LABEL_CLASS - BASE:LABEL_CLASS - BASE + 0x1C]
        assert struct.unpack_from("<II", descriptor) == (BASE_CLASS, LABEL_CTOR)
        return dict(context=hex(context), queue_records=occupied, queue_and_handle_unchanged=True,
                    label_descriptor=dict(address=hex(LABEL_CLASS), bytes=descriptor.hex()),
                    stores=self.stores, parent_at_0x3c=hex(self.parents[-1]), text_calls=self.text_calls,
                    allocations=self.allocation_log, freed_text_buffers=[hex(a) for a in self.frees],
                    modeled_leaves={hex(pc): n for pc, n in sorted(self.leaves.items())},
                    watched_sha256={hex(a): hashlib.sha256(data).hexdigest()
                                    for (a, _), data in zip(watched, after)})


class BitmapReplay(DelayReplay):
    FONT = 0x800A56D4
    DESCRIPTOR = 0x800A56BC
    BITMAP = 0x8009B5C4
    GLYPHS = 0x800A513C
    CACHE = 0x805ABE7C
    GET_BITMAP = 0x8002C844
    CANDIDATE = 0x8009EF10

    def __init__(self, raw):
        super().__init__(raw)
        self.u.hook_add(UC_HOOK_MEM_READ, self.on_read)

    def code(self, u, pc, size, data):
        if pc == RET:
            u.emu_stop()
            return
        assert size == 4 and (0x8001D5B0 <= pc < 0x8001D79C or self.GET_BITMAP <= pc <= 0x8002C88C)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
        self.steps.append(hex(pc))

    def on_read(self, u, access, address, size, value, data):
        if 0x800A513C <= address <= 0x800A56E4 or self.CACHE <= address < self.CACHE + 8:
            self.reads.append([hex(address), size])

    def write(self, u, access, address, size, value, data):
        if address in (self.CACHE, self.CACHE + 4):
            assert size == 4
            self.writes.append([hex(address), value])
            return
        super().write(u, access, address, size, value, data)

    def check_bitmap(self, raw):
        assert self.read(self.FONT + 4) == self.GET_BITMAP
        assert self.read(self.FONT + 0x10) == self.DESCRIPTOR
        assert tuple(self.read(self.DESCRIPTOR + n) for n in (0, 4, 8, 0x14)) == (
            self.BITMAP, self.GLYPHS, 0x800A5694, self.CACHE,
        )
        self.put(self.CACHE, 0)
        self.put(self.CACHE + 4, 0)
        cases = []
        for point, index, bitmap, warm in (
            (0x7C, 93, 0x8009EE84, False), (0x7D, 94, 0x8009EEC2, False),
            (0x7D, 94, 0x8009EEC2, True), (0x7E, 95, 0x8009EF6D, False),
        ):
            self.steps, self.reads, self.writes = [], [], []
            assert self.invoke(self.GET_BITMAP, self.FONT, point) == bitmap
            assert self.read(self.CACHE) == point and self.read(self.CACHE + 4) == index
            assert self.writes == ([] if warm else [[hex(self.CACHE), point], [hex(self.CACHE + 4), index]])
            assert ([hex(self.CACHE + 4), 4] in self.reads) == warm
            entry = self.GLYPHS + index * 8
            assert [hex(entry), 4] in self.reads
            cases.append(dict(codepoint=hex(point), index=index, bitmap=hex(bitmap), cache_hit=warm,
                              descriptor_reads=self.reads, cache_writes=self.writes, executed=self.steps))
        glyph = self.GLYPHS + 94 * 8
        words = raw[glyph - BASE:glyph - BASE + 8]
        start = self.BITMAP + (self.read(glyph) & 0xFFFFF)
        limit = self.BITMAP + (self.read(glyph + 8) & 0xFFFFF)
        width, height = words[4:6]
        assert (width, height) == (11, 31) and (width * height + 1) // 2 == limit - start
        assert start <= self.CANDIDATE <= limit - 4
        candidate = raw[self.CANDIDATE - BASE:self.CANDIDATE - BASE + 4]
        assert candidate.hex() == "000bffda"
        return dict(
            font_descriptor=hex(self.FONT), format_descriptor=hex(self.DESCRIPTOR),
            glyph_record=hex(glyph), glyph_record_bytes=words.hex(), glyph_dimensions=[width, height],
            span=[hex(start), hex(limit)], candidate=hex(self.CANDIDATE),
            candidate_bytes=candidate.hex(), candidate_offset=self.CANDIDATE - start,
            glyph_payload_sha256=hashlib.sha256(raw[start - BASE:limit - BASE]).hexdigest(),
            cases=cases, executed_bytes={hex(pc): b for pc, b in sorted(self.coverage.items())},
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd()
    manifest = json.loads((root / "original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    versions, observations = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        replay = FieldReplay(raw)
        cases = [replay.run_fields(raw, 0x10011000, 0x10015000, 0)]
        instructions = replay.coverage.copy()
        cases.append(replay.run_fields(raw, 0x10011800, 0x10015800, 3))
        assert replay.coverage == instructions
        bitmap = BitmapReplay(raw).check_bitmap(raw)
        versions.append(dict(version=item["version"], input_sha256=digest, cases=len(cases),
                             glyph_lookup_cases=len(bitmap["cases"])))
        observations.append((cases, instructions, bitmap))
    assert len(versions) == 2 and observations[0] == observations[1]
    cases, instructions, bitmap = observations[0]
    report = dict(schema="ys4470.gui-field-queue-provenance.v1", versions=versions,
                  entry=hex(ENTRY), stop=hex(STOP), cases=cases, glyph_bitmap=bitmap,
                  executed_bytes={hex(pc): code for pc, code in sorted(instructions.items())},
                  limits=[
                      "Original caller and panel initializer run to the selected stop PC, before the full UI is initialized.",
                      "Object allocator, display roots, containers, base class and unrelated styling/layout leaves are fixtures. Label object, child list, indirect label callback, text setter and string operations execute original bytes.",
                      "Two relocated context and heap layouts distinguish GUI slots from an independently constructed empty or populated control queue.",
                      "The bitmap probe calls the original descriptor's lookup, verifies adjacent glyphs and the cache path, and bounds the resource interval. It does not render pixels or prove the absence of all executable aliases.",
                      "These probes do not establish whole-program queue-writer coverage or physical UI behavior.",
                  ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS four original GUI field and eight glyph lookup cases across V3.6 and V3.8")


if __name__ == "__main__":
    main()
