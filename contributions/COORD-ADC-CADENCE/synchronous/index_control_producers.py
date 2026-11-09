"""Index aligned ARM immediate branch candidates to the original record producer."""

import argparse
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

BASE = 0x7FFFFFE0
PRODUCER = 0x80006778


def sha(data):
    return hashlib.sha256(data).hexdigest()


def classify(suffix):
    setup = [i for i in suffix[:-1] if i.op_str.startswith("r0, #") and i.mnemonic.startswith("mov")]
    last = setup[-1]
    if last.mnemonic == "mov":
        return [int(last.op_str[5:], 0)]
    assert [i.mnemonic for i in suffix] == ["cmp", "moveq", "movne", "bl"]
    return sorted(int(i.op_str[5:], 0) for i in setup)


def index(raw):
    decoder = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    calls, pointers = [], []
    for index, (word,) in enumerate(struct.iter_unpack("<I", raw)):
        pc = BASE + index * 4
        if word == PRODUCER:
            pointers.append(hex(pc))
        if word >> 28 == 15 or word & 0x0E000000 != 0x0A000000:
            continue
        signed_offset = (((word & 0xFFFFFF) ^ 0x800000) - 0x800000) * 4
        if pc + 8 + signed_offset != PRODUCER:
            continue
        offset = index * 4
        instructions = list(decoder.disasm(raw[offset - 12:offset + 4], pc - 12))
        assert len(instructions) == 4 and instructions[-1].op_str == "#" + hex(PRODUCER)
        types = classify(instructions)
        calls.append(dict(address=hex(pc), local_r0_values=types, instructions=[
            dict(pc=hex(i.address), bytes=i.bytes.hex(), asm=f"{i.mnemonic} {i.op_str}")
            for i in instructions
        ]))
    counts = Counter(kind for site in calls for kind in site["local_r0_values"])
    assert len(calls) == 31 and dict(counts) == {0: 1, 1: 9, 2: 17, 3: 2, 4: 1, 5: 2}
    assert pointers == []
    return dict(calls=calls, aligned_pointer_hits=pointers, site_counts_by_local_r0=counts)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[3]
    manifest = json.loads((root / "original-firmware/manifest.json").read_text())
    results, versions = [], []
    for item in manifest["images"]:
        raw = (root / item["path"]).read_bytes()
        assert sha(raw) == item["sha256"] and len(raw) == item["size_bytes"]
        results.append(index(raw))
        versions.append(dict(version=item["version"], input_sha256=item["sha256"]))
    assert results[0] == results[1]
    args.out.write_text(json.dumps(dict(
        schema="ys4470.control-producer-references.v1", source_sha256=sha(Path(__file__).read_bytes()),
        producer=hex(PRODUCER), versions=versions, identical_observations=results[0],
        limits=[
            "Full-file aligned ARM immediate B/BL scan and aligned absolute pointer search.",
            "R0 values describe the decoded local setup suffix, with both conditions at 0x8005d130.",
            "Coverage excludes indirect or synthesized targets, alternate queue writers and reachability.",
        ],
    ), indent=2) + "\n", encoding="utf-8")
    print("PASS 31 identical direct branch candidates per original")


if __name__ == "__main__":
    main()
