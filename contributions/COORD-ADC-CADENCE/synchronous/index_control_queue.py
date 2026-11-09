"""Index bounded, instruction-byte-checked references to the control queue."""

import argparse
import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs

from index_control_producers import BASE, sha

CONTROL = 0x805AAE8C
HANDLE = CONTROL + 4
DEFERRED = 0x805AC6D0
CONSTRUCTOR = 0x800029DC
PRODUCER = 0x80006778
SEND = 0x80061ACC
RECEIVE = 0x800618DC
TARGETS = (CONSTRUCTOR, PRODUCER, SEND, RECEIVE)
VALUES = (CONTROL, HANDLE, DEFERRED, *TARGETS)
HANDLE_USES = {
    0x800029F4: ("str", "r0, [r1, #4]", 0x800029F0),
    0x80003D7C: ("ldr", "r4, [r0, #4]", 0x80003D78),
    0x80005B78: ("ldr", "r0, [r4, #4]", 0x80005B70),
    0x80005CA8: ("ldr", "r0, [r4, #4]", 0x80005B70),
    0x80006784: ("ldr", "r0, [r0, #4]", 0x8000677C),
}


def index(raw):
    arm, thumb = (Cs(CS_ARCH_ARM, mode) for mode in (CS_MODE_ARM, CS_MODE_THUMB))
    end = BASE + len(raw)
    direct = {target: [] for target in TARGETS}
    aligned = {value: [] for value in VALUES}
    literal_loads = []

    def decode(pc, decoder):
        code = raw[pc - BASE:pc - BASE + 4]
        ins = next(decoder.disasm(code, pc))
        assert ins.size == 4
        return dict(pc=hex(pc), bytes=ins.bytes.hex(), mnemonic=ins.mnemonic, operands=ins.op_str)

    for offset, (word,) in enumerate(struct.iter_unpack("<I", raw)):
        pc = BASE + 4 * offset
        if word in aligned:
            aligned[word].append(hex(pc))
        if word >> 28 != 15 and word & 0x0E000000 == 0x0A000000:
            disp = (((word & 0xFFFFFF) ^ 0x800000) - 0x800000) * 4
            target = pc + 8 + disp
            if target in direct:
                entry = decode(pc, arm)
                assert entry["operands"] == "#" + hex(target)
                direct[target].append(dict(isa="ARM", **entry))
        if word & 0x0F7F0000 == 0x051F0000:
            loc = pc + 8 + (word & 0xFFF) * (1 if word & 0x800000 else -1)
            if BASE <= loc <= end - 4:
                value = struct.unpack_from("<I", raw, loc - BASE)[0]
                if value in (CONTROL, HANDLE, DEFERRED):
                    literal_loads.append(dict(literal=hex(loc), value=hex(value), **decode(pc, arm)))

    for index, (hi,) in enumerate(struct.iter_unpack("<H", raw)):
        offset = index * 2
        if hi & 0xF800 != 0xF000 or offset + 4 > len(raw):
            continue
        lo = struct.unpack_from("<H", raw, offset + 2)[0]
        if lo & 0xF801 != 0xE800:
            continue
        pc = BASE + offset
        disp = ((((hi & 0x7FF) ^ 0x400) - 0x400) << 12) + ((lo & 0x7FF) << 1)
        target = (pc + 4 + disp) & ~3
        if target in direct:
            entry = decode(pc, thumb)
            assert entry["mnemonic"] == "blx" and entry["operands"] == "#" + hex(target)
            direct[target].append(dict(isa="Thumb", **entry))

    assert [i["pc"] for i in direct[CONSTRUCTOR]] == ["0x800418a4"]
    assert [i["pc"] for i in direct[SEND]] == ["0x800067b8"]
    assert [i["pc"] for i in direct[RECEIVE]] == ["0x80003da0", "0x80005b90", "0x80005cb4"]
    assert len(direct[PRODUCER]) == 31 and all(i["isa"] == "ARM" for rows in direct.values() for i in rows)
    assert not aligned[HANDLE] and all(not aligned[target] for target in TARGETS)
    bases = {entry["pc"] for entry in literal_loads if entry["value"] == hex(CONTROL)}
    uses = []
    for pc, (mnemonic, operands, source) in HANDLE_USES.items():
        row = decode(pc, arm)
        assert (row["mnemonic"], row["operands"]) == (mnemonic, operands) and hex(source) in bases
        uses.append(dict(control_literal_load=hex(source), **row))
    return dict(
        direct_candidates={hex(k): v for k, v in direct.items()},
        aligned_exact_words={hex(k): v for k, v in aligned.items()},
        control_literal_loads=literal_loads, reviewed_handle_accesses=uses,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo / "original-firmware/manifest.json").read_text())
    versions, rows = [], []
    for item in manifest["images"]:
        raw = (repo / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        rows.append(index(raw))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"]))
    assert rows[0] == rows[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.control-queue-index.v1", versions=versions, source_sha256=sha(Path(__file__).read_bytes()),
        shared_observations=rows[0],
        scope=[
            "Full file aligned ARM B/BL, ARMv5 Thumb immediate BLX, ARM immediate PC literal load and aligned word scans.",
            "Handle uses are reviewed local accesses. No whole-program register or memory alias proof.",
            "Synthesized or indirect targets, alternative send primitives, RAM-created tables and inlined writes remain open.",
        ],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS queue references agree across both originals")


if __name__ == "__main__":
    main()
