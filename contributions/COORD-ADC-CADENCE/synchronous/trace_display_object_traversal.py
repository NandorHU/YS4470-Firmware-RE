"""Execute native object traversal and ancestor post-draw dispatch."""

import argparse
import hashlib
import json
from pathlib import Path

from unicorn.arm_const import UC_ARM_REG_LR, UC_ARM_REG_PC, UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2

from trace_display_refresh_setup import SetupReplay, CONTEXT, DISPLAY, GLOBAL, RETURN

NODES = {name: 0x11004000 + index * 0x100 for index, name in enumerate(("grand", "root", "a", "b", "c", "d"))}
NAMES = {address: name for name, address in NODES.items()}
PARENTS = {"grand": None, "root": "grand", "a": "root", "b": "root", "c": "root", "d": "grand"}
WINDOWS = ((0x80044378, 0x80044448), (0x80035EB4, 0x80035EC0),
           (0x80035ABC, 0x80035ACC), (0x80025D84, 0x80025DA4))


class ObjectReplay(SetupReplay):
    def __init__(self, raw):
        super().__init__(raw)
        self.events = []

    def code(self, u, pc, size, data):
        if pc == self.stop:
            u.emu_stop()
            return
        if pc in (0x80043EB0, 0x8002C758):
            args = [u.reg_read(reg) for reg in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2)]
            if pc == 0x80043EB0:
                assert args[0] == CONTEXT and args[1] in NAMES
                self.events.append(["render", NAMES[args[1]]])
            else:
                assert args[0] in NAMES and args[1] in (0x17, 0x18, 0x19) and args[2] == CONTEXT
                self.events.append(["event", NAMES[args[0]], args[1]])
            u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))
            return
        if any(lo <= pc < hi for lo, hi in WINDOWS):
            assert size == 4
            self.coverage[pc] = bytes(u.mem_read(pc, size)).hex()
            return
        super().code(u, pc, size, data)

    def run_objects(self):
        self.execute(0x8003B080, 0x80025AC8)
        self.put(GLOBAL + 4, DISPLAY)
        cases = []
        for reverse in (False, True):
            children = {"grand": ["root", "d"], "root": ["a", "b", "c"]}
            if reverse:
                children = {node: list(reversed(items)) for node, items in children.items()}
            for index, (name, address) in enumerate(NODES.items()):
                self.u.mem_write(address, bytes(0x20))
                parent = PARENTS[name]
                self.put(address + 4, NODES[parent] if parent else 0)
                members = children.get(name, [])
                if members:
                    special, array = 0x11006000 + index * 0x20, 0x11007000 + index * 0x20
                    self.put(address + 8, special)
                    self.put(special, array)
                    self.put(special + 4, len(members))
                    for position, child in enumerate(members):
                        self.put(array + 4 * position, NODES[child])
            for requested in ("grand", "root", "a", "b", "c", "d", "default", "empty-default"):
                self.put(DISPLAY + 0x10, 0 if requested == "empty-default" else NODES["root"])
                target = "root" if requested == "default" else None if requested == "empty-default" else requested
                expected = []
                if target:
                    expected.append(["render", target])
                    current = target
                    while PARENTS[current]:
                        parent = PARENTS[current]
                        siblings = children[parent]
                        expected.extend(["render", name] for name in siblings[siblings.index(current) + 1:])
                        expected.extend(["event", parent, event] for event in (0x17, 0x18, 0x19))
                        current = parent
                self.events = []
                self.execute(0x80044378, RETURN, (
                    (UC_ARM_REG_R0, CONTEXT),
                    (UC_ARM_REG_R1, 0 if requested in ("default", "empty-default") else NODES[requested])))
                assert self.events == expected, (reverse, requested, self.events, expected)
                cases.append(dict(reverse_children=reverse, requested=requested, dispatches=self.events))
        return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        replay = ObjectReplay(raw)
        cases = replay.run_objects()
        observations.append((cases, replay.coverage))
    assert observations[0] == observations[1]
    cases, coverage = observations[0]
    report = dict(schema="ys4470.native-display-object-traversal.v1", images=images, cases=cases,
                  instruction_bytes={hex(pc): word for pc, word in sorted(coverage.items())},
                  limits=["Original object traversal, parent lookup, child count and default-root getter execute.",
                          "The object tree, child order, active display and default root are fixtures.",
                          "Object renderer 0x80043eb0 and event dispatcher 0x8002c758 are modeled boundaries.",
                          "This records top-level renderer calls and ancestor post-draw events.",
                          "Recursive object painting, native label integration and physical LCD output remain open."])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print("PASS 32 native object traversal schedules across both factory images")


if __name__ == "__main__":
    main()
