"""Differential check of separately compiled C against the original ARM dispatcher."""

import argparse
import json
import struct
from itertools import product
from pathlib import Path

from trace_deferred_producers import CTRL, DEFERRED, FSM
from trace_type6_queue import RealQueueReplay
from trace_uart_correlation import sha
from validate_uart_correlation import Compiled

OUTPUT = 0x30000300
PLAN = struct.Struct("<9I")
MARKER = bytes([0xA5]) * PLAN.size
INITIAL_CONFIGURED = 0x12345678
INITIAL_DISCARD = 0xA5


class OriginalDispatcher(RealQueueReplay):
    def memory(self, u, access, address, size, value, data):
        if address == CTRL + 8 and size == 4:
            return
        super().memory(u, access, address, size, value, data)

    def probe(self, record_type, primary, secondary):
        self.reset()
        self.configuring = False
        self.put(CTRL + 8, INITIAL_CONFIGURED)
        self.u.mem_write(CTRL + 1, bytes([INITIAL_DISCARD]))
        self.u.mem_write(DEFERRED, struct.pack("<IBB", record_type, primary, secondary) + bytes(62))
        result = self.invoke(0x80004390, (DEFERRED,))
        assert result in (0, 1)
        configured, discard = self.rd(CTRL + 8), self.byte(CTRL + 1)
        if not result:
            assert configured == INITIAL_CONFIGURED and discard == INITIAL_DISCARD
            assert self.byte(FSM) == self.byte(FSM + 0x34) == 0
            return result, MARKER
        assert self.byte(FSM) == self.byte(FSM + 0x34) == 1
        updates = int((configured, discard) != (INITIAL_CONFIGURED, INITIAL_DISCARD))
        commands = struct.unpack("<4I", self.u.mem_read(FSM + 4, 16))
        return result, PLAN.pack(self.byte(FSM + 1), self.rd(FSM + 0x14), *commands, updates,
                                 configured if updates else 0, discard if updates else 0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--object", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--compiler", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    compiled = Compiled(args.object, "ys4470_make_measurement_plan")
    cases = list(product((2, 3, 4, 5), (0x0C, 0xFF), range(256)))
    cases.extend((kind, 0x0C, 0x15) for kind in (0, 1, 6, 7, 8, 0xFFFFFFFF))
    versions, shared = [], None
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        original = OriginalDispatcher(raw)
        rows = bytearray()
        for inputs in cases:
            expected, expected_bytes = original.probe(*inputs)
            compiled.u.mem_write(OUTPUT, MARKER)
            actual = compiled.call((*inputs, OUTPUT))
            assert actual == expected
            assert bytes(compiled.u.mem_read(OUTPUT, PLAN.size)) == expected_bytes
            rows.extend(struct.pack("<4I", *inputs, expected) + expected_bytes)
        if shared is None:
            shared = sha(rows)
        assert shared == sha(rows)
        versions.append(dict(version=item["version"], input_sha256=item["sha256"], cases=len(cases),
                             original_instruction_bytes={hex(pc): value for pc, value in sorted(original.coverage.items())}))
    def source_hash(path):
        return sha(path.read_text(encoding="utf-8").encode("utf-8"))

    args.out.write_text(json.dumps(dict(
        schema="ys4470.measurement-plan-differential.v1", versions=versions, compiler=args.compiler,
        source_hash_rule="UTF-8 source with LF line endings",
        test_sha256=source_hash(Path(__file__)),
        c_source_sha256=source_hash(Path(__file__).with_name("measurement_plan.c")),
        c_header_sha256=source_hash(Path(__file__).with_name("measurement_plan.h")),
        arm_object_sha256=sha(args.object.read_bytes()), comparison_sha256=shared,
        compiled_executed_addresses=[hex(pc) for pc in sorted(compiled.coverage)],
        cases_total=len(cases)*len(versions), rejected_record_types=[0, 1, 6, 7, 8, 0xFFFFFFFF],
        scope="Pure plan with a valid output pointer. Original dispatcher/builder execute. Queue arbitration and I/O are separate.",
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS", len(cases)*len(versions), "original versus separately compiled ARM plan cases")


if __name__ == "__main__":
    main()
