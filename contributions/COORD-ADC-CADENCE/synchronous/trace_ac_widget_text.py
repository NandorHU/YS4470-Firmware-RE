"""Follow regular AC text into original widget storage on each refresh."""

import argparse
import hashlib
import json
from itertools import product
from pathlib import Path

from trace_ac_checkbox_renderer import BASE, INIT_BASE, TABLE_SIZE, UNIT_TABLE, WIDGET_TEXT, restore_globals
from trace_ac_native_formatter import NativeNormal
from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1

TEXT_POINTER, FLAGS, STATIC_TEXT = 0x24, 0x48, 8
ALLOC, FREE, INVALIDATE, LAYOUT = 0x80032800, 0x80032A80, 0x80037F3C, 0x800316FC
GETS = (0x80003400, 0x8000340C)
WIDGETS = (0x11000000, 0x11000100)
POOL = {widget: widget + 0x200 for widget in WIDGETS}
ORIGINAL = {widget: widget + 0x400 for widget in WIDGETS}
BUFFER_SIZE = 64
WINDOWS = ((WIDGET_TEXT, 0x800320E8), (0x80000934, 0x800009C4))
SAMPLES = ((-12345, 0), (550, 1), (0x7FFFFF, 6))


class WidgetReplay(NativeNormal):
    primary_widget, unit_widget = WIDGETS
    text_flags = 0x20
    samples = SAMPLES

    def __init__(self, raw, table):
        super().__init__(raw, table)
        self.u.mem_map(WIDGETS[0], 0x1000)
        self.widget_call = None
        self.widget_actions = []
        self.widget_instructions = {}
        self.allocated = set()

    def code(self, u, pc, size, data):
        if not self.in_view or self.widget_call is None and pc != WIDGET_TEXT:
            return super().code(u, pc, size, data)
        r0, r1, lr = (u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_LR))
        if pc == WIDGET_TEXT:
            assert self.widget_call is None and r0 in WIDGETS and lr == GETS[WIDGETS.index(r0)]
            text = self.string(r1)
            self.widget_call = (r0, lr, text)
            self.widget_actions.append(["set", hex(r0), text])
            self.emitted.append([hex(r0), text])
        widget, return_pc, text = self.widget_call
        if pc == return_pc:
            self.widget_call = None
            return super().code(u, pc, size, data)
        if pc == INVALIDATE:
            assert (r0, lr) == (widget, 0x80032048)
            self.widget_actions.append(["invalidate", hex(widget)])
            self.return_leaf(u, lr, 0)
            return
        if pc == FREE:
            assert (r0, lr) == (POOL[widget], 0x800320A0) and r0 in self.allocated
            self.allocated.remove(r0)
            self.widget_actions.append(["free", hex(r0)])
            self.return_leaf(u, lr, 0)
            return
        if pc == ALLOC:
            assert (r0, lr) == (len(text) + 1, 0x800320B8) and 0 < r0 <= BUFFER_SIZE
            buffer = POOL[widget]
            assert buffer not in self.allocated
            self.allocated.add(buffer)
            u.mem_write(buffer, b"\xA5" * BUFFER_SIZE)
            self.widget_actions.append(["allocate", hex(buffer), r0])
            self.return_leaf(u, lr, buffer)
            return
        if pc == LAYOUT:
            assert (r0, lr) == (widget, return_pc)
            self.check_layout_input(u, widget, text)
            return self.layout(u, widget, text, return_pc)
        assert size in (2, 4) and any(lo <= pc < hi for lo, hi in WINDOWS), hex(pc)
        self.widget_instructions[pc] = bytes(u.mem_read(pc, size)).hex()

    def check_layout_input(self, u, widget, text):
        assert self.read(widget + TEXT_POINTER) == POOL[widget]
        buffer = bytes(u.mem_read(POOL[widget], BUFFER_SIZE))
        assert buffer == (text.encode("ascii") + b"\0").ljust(BUFFER_SIZE, b"\xA5")
        assert not u.mem_read(widget + FLAGS, 1)[0] & STATIC_TEXT
        self.widget_actions.append(["layout", hex(widget), text])

    def layout(self, u, widget, text, return_pc):
        self.return_leaf(u, return_pc, 0)

    def write(self, u, access, address, size, value, data):
        if self.widget_call is not None:
            widget, _, text = self.widget_call
            if address in (widget + TEXT_POINTER, widget + FLAGS):
                pc = u.reg_read(UC_ARM_REG_PC)
                if address == widget + TEXT_POINTER:
                    assert size == 4 and (pc, value) in ((0x800320A4, 0), (0x800320BC, POOL[widget]))
                else:
                    assert (pc, size, value) == (0x800320D4, 1, self.text_flags)
                return
            if POOL[widget] <= address and address + size <= POOL[widget] + len(text) + 1:
                return
        super().write(u, access, address, size, value, data)

    def render_once(self, previous_ownership):
        start = len(self.widget_actions)
        row = self.timer_refresh(2)
        assert self.widget_call is None
        record, = row["native_render_record"]
        expected = []
        for widget, text in zip(WIDGETS, (record["text"], record["unit"])):
            expected.extend((["set", hex(widget), text], ["invalidate", hex(widget)]))
            if previous_ownership == "owned":
                expected.append(["free", hex(POOL[widget])])
            expected.extend((["allocate", hex(POOL[widget]), len(text) + 1], ["layout", hex(widget), text]))
            assert self.read(widget + TEXT_POINTER) == POOL[widget]
            assert self.string(POOL[widget]) == text
            assert self.u.mem_read(widget + FLAGS, 1) == bytes((self.text_flags,))
            assert bytes(self.u.mem_read(ORIGINAL[widget], 7)) == b"borrow\0"
        assert self.widget_actions[start:] == expected
        return dict(widget_value=record["text"], widget_unit=record["unit"], actions=expected)

    def run(self, initial, ownership):
        self.prepare_refresh_state(initial, 2)
        for widget in WIDGETS:
            self.u.mem_write(widget, bytes(0x80))
            self.u.mem_write(ORIGINAL[widget], b"borrow\0")
            self.u.mem_write(widget + FLAGS, bytes((self.text_flags | (STATIC_TEXT if ownership == "borrowed" else 0),)))
            if ownership == "borrowed":
                self.put(widget + TEXT_POINTER, ORIGINAL[widget])
            elif ownership == "owned":
                self.put(widget + TEXT_POINTER, POOL[widget])
                self.u.mem_write(POOL[widget], b"owned\0")
                self.allocated.add(POOL[widget])
        first = self.render_once(ownership)
        assert not self.measurement(100, 0, True)["published"]
        self.render_once("owned")
        observed = []
        for sample, selector in self.samples:
            assert self.measurement(sample & 0xFFFFFF, selector, True)["published"]
            observed.append(dict(sample=sample, selector=selector, **self.render_once("owned")))
        return dict(configuration=9 if initial else 10, original_widget_ownership=ownership,
                    initial_actions=first["actions"], samples=observed)


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
        offset = UNIT_TABLE - INIT_BASE
        table = restore_globals(raw)[offset:offset + TABLE_SIZE]
        assert len(table) == TABLE_SIZE
        cases, coverage = [], {}
        for initial, ownership in product((0, 1), ("empty", "borrowed", "owned")):
            replay = WidgetReplay(raw, table)
            cases.append(replay.run(initial, ownership))
            coverage.update(replay.widget_instructions)
        observations.append((cases, coverage))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.ac-widget-text.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): encoded for pc, encoded in sorted(coverage.items())},
                  limits=["The original text setter, strlen, string copy and ownership stores execute.",
                          "Widget objects are seeded. Allocator, free, invalidation and layout calls are modeled.",
                          "The trace establishes native RAM text and pointer state. The LCD controller and pixel output are outside the replay."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS {len(cases)} original AC widget cases per image, {2*len(cases)} total")


if __name__ == "__main__":
    main()
