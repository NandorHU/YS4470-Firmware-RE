"""Decode fixed-width measurement-command descriptors from a raw YS-4470 image.

Each entry is eight bytes: a 32-bit ARM pointer plus a source-byte count at
+4.  The send helper at 0x80005e84 copies that many source bytes, appends their
8-bit sum, then transmits source_count + 1 bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any


LINK_BASE = 0x7FFFFFE0
TABLE_BASE = 0x8006367C


def parse_number(value: str) -> int:
    return int(value, 0)


def parse_input(value: str) -> tuple[str, Path]:
    try:
        version, location = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use VERSION=PATH") from exc
    return version, Path(location)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decode_entry(data: bytes, link_base: int, table_base: int, command_id: int) -> dict[str, Any]:
    entry_address = table_base + command_id * 8
    entry_offset = entry_address - link_base
    if not (0 <= entry_offset <= len(data) - 8):
        raise ValueError(f"entry {command_id:#x} outside image")
    entry = data[entry_offset:entry_offset + 8]
    payload_pointer = struct.unpack_from("<I", entry)[0]
    source_length = entry[4]
    wire_length = source_length + 1
    payload_offset = payload_pointer - link_base
    if not (0 <= payload_offset <= len(data) - source_length):
        raise ValueError(f"entry {command_id:#x} payload outside image: {payload_pointer:#x}")
    source = data[payload_offset:payload_offset + source_length]
    checksum = sum(source) & 0xFF
    wire = source + bytes([checksum])
    return {
        "command_id": f"0x{command_id:02x}",
        "entry_address": f"0x{entry_address:08x}",
        "entry_bytes": entry.hex(),
        "payload_pointer": f"0x{payload_pointer:08x}",
        "source_length": source_length,
        "wire_length": wire_length,
        "source_hex": source.hex(),
        "checksum": f"0x{checksum:02x}",
        "wire_hex": wire.hex(),
        "wire_sha256": sha256(wire),
        "entry_tail_hex": entry[5:8].hex(),
    }


def analyze(version: str, path: Path, ids: list[int], table_base: int, link_base: int) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "version": version,
        "input": {"name": path.name, "bytes": len(data), "sha256": sha256(data)},
        "descriptors": [decode_entry(data, link_base, table_base, command_id) for command_id in ids],
    }


def self_test() -> None:
    image = bytearray(256)
    base = 0x80000000
    table = base + 0x20
    payload = base + 0x80
    struct.pack_into("<I", image, table - base + 0x18, payload)
    image[table - base + 0x1c] = 2
    image[payload - base:payload - base + 3] = b"\x58\x03\x58"
    decoded = decode_entry(bytes(image), base, table, 3)
    assert decoded["source_hex"] == "5803"
    assert decoded["checksum"] == "0x5b"
    assert decoded["wire_hex"] == "58035b"
    assert decoded["wire_length"] == 3
    assert decoded["entry_tail_hex"] == "000000"
    print("self_test=passed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=parse_input)
    parser.add_argument("--id", action="append", type=parse_number)
    parser.add_argument("--table-base", type=parse_number, default=TABLE_BASE)
    parser.add_argument("--link-base", type=parse_number, default=LINK_BASE)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.input or not args.id or not args.out:
        parser.error("--input, --id and --out are required unless --self-test is used")
    ids = sorted(set(args.id))
    reports = [analyze(version, path, ids, args.table_base, args.link_base) for version, path in args.input]
    pairs = []
    for command_id in ids:
        values = []
        for report in reports:
            entry = next(item for item in report["descriptors"] if item["command_id"] == f"0x{command_id:02x}")
            values.append({"version": report["version"], "wire_sha256": entry["wire_sha256"], "wire_hex": entry["wire_hex"]})
        pairs.append({
            "command_id": f"0x{command_id:02x}",
            "identical_wire_frames": len({item["wire_sha256"] for item in values}) == 1,
            "versions": values,
        })
    output = {
        "schema": "ys4470.measurement-descriptor-export.v1",
        "method": "8-byte pointer/count descriptors; 0x80005e84 copies source_length bytes, appends their 8-bit sum, and sends wire_length=source_length+1 bytes",
        "link_base": f"0x{args.link_base:08x}",
        "table_base": f"0x{args.table_base:08x}",
        "versions": reports,
        "cross_version": pairs,
        "limits": ["Descriptor payloads are not assigned physical measurement names without separate evidence."],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"wrote {args.out}; {len(ids)} descriptors across {len(reports)} versions")


if __name__ == "__main__":
    main()

