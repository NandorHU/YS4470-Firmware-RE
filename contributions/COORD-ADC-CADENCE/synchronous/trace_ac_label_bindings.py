"""Execute the original construction and style bindings of the regular AC labels."""

import argparse
import hashlib
import json
from pathlib import Path

from trace_control_gui_events import EventReplay
from trace_gui_field_provenance import ALLOCATE, BASE, LABEL_CLASS, PARENT, STACK, FieldReplay
from unicorn.arm_const import (
    UC_ARM_REG_CPSR, UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2,
    UC_ARM_REG_R3, UC_ARM_REG_R4, UC_ARM_REG_R7, UC_ARM_REG_SP,
)

ENTRY, STOP = 0x80050C48, 0x80050EFC
CONTEXT, HEAP = 0x10011000, 0x11000000
FONT, STYLE_WRITE, STYLE_FIND = 0x57, 0x80039FA0, 0x80035E54
STORES = {0x80050C54: 0x2F4, 0x80050DB0: 0x2F8}
WINDOWS = (
    (ENTRY, STOP), (0x80031F94, 0x80032038),
    (0x8003A160, 0x8003A200), (0x8003A2C8, 0x8003A368),
    (0x8003A718, 0x8003A7F8), (0x8003A9C8, 0x8003AAC8),
)
EXPECTED = (
    dict(offset=0x2F4, text="+0.000", font=0x804B000C, position=[41, 118], size=[770, 148]),
    dict(offset=0x2F8, text="V", font=0x800D0BB4, position=[681, 273], size=[129, 44]),
)


class AcLabelBindings(FieldReplay):
    return_leaf = EventReplay.return_leaf

    def __init__(self, raw):
        super().__init__(raw)
        self.u.mem_map(HEAP, 0x1000)

    def allocate(self, size, return_pc):
        assert size in (0x4C,) or 0 < size <= 32, (size, hex(return_pc))
        address = self.heap
        self.heap += (size + 7) & ~7
        assert self.heap <= self.heap_end
        self.allocations[address] = size
        self.allocation_log.append([hex(return_pc), hex(address), size])
        return address

    def emulate_leaf(self, u, pc, lr, r0):
        if pc == ALLOCATE:
            return self.allocate(r0, lr)
        if pc == 0x80032AE4:
            size = u.reg_read(UC_ARM_REG_R1)
            address = self.allocate(size, lr)
            if r0:
                old_size = self.allocations.pop(r0)
                u.mem_write(address, bytes(u.mem_read(r0, min(old_size, size))))
                self.frees.append(r0)
            return address
        if pc == 0x80032A80:
            assert r0 in self.allocations
            self.allocations.pop(r0)
            self.frees.append(r0)
            return 0
        if pc == 0x80024CA4:
            return r0
        return super().emulate_leaf(u, pc, lr, r0)

    def code(self, u, pc, size, data):
        if not self.gui:
            return super().code(u, pc, size, data)
        if pc == STOP:
            u.emu_stop()
            return
        r0, r1, r2, r3, lr = (u.reg_read(reg) for reg in (
            UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_LR,
        ))
        if pc == STYLE_WRITE:
            assert r0 in self.labels and r3 == 0
            self.styles[r0, r1] = r2
            self.style_calls.append([hex(r0), hex(r1), hex(r2), hex(lr)])
            self.return_leaf(u, lr, 0)
            return
        if pc == STYLE_FIND:
            assert r0 in self.labels and r3 == 0 and r1 in (1, 4, 7, 8)
            assert (r0, r1) not in self.styles
            self.return_leaf(u, lr, 0)
            return
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def write(self, u, access, address, size, value, data):
        pc = u.reg_read(UC_ARM_REG_PC)
        if self.gui and pc in STORES:
            assert (address, size, value) == (self.context + STORES[pc], 4, self.labels[-1])
            self.stores.append([hex(pc), hex(address), hex(value)])
        super().write(u, access, address, size, value, data)

    def run(self):
        u = self.u
        self.context, self.heap, self.heap_end = CONTEXT, HEAP, HEAP + 0x1000
        self.allocations, self.leaves = {}, {}
        self.styles, self.style_calls = {}, []
        self.allocation_log, self.parents, self.labels = [], [PARENT], []
        self.stores, self.text_calls, self.frees = [], [], []
        u.mem_write(CONTEXT - 4, b"\xA5" * 4 + bytes(0x4C8) + b"\x5A" * 4)
        u.mem_write(PARENT, bytes(0x80))
        self.put(PARENT + 8, PARENT + 0x50)
        self.put(CONTEXT + 0x268, PARENT)
        for reg, value in ((UC_ARM_REG_R4, CONTEXT), (UC_ARM_REG_R7, 0x222222), (UC_ARM_REG_SP, STACK),
                           (UC_ARM_REG_CPSR, 0x13)):
            u.reg_write(reg, value)
        self.gui = True
        try:
            u.emu_start(ENTRY, 0, count=20_000)
        finally:
            self.gui = False
        assert (u.reg_read(UC_ARM_REG_PC), u.reg_read(UC_ARM_REG_SP)) == (STOP, STACK)
        assert self.read(CONTEXT - 4) == 0xA5A5A5A5 and self.read(CONTEXT + 0x4C8) == 0x5A5A5A5A
        assert len(self.labels) == 2 and self.labels[0] != self.labels[1]
        assert self.read(PARENT + 0x54) == 2
        children = self.read(PARENT + 0x50)
        assert [self.read(children + 4 * i) for i in range(2)] == self.labels
        rows = []
        for widget, expected in zip(self.labels, EXPECTED):
            assert self.read(CONTEXT + expected["offset"]) == widget
            assert self.read(widget) == LABEL_CLASS and self.read(widget + 4) == PARENT
            text = bytes(u.mem_read(self.read(widget + 0x24), len(expected["text"]) + 1))
            assert text == expected["text"].encode("ascii") + b"\0"
            assert self.styles[widget, FONT] == expected["font"]
            assert [self.styles[widget, key] for key in (7, 8)] == expected["position"]
            assert [self.styles[widget, key] for key in (1, 4)] == expected["size"]
            assert self.styles[widget, 0x58] == self.styles[widget, 0x59] == 0
            flags = bytes(u.mem_read(widget + 0x48, 1))[0]
            assert flags & 0x27 == 0
            rows.append(dict(**expected, widget=hex(widget), label_flags=flags,
                             styles={hex(key): value for (obj, key), value in self.styles.items() if obj == widget}))
        return dict(labels=rows, context_stores=self.stores, style_calls=self.style_calls,
                    allocations=self.allocation_log, text_calls=self.text_calls,
                    instruction_bytes={hex(pc): encoded for pc, encoded in sorted(self.coverage.items())})


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
        observations.append(AcLabelBindings(raw).run())
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.ac-label-bindings.v1", images=images, **observations[0], limits=[
        "Both native class allocations, object stores, initial text copies and style-argument wrappers execute.",
        "Heap allocation and the style-storage sink are fixtures. The parent and prior color argument are seeded.",
        "Position and size are firmware style arguments. No physical layout or LCD pixels are observed.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 2 original AC label bindings per factory image, 4 total")


if __name__ == "__main__":
    main()
