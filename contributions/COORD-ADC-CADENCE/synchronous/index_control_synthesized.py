"""Index immediate and two-instruction materializations of control-queue addresses."""

import argparse
import hashlib
import json
import struct
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB, Cs
from index_control_queue import BASE, CONTROL, DEFERRED, HANDLE, PRODUCER, RECEIVE, SEND

TARGETS = (CONTROL, HANDLE, DEFERRED, PRODUCER, SEND, RECEIVE)
MASK32 = 0xFFFFFFFF
ARM_ADD, ARM_SUB, ARM_ORR, ARM_MOV, ARM_BIC, ARM_MVN = 4, 2, 12, 13, 14, 15


def immediate(word):
    rotate = ((word >> 8) & 15) * 2
    value = word & 0xFF
    return ((value >> rotate) | (value << (32 - rotate))) & MASK32


def combine(opcode, left, right):
    if opcode == ARM_ADD:
        return (left + right) & MASK32
    if opcode == ARM_SUB:
        return (left - right) & MASK32
    if opcode == ARM_ORR:
        return left | right
    if opcode == ARM_BIC:
        return left & ~right
    return None


def first_arm(raw, pc, word):
    if word >> 28 == 15:
        return None
    destination = (word >> 12) & 15
    if word & 0x0F7F0000 == 0x051F0000:
        location = pc + 8 + (word & 0xFFF) * (1 if word & 0x800000 else -1)
        offset = location - BASE
        # The instruction is an aligned word load. Treat unaligned matches as
        # raw pointer bytes only, without inferring ARM926 load rotation.
        if location % 4 == 0 and 0 <= offset <= len(raw) - 4:
            value, = struct.unpack_from("<I", raw, offset)
            return destination, value, "literal", location
    elif word & 0x0E100000 == 0x02000000:
        opcode = (word >> 21) & 15
        source = (word >> 16) & 15
        value = immediate(word)
        if opcode == ARM_MOV and source == 0:
            return destination, value, "constant", None
        if opcode == ARM_MVN and source == 0:
            return destination, value ^ MASK32, "constant", None
        if source == 15 and opcode in (ARM_ADD, ARM_SUB):
            return destination, combine(opcode, pc + 8, value), "pc_relative", None
    return None


def add_arm(second, condition, register, value):
    if second >> 28 != condition or second & 0x0E100000 != 0x02000000:
        return None
    if (second >> 16) & 15 != register:
        return None
    return combine((second >> 21) & 15, value, immediate(second))


def thumb_origin(raw, pc, halfword):
    location = ((pc + 4) & ~3) + (halfword & 0xFF) * 4
    if halfword & 0xF800 == 0xA000:
        return location, "pc_relative", None
    if halfword & 0xF800 == 0x4800 and 0 <= location - BASE <= len(raw) - 4:
        value, = struct.unpack_from("<I", raw, location - BASE)
        return value, "literal", location
    return None


def find_references(raw):
    arm, thumb = (Cs(CS_ARCH_ARM, mode) for mode in (CS_MODE_ARM, CS_MODE_THUMB))
    exact_words = {hex(v): [] for v in TARGETS}
    references = []

    def decoded(decoder, pc, size):
        offset = pc - BASE
        instruction, = decoder.disasm(raw[offset:offset + size], pc)
        assert instruction.size == size
        return dict(address=hex(pc), bytes=instruction.bytes.hex(),
                    assembly=f"{instruction.mnemonic} {instruction.op_str}".strip())

    def record(isa, target, kind, literal, *instructions):
        references.append(dict(isa=isa, target=hex(target), kind=kind,
                               literal=hex(literal) if literal is not None else None,
                               instructions=list(instructions)))

    for target in TARGETS:
        needle = struct.pack("<I", target)
        offset = raw.find(needle)
        while offset >= 0:
            exact_words[hex(target)].append(dict(address=hex(BASE + offset), file_phase=offset % 4))
            offset = raw.find(needle, offset + 1)

    for index, (word,) in enumerate(struct.iter_unpack("<I", raw)):
        if word & 0x0E000000 not in (0x02000000, 0x04000000):
            continue
        pc = BASE + index * 4
        result = first_arm(raw, pc, word)
        if result is None:
            continue
        reg, target, kind, literal = result
        if target in TARGETS:
            record("ARM", target, kind, literal, decoded(arm, pc, 4))
        if reg == 15 or index * 4 + 8 > len(raw):
            continue
        next_word, = struct.unpack_from("<I", raw, index * 4 + 4)
        result = add_arm(next_word, word >> 28, reg, target)
        if result in TARGETS:
            record("ARM", result, kind + "_then_immediate", literal,
                   decoded(arm, pc, 4), decoded(arm, pc + 4, 4))

    for index, (halfword,) in enumerate(struct.iter_unpack("<H", raw)):
        if halfword & 0xF800 not in (0xA000, 0x4800):
            continue
        pc = BASE + index * 2
        origin = thumb_origin(raw, pc, halfword)
        if origin is None:
            continue
        target, kind, literal = origin
        if target in TARGETS:
            record("Thumb", target, kind, literal, decoded(thumb, pc, 2))
    return dict(exact_words=exact_words, references=references)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    manifest = json.loads(Path("original-firmware/manifest.json").read_bytes())
    assert manifest["linked_base"] == hex(BASE)
    # Positive controls for the immediate decoder, independent of image data.
    assert first_arm(b"", 0x1000, 0xE28F0004) == (0, 0x100C, "pc_relative", None)
    assert add_arm(0xE2801004, 14, 0, 0x100C) == 0x1010
    assert thumb_origin(b"", 0x1002, 0xA001) == (0x1008, "pc_relative", None)
    images, observations = {}, []
    for item in manifest["images"]:
        raw = Path(item["path"]).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == item["sha256"] and len(raw) == item["size_bytes"]
        images[item["version"]] = digest
        observations.append(find_references(raw))
    assert images.keys() == {"V3.6", "V3.8"} and observations[0] == observations[1]
    report = dict(schema="ys4470.control-synthesized-references.v1", images=images,
                  **observations[0], limits=[
        "Aligned ARM and halfword-aligned Thumb immediate encodings are scanned throughout the raw image. Exact pointer bytes are checked at all byte phases.",
        "ARM pairs are adjacent, same-condition operations and track one register only. No value flow across branches, computed tables, RAM aliases or interworking veneers is inferred.",
        "Raw encoding hits may be data. Existing original-execution evidence is required to classify an actual runtime caller.",
    ])
    args.out.write_bytes((json.dumps(report, indent=2) + "\n").encode())
    print(f"PASS matching control reference indexes, {len(report['references'])} raw hits per factory image")


if __name__ == "__main__":
    main()
