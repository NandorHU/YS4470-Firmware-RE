"""Find direct callers of TransactionBuilder and decode their static command lists.

The parser intentionally recognizes only a narrow ARM subset (MOV immediate
and PC-literal LDR) within a fixed window immediately preceding a direct BL.
It reports an unresolved register rather than inventing a value.  The emitted
PyGhidra windows preserve the raw instructions for review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


LINK_BASE = 0x7FFFFFE0
LANGUAGE = "ARM:LE:32:v5t"
TRANSACTION_BUILDER = 0x8000489C


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def word_at(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - LINK_BASE)[0]


def arm_branch_target(address: int, word: int) -> int | None:
    if ((word >> 25) & 0x7) != 0x5:
        return None
    displacement = word & 0x00FFFFFF
    if displacement & 0x00800000:
        displacement -= 0x01000000
    return (address + 8 + (displacement << 2)) & 0xFFFFFFFF


def is_bl_to(address: int, word: int, target: int) -> bool:
    return bool(word & (1 << 24)) and arm_branch_target(address, word) == target


def decode_mov_immediate(word: int) -> tuple[int, int] | None:
    """Decode ARM MOV Rd,#imm (no flag tracking needed for this trace)."""
    if (word & 0x0C000000) != 0 or not (word & (1 << 25)):
        return None
    if ((word >> 21) & 0xF) != 13:
        return None
    imm8 = word & 0xFF
    rotate = ((word >> 8) & 0xF) * 2
    value = ((imm8 >> rotate) | (imm8 << (32 - rotate))) & 0xFFFFFFFF if rotate else imm8
    return (word >> 12) & 0xF, value


def decode_pc_literal_load(address: int, word: int) -> tuple[int, int] | None:
    if (word & 0x0C000000) != 0x04000000 or word & (1 << 25):
        return None
    if not (word & (1 << 20)) or not (word & (1 << 24)) or ((word >> 16) & 0xF) != 15:
        return None
    offset = word & 0xFFF
    literal = address + 8 + (offset if word & (1 << 23) else -offset)
    return (word >> 12) & 0xF, literal & 0xFFFFFFFF


def decode_mov_register(word: int) -> tuple[int, int] | None:
    """Decode an unshifted ARM MOV Rd,Rs used in the bounded call setup."""
    if (word & 0x0C000000) != 0 or word & (1 << 25):
        return None
    if ((word >> 21) & 0xF) != 13 or ((word >> 4) & 0xFF) != 0:
        return None
    return (word >> 12) & 0xF, word & 0xF


def preceding_arguments(image: bytes, call_address: int, window_words: int = 20) -> dict[str, Any]:
    """Evaluate the trace subset up to a direct BL and decode r1's word list."""
    registers: dict[int, int] = {}
    updates: list[dict[str, str]] = []
    for address in range(call_address - window_words * 4, call_address, 4):
        word = word_at(image, address)
        mov = decode_mov_immediate(word)
        if mov is not None:
            register, value = mov
            registers[register] = value
            updates.append({"address": f"0x{address:08x}", "register": f"r{register}", "value": f"0x{value:08x}", "kind": "mov_immediate"})
            continue
        register_mov = decode_mov_register(word)
        if register_mov is not None:
            destination, source = register_mov
            if source in registers:
                registers[destination] = registers[source]
                updates.append({"address": f"0x{address:08x}", "register": f"r{destination}", "value": f"0x{registers[source]:08x}", "kind": f"mov_register_r{source}"})
            else:
                registers.pop(destination, None)
                updates.append({"address": f"0x{address:08x}", "register": f"r{destination}", "value": "<unresolved>", "kind": f"mov_register_r{source}"})
            continue
        literal = decode_pc_literal_load(address, word)
        if literal is not None:
            register, literal_address = literal
            if LINK_BASE <= literal_address <= LINK_BASE + len(image) - 4:
                value = word_at(image, literal_address)
                registers[register] = value
                updates.append({"address": f"0x{address:08x}", "register": f"r{register}", "value": f"0x{value:08x}", "kind": "pc_literal", "literal_address": f"0x{literal_address:08x}"})
    values = {f"r{register}": (None if register not in registers else f"0x{registers[register]:08x}") for register in (0, 1, 2)}
    commands: list[str] | None = None
    source = registers.get(1)
    count = registers.get(2)
    if source is not None and count is not None and 0 <= count <= 4 and LINK_BASE <= source <= LINK_BASE + len(image) - count * 4:
        commands = [f"0x{word_at(image, source + index * 4):02x}" for index in range(count)]
    return {"argument_updates": updates, "arguments": values, "decoded_command_words": commands}


def disassembly_window(flat: Any, start: int, count: int) -> list[dict[str, str]]:
    listing = flat.getCurrentProgram().getListing()
    memory = flat.getCurrentProgram().getMemory()
    rows: list[dict[str, str]] = []
    for index in range(count):
        address = start + index * 4
        candidate = flat.toAddr(f"{address:08x}")
        flat.disassemble(candidate)
        instruction = listing.getInstructionAt(candidate)
        word = memory.getInt(candidate) & 0xFFFFFFFF
        rows.append({"address": f"0x{address:08x}", "raw_word": f"0x{word:08x}", "assembly": "<not decoded>" if instruction is None else str(instruction)})
    return rows


def collect(image_path: Path, project_root: Path, ghidra_dir: Path) -> dict[str, Any]:
    import pyghidra

    image = image_path.read_bytes()
    sites = [
        LINK_BASE + offset
        for offset in range(0, len(image) - 3, 4)
        if is_bl_to(LINK_BASE + offset, struct.unpack_from("<I", image, offset)[0], TRANSACTION_BUILDER)
    ]
    pyghidra.start(install_dir=ghidra_dir)
    with pyghidra.open_program(
        image_path,
        project_location=project_root,
        project_name="ys4470_measurement_command_sequences",
        program_name=image_path.name,
        analyze=False,
        language=LANGUAGE,
        loader="ghidra.app.util.opinion.BinaryLoader",
    ) as flat:
        program = flat.getCurrentProgram()
        transaction = program.startTransaction("bounded TransactionBuilder caller trace")
        try:
            desired = flat.toAddr(f"{LINK_BASE:08x}")
            if program.getImageBase() != desired:
                program.setImageBase(desired, True)
            calls = [
                {
                    "call_address": f"0x{address:08x}",
                    "raw_word": f"0x{word_at(image, address):08x}",
                    "target": f"0x{TRANSACTION_BUILDER:08x}",
                    "static_arguments": preceding_arguments(image, address),
                    "window": disassembly_window(flat, address - 48 * 4, 56),
                }
                for address in sites
            ]
        finally:
            program.endTransaction(transaction, True)
    return {
        "schema": "ys4470.measurement-command-sequences.v1",
        "method": "raw ARM direct-BL scan plus fixed backward subset evaluation and PyGhidra windows; unresolved register values remain null",
        "input": {"name": image_path.name, "bytes": len(image), "sha256": sha256(image_path)},
        "link_base": f"0x{LINK_BASE:08x}",
        "transaction_builder": f"0x{TRANSACTION_BUILDER:08x}",
        "calls": calls,
    }


def self_test() -> None:
    assert arm_branch_target(0x80000000, 0xEB000001) == 0x8000000C
    assert is_bl_to(0x80000000, 0xEB000001, 0x8000000C)
    assert decode_mov_immediate(0xE3A02004) == (2, 4)
    assert decode_mov_immediate(0xE3A00000) == (0, 0)
    assert decode_mov_register(0xE1A0100D) == (1, 13)
    assert decode_pc_literal_load(0x80000000, 0xE59F1020) == (1, 0x80000028)
    print("self_test=passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--ghidra", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.input or not args.ghidra or not args.out:
        parser.error("--input, --ghidra, and --out are required unless --self-test is used")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = collect(args.input, args.out.parent / "ghidra-projects", args.ghidra)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {args.out}; {len(report['calls'])} direct calls")


if __name__ == "__main__":
    main()

