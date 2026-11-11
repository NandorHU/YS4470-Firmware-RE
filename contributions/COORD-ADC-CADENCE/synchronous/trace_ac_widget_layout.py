"""Execute native regular AC widget layout with an original ASCII font."""

import argparse
import hashlib
import json
import struct
from itertools import product
from pathlib import Path

from trace_ac_checkbox_renderer import BASE, INIT_BASE, TABLE_SIZE, UNIT_TABLE, restore_globals
from trace_ac_widget_text import INVALIDATE, LAYOUT, WidgetReplay
from trace_gui_field_provenance import BitmapReplay
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP

FONT, GLYPHS, CACHE = BitmapReplay.FONT, BitmapReplay.GLYPHS, BitmapReplay.CACHE
CHARACTER_ROUTINES, ROUTINE_SIZE = 0x805ABDC0, 28
MEASURE, STYLE = 0x80041078, 0x80036F88
AFTER_RECTANGLE, AFTER_MEASURE = 0x8003172C, 0x800317E8
OUTER_RECT = (10, 20, 89, 69)
WINDOWS = (
    (LAYOUT, 0x8003181C), (0x80031E88, 0x80031E98), (0x80035B44, 0x80035C08),
    (0x80021874, 0x800218A8), (0x8003924C, 0x80039294),
    (0x80041078, 0x80041690), (0x8000B300, 0x8000B800),
    (0x8001D5B0, 0x8001D79C), (0x8002C8A4, 0x8002CBCC),
)


class LayoutReplay(WidgetReplay):
    def __init__(self, raw, initialized, spacing, padding):
        table_offset = UNIT_TABLE - INIT_BASE
        table = initialized[table_offset:table_offset + TABLE_SIZE]
        assert len(table) == TABLE_SIZE
        super().__init__(raw, table)
        decoder_offset = CHARACTER_ROUTINES - INIT_BASE
        self.characters = initialized[decoder_offset:decoder_offset + ROUTINE_SIZE]
        assert len(self.characters) == ROUTINE_SIZE
        self.letter, self.line = spacing
        self.padding = padding
        self.line_height, = struct.unpack_from("<H", raw, FONT + 8 - BASE)
        assert self.line_height == 37
        assert raw[BitmapReplay.DESCRIPTOR + 0xC - BASE:BitmapReplay.DESCRIPTOR + 0x10 - BASE] == bytes(4)
        self.advances = [(struct.unpack_from("<I", raw, GLYPHS + 8 * index - BASE)[0] >> 20) + 8
                         for index in range(1, 96)]
        self.layout_call = None
        self.layout_lines = []
        self.layout_rows, self.style_reads = [], []
        self.layout_instructions = {}

    def prepare_refresh_state(self, initial, warmup):
        setup = super().prepare_refresh_state(initial, warmup)
        self.u.mem_write(CHARACTER_ROUTINES, self.characters)
        for cache in self.font_caches():
            self.u.mem_write(cache, bytes(8))
        return setup

    def layout(self, u, widget, text, return_pc):
        assert self.layout_call is None
        u.mem_write(widget + 0x14, struct.pack("<4h", *self.outer_rect(widget)))
        self.layout_lines.clear()
        self.layout_call = (widget, text, return_pc)
        self.layout_instructions[LAYOUT] = bytes(u.mem_read(LAYOUT, 4)).hex()

    def outer_rect(self, widget):
        return OUTER_RECT

    def styles_for(self, widget):
        return {0x32: 1, 0x12: self.padding, 0x13: self.padding, 0x10: 2, 0x11: 3,
                0x57: FONT, 0x59: self.line, 0x58: self.letter, 1: 80, 4: 50}

    def font_caches(self):
        return (CACHE,)

    def content_rect(self, widget):
        left, top, right, bottom = self.outer_rect(widget)
        styles = self.styles_for(widget)
        border = styles[0x32]
        return (left + border + styles[0x12], top + border + styles[0x10],
                right - border - styles[0x13], bottom - border - styles[0x11])

    def check_dimensions(self, widget, text, width, height):
        advances = [self.advances[ord(char) - 32] >> 4 for char in text]
        positive = [value for value in advances if value > 0]
        assert (width, height) == (sum(positive) + max(0, len(positive) - 1) * self.letter, self.line_height)

    def code(self, u, pc, size, data):
        if self.layout_call is None:
            return super().code(u, pc, size, data)
        widget, text, return_pc = self.layout_call
        if pc == return_pc:
            self.layout_call = None
            assert self.read(widget + 0x30) == 0xFFFFFFFF
            return super().code(u, pc, size, data)
        r0, r1, r2, r3, sp, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR,
        ))
        if pc == STYLE:
            assert r0 == widget and r1 == 0
            self.style_reads.append(r2)
            self.return_leaf(u, lr, self.styles_for(widget)[r2])
            return
        if pc == INVALIDATE:
            assert (r0, lr) == (widget, 0x80031E90)
            self.return_leaf(u, lr, 0)
            return
        if pc == AFTER_RECTANGLE:
            bounds = struct.unpack("<4h", u.mem_read(sp + 0x48, 8))
            assert bounds == self.content_rect(widget)
        if pc == MEASURE:
            styles = self.styles_for(widget)
            left, _, right, _ = self.content_rect(widget)
            assert (self.string(r1), r2, r3, lr) == (text, styles[0x57], styles[0x58], AFTER_MEASURE)
            flags = (self.text_flags & 0x30) >> 4
            assert struct.unpack("<3I", u.mem_read(sp, 12)) == (styles[0x59], right - left + 1, flags)
        if pc == 0x80041140:
            self.layout_lines.append(self.string(r0)[:r1])
        if pc == AFTER_MEASURE:
            width, height = struct.unpack("<2h", u.mem_read(sp + 0x44, 4))
            self.check_dimensions(widget, text, width, height)
            self.layout_rows.append([hex(widget), text, width, height])
        assert size == 4 and any(lo <= pc < hi for lo, hi in WINDOWS), hex(pc)
        self.layout_instructions[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        if self.layout_call is not None:
            if address == self.layout_call[0] + 0x30:
                assert (u.reg_read(UC_ARM_REG_PC), size, value) == (0x80031724, 4, 0xFFFFFFFF)
                return
            if any(cache <= address < cache + 8 for cache in self.font_caches()):
                assert size == 4
                return
        super().write(u, access, address, size, value, data)

    def check(self, initial):
        widgets = self.run(initial, "borrowed")
        assert self.layout_call is None and len(self.layout_rows) == 10
        expected_style = [0x32, 0x12, 0x13, 0x10, 0x11, 0x57, 0x59, 0x58, 1, 1, 4]
        assert self.style_reads == expected_style * len(self.layout_rows)
        return dict(configuration=widgets["configuration"], letter_spacing=self.letter, line_spacing=self.line,
                    horizontal_padding=self.padding, layouts=self.layout_rows)


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
        initialized = restore_globals(raw)
        cases, coverage = [], {}
        for initial, spacing, padding in product((0, 1), ((0, 0), (2, 5)), (0, 3)):
            replay = LayoutReplay(raw, initialized, spacing, padding)
            cases.append(replay.check(initial))
            coverage.update(replay.layout_instructions)
        observations.append((cases, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.ac-widget-layout.v1", images=images, cases=cases, original_font=hex(FONT),
                  font_glyph_records=hex(GLYPHS), character_dispatch=hex(CHARACTER_ROUTINES),
                  layout_columns=["widget", "text", "width", "height"],
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["Original label layout, content rectangle, ASCII decoder, glyph descriptor and text sizing execute.",
                          "The font is original, with a seeded style mapping and fixed-size labels. Allocator and invalidation leaves are modeled.",
                          "This path sizes a single line. Text wrapping, animation, the actual AC style binding and LCD pixels remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {len(cases)} original widget layout schedules per image, {2*len(cases)} total")


if __name__ == "__main__":
    main()
