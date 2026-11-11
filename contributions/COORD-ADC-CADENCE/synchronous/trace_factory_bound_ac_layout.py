"""Use the native AC label bindings to exercise the original sizing and wrap path."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from trace_ac_label_bindings import AcLabelBindings
from trace_ac_checkbox_renderer import BASE, restore_globals
from trace_ac_widget_layout import LayoutReplay
from trace_ac_widget_text import WIDGETS


class BoundLayoutReplay(LayoutReplay):
    invoke_instruction_limit = 100_000
    text_flags = 0
    samples = ((-12345, 0), (550, 1), (8388606, 6), (0x7FFFFF, 6))

    def __init__(self, raw, initialized, bindings):
        super().__init__(raw, initialized, (0, 0), 0)
        self.bindings = dict(zip(WIDGETS, bindings))
        self.fonts, self.styles, self.line_traces = {}, {}, []
        for widget, binding in self.bindings.items():
            font = binding["font"]
            desc, = struct.unpack_from("<I", raw, font + 0x10 - BASE)
            height, = struct.unpack_from("<H", raw, font + 8 - BASE)
            _, glyphs, cmap, kerning, _, cache = struct.unpack_from("<6I", raw, desc - BASE)
            assert kerning == 0 and struct.unpack_from("<IHH", raw, cmap - BASE) == (32, 95, 1)
            advances = tuple(((struct.unpack_from("<I", raw, glyphs + 8 * index - BASE)[0] >> 20) + 8) >> 4
                             for index in range(1, 96))
            self.fonts[widget] = (height, advances, cache)
            self.styles[widget] = {int(key, 16): value for key, value in binding["styles"].items()}
            assert binding["label_flags"] == self.text_flags

    def font_caches(self):
        return tuple(font[2] for font in self.fonts.values())

    def styles_for(self, widget):
        return self.styles[widget]

    def outer_rect(self, widget):
        binding = self.bindings[widget]
        x, y = binding["position"]
        width, height = binding["size"]
        return x, y, x + width - 1, y + height - 1

    def check_dimensions(self, widget, text, width, height):
        line_height, advances, _ = self.fonts[widget]
        lines = self.layout_lines or [""]
        assert "".join(lines) == text
        widths = [sum(advances[ord(char) - 32] for char in line) for line in lines]
        left, _, right, _ = self.content_rect(widget)
        assert all(value <= right - left + 1 for value in widths)
        assert (width, height) == (max(widths), line_height * len(lines))
        self.line_traces.append(dict(widget=hex(widget), text=text, lines=list(lines),
                                     line_widths=widths, dimensions=[width, height]))

    def check_bound(self, initial):
        record = self.run(initial, "borrowed")
        assert self.layout_call is None and len(self.line_traces) == 2 * (len(self.samples) + 2)
        assert any(len(row["lines"]) > 1 for row in self.line_traces if row["text"].endswith("8388606.000"))
        return dict(configuration=record["configuration"], layouts=self.line_traces)


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
        bindings = AcLabelBindings(raw).run()["labels"]
        initialized = restore_globals(raw)
        cases, coverage = [], {}
        for initial in (0, 1):
            replay = BoundLayoutReplay(raw, initialized, bindings)
            cases.append(replay.check_bound(initial))
            coverage.update(replay.layout_instructions)
        observations.append((bindings, cases, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    bindings, cases, coverage = observations[0]
    report = dict(schema="ys4470.factory-bound-ac-layout.v1", images=images, bindings=bindings, cases=cases,
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["The label constructor's actual style arguments supply the per-widget style model.",
                          "Original layout, text sizing, line splitting and both assigned fonts execute.",
                          "The parent geometry, style storage, allocator and invalidation are bounded fixtures. No rasterizer or panel is driven."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 2 factory-bound AC layout schedules per image, 4 total")


if __name__ == "__main__":
    main()
