"""Follow original label draw events to glyph-position dispatch in an offline draw context."""

import argparse
import hashlib
import json
import struct
from itertools import groupby, product
from pathlib import Path

from trace_ac_label_bindings import AcLabelBindings
from trace_ac_checkbox_renderer import INIT_BASE, restore_globals
from trace_ac_widget_layout import CHARACTER_ROUTINES, ROUTINE_SIZE, WINDOWS as LAYOUT_WINDOWS
from trace_scheduler_delay_wake import BASE, RET, STACK, DelayReplay
from unicorn.arm_const import (
    UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP,
)

EVENT_HANDLER, EVENT_BASE, PAINT, DRAW = 0x80030B3C, 0x80035A1C, 0x800158C4, 0x800265BC
STYLE = 0x80036F88
CONTEXT_INIT, NATIVE_GLYPH, MASK = 0x80029CC8, 0x8002A0C4, 0x80014688
WIDGET, EVENT, CONTEXT, CLIP, TEXT = (0x11000000 + offset for offset in (0, 0x100, 0x200, 0x300, 0x400))
WINDOWS = (
    (EVENT_HANDLER, 0x80030BFC), (0x8002C688, 0x8002C6D0), (0x8002C748, 0x8002C750),
    (PAINT, 0x80015C30), (DRAW, 0x80026E58),
    (0x80037824, 0x8003795C), (0x80008FC4, 0x80009054), (0x8000AC90, 0x8000AD08),
    (0x800363B0, 0x800363D0), (0x800218A8, 0x800218DC), (0x80032E14, 0x80032EA4),
    (0x80024A10, 0x80024A3C), (0x8003AE20, 0x8003AE5C),
    (CONTEXT_INIT, 0x80029D60), (NATIVE_GLYPH, 0x8002A1E0), (0x8002C844, 0x8002CBCC),
    (0x80026FBC, 0x80027010), (0x80028380, 0x80028520), *LAYOUT_WINDOWS,
)
VIEWPORTS = {
    "full": (0, 0, 900, 550), "partial": (100, 130, 760, 300),
    "first-line-only": (0, 0, 900, 260), "outside": (0, 0, 10, 10),
}
LABEL_TEXTS = (("+0.000", "-12.345", ".OL", "+8388606.000"), ("V", ""))


class DrawReplay(DelayReplay):
    invoke_instruction_limit = 100_000

    def __init__(self, raw, initialized, binding):
        super().__init__(raw)
        self.u.mem_map(0x805AC000, 0x1000)
        self.u.mem_map(WIDGET, 0x1000)
        offset = CHARACTER_ROUTINES - INIT_BASE
        self.u.mem_write(CHARACTER_ROUTINES, initialized[offset:offset + ROUTINE_SIZE])
        self.raw, self.binding = raw, binding
        self.style = {int(key, 16): value for key, value in binding["styles"].items()}
        self.font = binding["font"]
        descriptor = self.read(self.font + 0x10)
        glyphs, self.cache = self.read(descriptor + 4), self.read(descriptor + 0x14)
        self.advances = {chr(code): ((self.read(glyphs + (code - 31) * 8) >> 20) + 8) >> 4
                         for code in range(32, 127)}
        self.height, self.baseline = struct.unpack_from("<2H", raw, self.font + 8 - BASE)
        self.bitmap_base, self.glyph_table = self.read(descriptor), glyphs
        self.initializing = False

    def return_leaf(self, u, lr, value):
        u.reg_write(UC_ARM_REG_R0, value)
        u.reg_write(UC_ARM_REG_PC, lr)

    def code(self, u, pc, size, data):
        if pc == RET:
            u.emu_stop()
            return
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc == EVENT_BASE:
            assert r1 == EVENT and lr == 0x80030B50
            self.return_leaf(u, lr, 1)
            return
        if pc == STYLE:
            assert r0 == WIDGET and r1 in (0, 0x40000)
            assert r2 in self.style or r2 in (0x5A, 0x61)
            self.return_leaf(u, lr, self.style.get(r2, 0))
            return
        if pc == NATIVE_GLYPH:
            assert r0 == CONTEXT and lr == 0x80026AFC
            assert self.read(r1) == self.font and chr(r3) in self.advances
            x, y = struct.unpack("<2h", u.mem_read(r2, 4))
            clip = struct.unpack("<4h", u.mem_read(self.read(CONTEXT + 8), 8))
            self.glyphs.append([chr(r3), x, y, list(clip)])
        if pc == MASK:
            assert r0 == CONTEXT and lr == 0x8002A1D8 and self.read(r1) == self.font and self.read(r3) == self.font
            char, x, y, _ = self.glyphs[-1]
            ink, pointer = self.ink(char, x, y)
            assert struct.unpack("<2h", u.mem_read(r2, 4)) == ink[:2]
            assert self.read(u.reg_read(UC_ARM_REG_SP)) == pointer
            assert struct.unpack("<2H", u.mem_read(r3 + 6, 4)) == ink[2:]
            self.masks.append([char, *ink, hex(pointer)])
            self.return_leaf(u, lr, 0)
            return
        if pc == DRAW:
            assert r0 == CONTEXT and self.read(r1) == self.font and r3 == TEXT
            assert u.mem_read(r1 + 0x1A, 3) == bytes((255, 0, self.style[0x5B]))
            self.draws.append(list(struct.unpack("<4h", u.mem_read(r2, 8))))
        assert size in (2, 4) and any(lo <= pc < hi for lo, hi in WINDOWS), (hex(pc), hex(lr))
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        if address in (self.cache, self.cache + 4):
            assert size == 4
            return
        if self.initializing and CONTEXT <= address and address + size <= CONTEXT + 0x58:
            return
        if address == CONTEXT + 8:
            assert size == 4 and u.reg_read(UC_ARM_REG_PC) in (0x80015AFC, 0x80015C24)
            return
        assert STACK - 0x500 <= address and address + size <= STACK, (hex(u.reg_read(UC_ARM_REG_PC)), hex(address))

    def initialize_context(self):
        self.initializing = True
        try:
            self.invoke(CONTEXT_INIT, 0, CONTEXT)
        finally:
            self.initializing = False
        assert self.read(CONTEXT + 0x20) == NATIVE_GLYPH

    def ink(self, char, x, y):
        index = ord(char) - 31
        word, width, height, dx, dy = struct.unpack_from("<IBBbb", self.raw, self.glyph_table + 8 * index - BASE)
        return (x + dx, y + self.height - self.baseline - height - dy, width, height), self.bitmap_base + (word & 0xFFFFF)

    def run(self, text, viewport):
        x, y = self.binding["position"]
        width, height = self.binding["size"]
        bounds = (x, y, x + width - 1, y + height - 1)
        content = (x + self.style[0x12], y + self.style[0x10], bounds[2] - self.style[0x13], bounds[3])
        self.glyphs, self.draws, self.masks = [], [], []
        u = self.u
        u.mem_write(WIDGET, bytes(0x80))
        u.mem_write(WIDGET + 0x14, struct.pack("<4h", *bounds))
        self.put(WIDGET + 0x24, TEXT)
        self.put(WIDGET + 0x30, 0xFFFFFFFF)
        self.put(WIDGET + 0x3C, 0xFFFF)
        self.put(WIDGET + 0x40, 0xFFFF)
        u.mem_write(WIDGET + 0x48, bytes((self.binding["label_flags"],)))
        self.put(EVENT, WIDGET)
        self.put(EVENT + 4, WIDGET)
        self.put(EVENT + 8, 0x15)
        self.put(EVENT + 0x10, CONTEXT)
        self.initialize_context()
        self.put(CONTEXT + 8, CLIP)
        u.mem_write(CLIP, struct.pack("<4h", *VIEWPORTS[viewport]))
        u.mem_write(TEXT, text.encode("ascii") + b"\0")
        self.invoke(EVENT_HANDLER, 0x80068EE0, EVENT)
        assert self.read(CONTEXT + 8) == CLIP and bytes(u.mem_read(TEXT, len(text) + 1)) == text.encode("ascii") + b"\0"
        clip = VIEWPORTS[viewport]
        intersects = content[0] <= clip[2] and clip[0] <= content[2] and content[1] <= clip[3] and clip[1] <= content[3]
        assert self.draws == ([list(content)] if intersects else []), (text, viewport, self.draws)
        lines = [text] if text else []
        if sum(self.advances[char] for char in text) > width:
            prefix, suffix = text.rsplit(".", 1)
            lines = [prefix + ".", suffix]
        expected = [(content[1] + index * self.height, line) for index, line in enumerate(lines)] if intersects else []
        expected = [(top, line) for top, line in expected if top <= clip[3] and top + self.height - 1 >= clip[1]]
        observed = [(top, list(glyphs)) for top, glyphs in groupby(self.glyphs, key=lambda glyph: glyph[2])]
        assert [(top, "".join(glyph[0] for glyph in glyphs)) for top, glyphs in observed] == expected, (
            text, viewport, expected, self.glyphs,
        )
        for _, glyphs in observed:
            measured = sum(self.advances[glyph[0]] for glyph in glyphs)
            alignment = self.style[0x5B]
            first = content[0] + ((width - measured) // 2 if alignment == 2 else width - measured)
            assert glyphs[0][1] == first
            assert all(glyph[3] == list(clip) for glyph in glyphs)
            for previous, current in zip(glyphs, glyphs[1:]):
                assert current[1] == previous[1] + self.advances[previous[0]]
        expected_masks = []
        for char, x, y, _ in self.glyphs:
            ink, pointer = self.ink(char, x, y)
            left, top, w, h = ink
            if left + w >= clip[0] and left <= clip[2] and top + h >= clip[1] and top <= clip[3]:
                expected_masks.append([char, *ink, hex(pointer)])
        assert self.masks == expected_masks, (text, viewport, self.masks, expected_masks)
        return dict(label_offset=self.binding["offset"], viewport=viewport, input_text=text,
                    draw_rectangle=self.draws, glyphs=self.glyphs, packed_alpha_calls=self.masks)


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
        bindings = AcLabelBindings(raw).run()["labels"]
        cases, coverage = [], {}
        for binding, texts in zip(bindings, LABEL_TEXTS):
            replay = DrawReplay(raw, initialized, binding)
            cases.extend(replay.run(text, viewport) for text, viewport in product(texts, VIEWPORTS))
            coverage.update(replay.coverage)
        observations.append((cases, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.factory-ac-draw.v1", images=images, cases=cases,
                  glyph_columns=["character", "x", "y", "clip_rectangle"],
                  packed_alpha_columns=["character", "ink_x", "ink_y", "width", "height", "bitmap_pointer"],
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["Original draw context initialization, label draw event, layout, glyph callback and ink clipping execute.",
                          "Style reads, base event acceptance and the packed-alpha composition boundary are modeled.",
                          "The trace verifies native glyph positions and packed-alpha arguments before composition. There is no physical LCD output or timing."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {len(cases)} original AC draw cases per image, {2*len(cases)} total")


if __name__ == "__main__":
    main()
