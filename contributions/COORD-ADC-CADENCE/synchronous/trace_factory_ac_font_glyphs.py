"""Check original glyph descriptors and packed alpha spans for both AC label fonts."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from trace_ac_label_bindings import AcLabelBindings
from trace_scheduler_delay_wake import BASE, RET, DelayReplay
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_R2, UC_ARM_REG_R3

METRICS, BITMAP = 0x8002C9C0, 0x8002C844
OUT = 0x10017500
CHARACTERS = "+-.0123456789OLV"
WINDOWS = ((0x8001D5B0, 0x8001D79C), (BITMAP, 0x8002C894), (METRICS, 0x8002CB9C))


class GlyphReplay(DelayReplay):
    def __init__(self, raw, font):
        super().__init__(raw)
        self.raw, self.font = raw, font
        assert self.read(font) == METRICS and self.read(font + 4) == BITMAP
        descriptor = self.read(font + 0x10)
        self.bitmap, self.glyphs, cmap, kerning, options, self.cache = struct.unpack_from("<6I", raw, descriptor - BASE)
        assert kerning == 0 and struct.unpack_from("<IHH", raw, cmap - BASE) == (32, 95, 1)
        assert (options >> 25) & 0xF == 4
        assert self.cache in (0x805AC090, 0x805ABE8C)
        if self.cache == 0x805AC090:
            self.u.mem_map(0x805AC000, 0x1000)
        self.cache_writes = []

    def code(self, u, pc, size, data):
        if pc == RET:
            u.emu_stop()
            return
        assert size == 4 and any(lo <= pc < hi for lo, hi in WINDOWS), hex(pc)
        self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()

    def write(self, u, access, address, size, value, data):
        if address in (self.cache, self.cache + 4):
            assert size == 4
            self.cache_writes.append([address - self.cache, value])
            return
        if OUT <= address and address + size <= OUT + 0x10:
            return
        super().write(u, access, address, size, value, data)

    def glyph(self, char):
        codepoint = ord(char)
        index = codepoint - 31
        entry, width, height, x_offset, y_offset = struct.unpack_from("<IBBbb", self.raw, self.glyphs + 8 * index - BASE)
        next_entry = self.read(self.glyphs + 8 * (index + 1))
        advance = ((entry >> 20) + 8) >> 4
        start = self.bitmap + (entry & 0xFFFFF)
        end = self.bitmap + (next_entry & 0xFFFFF)
        assert start < end and end - start == (width * height + 1) // 2

        self.put(self.cache, 0)
        self.put(self.cache + 4, 0)
        self.cache_writes.clear()
        self.u.mem_write(OUT, bytes(0x10))
        self.u.reg_write(UC_ARM_REG_R2, codepoint)
        self.u.reg_write(UC_ARM_REG_R3, 0)
        assert self.invoke(METRICS, self.font, OUT) == 1
        assert struct.unpack("<3H2h", self.u.mem_read(OUT + 4, 10)) == (advance, width, height, x_offset, y_offset)
        assert self.u.mem_read(OUT + 0xE, 1)[0] & 0xF == 4
        assert self.cache_writes == [[0, codepoint], [4, index]]
        self.cache_writes.clear()
        assert self.invoke(BITMAP, self.font, codepoint) == start
        assert self.cache_writes == []
        self.put(self.cache, 0)
        assert self.invoke(BITMAP, self.font, codepoint) == start
        assert self.cache_writes == [[0, codepoint], [4, index]]

        packed = self.raw[start - BASE:end - BASE]
        assert bytes(self.u.mem_read(start, end - start)) == packed
        pixels = [nibble for byte in packed for nibble in (byte >> 4, byte & 15)][:width * height]
        return dict(character=char, glyph_id=index, advance=advance, box=[width, height], offsets=[x_offset, y_offset],
                    bitmap_span=[hex(start), hex(end)], packed_alpha_sha256=hashlib.sha256(packed).hexdigest(),
                    nonzero_alpha_samples=sum(alpha != 0 for alpha in pixels))


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
        labels = AcLabelBindings(raw).run()["labels"]
        rows, coverage = [], {}
        for label in labels:
            replay = GlyphReplay(raw, label["font"])
            glyphs = [replay.glyph(char) for char in CHARACTERS]
            rows.append(dict(label_offset=hex(label["offset"]), font=hex(replay.font), cache=hex(replay.cache), glyphs=glyphs))
            coverage.update(replay.coverage)
        observations.append((rows, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    rows, coverage = observations[0]
    report = dict(schema="ys4470.factory-ac-font-glyphs.v1", images=images, fonts=rows,
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["Original descriptor and cold/warm bitmap lookup execute for each glyph.",
                          "Alpha spans are checked against the original file and represented by SHA-256.",
                          "No glyph compositing, LCD pixels, or physical display timing are exercised."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    count = sum(len(font["glyphs"]) for font in rows)
    print(f"PASS {count} factory AC font glyph cases per image, {2*count} total")


if __name__ == "__main__":
    main()
