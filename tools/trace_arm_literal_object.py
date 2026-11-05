"""Find bounded direct ARM accesses to an object loaded through a PC literal.

This is a raw-binary helper for ARM mode code.  It deliberately emits direct,
local evidence only: it follows simple register-to-register MOV aliases within
a fixed sequential window and does not claim complete interprocedural dataflow.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


def parse_number(value: str) -> int:
    return int(value, 0)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def word_at(data: bytes, address: int, link_base: int) -> int:
    return struct.unpack_from("<I", data, address - link_base)[0]


def decode_immediate_transfer(word: int) -> dict[str, int | bool] | None:
    """Decode ARM immediate-offset LDR/STR; return None for other classes."""
    if (word & 0x0C000000) != 0x04000000 or word & (1 << 25):
        return None
    return {
        "pre_index": bool(word & (1 << 24)),
        "up": bool(word & (1 << 23)),
        "byte": bool(word & (1 << 22)),
        "load": bool(word & (1 << 20)),
        "base": (word >> 16) & 0xF,
        "register": (word >> 12) & 0xF,
        "offset": word & 0xFFF,
    }


def decode_pc_literal_load(address: int, word: int) -> tuple[int, int] | None:
    transfer = decode_immediate_transfer(word)
    if not transfer or not transfer["load"] or not transfer["pre_index"] or transfer["base"] != 15:
        return None
    literal_address = (address + 8 + (transfer["offset"] if transfer["up"] else -transfer["offset"])) & 0xFFFFFFFF
    return int(transfer["register"]), literal_address


def is_simple_mov(word: int) -> tuple[int, int] | None:
    # Data processing, register operand, MOV opcode, no shift.
    if (word & 0x0C000000) != 0 or word & (1 << 25) or ((word >> 21) & 0xF) != 13:
        return None
    if ((word >> 4) & 0xFF) != 0:
        return None
    return (word >> 12) & 0xF, word & 0xF


def accesses_after_literal(
    data: bytes, link_base: int, load_address: int, initial_register: int,
    wanted_offsets: set[int], window_words: int,
) -> list[dict[str, Any]]:
    aliases = {initial_register}
    records: list[dict[str, Any]] = []
    for step in range(1, window_words + 1):
        address = load_address + step * 4
        if not (link_base <= address <= link_base + len(data) - 4):
            break
        word = word_at(data, address, link_base)
        move = is_simple_mov(word)
        if move:
            destination, source = move
            if source in aliases:
                aliases.add(destination)
            elif destination in aliases:
                aliases.remove(destination)
        transfer = decode_immediate_transfer(word)
        if not transfer or int(transfer["base"]) not in aliases or int(transfer["offset"]) not in wanted_offsets:
            continue
        records.append({
            "address": f"0x{address:08x}",
            "raw_word": f"0x{word:08x}",
            "operation": ("ldr" if transfer["load"] else "str") + ("b" if transfer["byte"] else ""),
            "base_register": f"r{transfer['base']}",
            "data_register": f"r{transfer['register']}",
            "offset": f"0x{transfer['offset']:x}",
            "pre_index": bool(transfer["pre_index"]),
            "direction": "+" if transfer["up"] else "-",
        })
    return records


def analyze(path: Path, link_base: int, object_address: int, offsets: set[int], window_words: int) -> dict[str, Any]:
    data = path.read_bytes()
    occurrences = []
    needle = object_address.to_bytes(4, "little")
    position = 0
    while True:
        position = data.find(needle, position)
        if position < 0:
            break
        occurrences.append(f"0x{link_base + position:08x}")
        position += 1
    loads = []
    for offset in range(0, len(data) - 3, 4):
        address = link_base + offset
        word = struct.unpack_from("<I", data, offset)[0]
        decoded = decode_pc_literal_load(address, word)
        if decoded is None:
            continue
        destination, literal_address = decoded
        if not (link_base <= literal_address <= link_base + len(data) - 4):
            continue
        if word_at(data, literal_address, link_base) != object_address:
            continue
        loads.append({
            "load_address": f"0x{address:08x}",
            "raw_word": f"0x{word:08x}",
            "destination_register": f"r{destination}",
            "literal_address": f"0x{literal_address:08x}",
            "direct_accesses": accesses_after_literal(data, link_base, address, destination, offsets, window_words),
        })
    return {
        "schema": "ys4470.arm-literal-object-trace.v1",
        "method": "ARM immediate PC-literal load scan plus bounded simple-MOV alias window; incomplete by design",
        "input": {"name": path.name, "bytes": len(data), "sha256": sha256(path)},
        "link_base": f"0x{link_base:08x}",
        "object_address": f"0x{object_address:08x}",
        "wanted_offsets": [f"0x{value:x}" for value in sorted(offsets)],
        "window_words": window_words,
        "raw_literal_occurrences": occurrences,
        "pc_literal_loads": loads,
    }


def self_test() -> None:
    assert decode_pc_literal_load(0x80000000, 0xE59F1020) == (1, 0x80000028)
    assert decode_pc_literal_load(0x80000000, 0xE3A00001) is None
    assert is_simple_mov(0xE1A04001) == (4, 1)
    assert decode_immediate_transfer(0xE5C47000)["load"] is False
    print("self_test=passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path)
    parser.add_argument("--object", type=parse_number)
    parser.add_argument("--link-base", type=parse_number, default=0x7FFFFFE0)
    parser.add_argument("--offset", action="append", type=parse_number, default=[])
    parser.add_argument("--window-words", type=int, default=64)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.input or args.object is None or not args.out:
        parser.error("--input, --object, and --out are required unless --self-test is used")
    offsets = set(args.offset)
    if not offsets:
        parser.error("at least one --offset is required")
    if args.window_words <= 0:
        parser.error("--window-words must be positive")
    report = analyze(args.input, args.link_base, args.object, offsets, args.window_words)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"wrote {args.out}; {len(report['pc_literal_loads'])} PC-literal loads")


if __name__ == "__main__":
    main()

