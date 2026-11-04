"""Extract an eGON main payload without changing the source flash image."""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path

HEADER_OFFSET = 0x50000
HEADER_SIZE = 0x20
MAGIC = b"eGON.EXE"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    source = args.input.read_bytes()
    header = source[HEADER_OFFSET:HEADER_OFFSET + HEADER_SIZE]
    if len(header) != HEADER_SIZE or header[4:12] != MAGIC:
        raise SystemExit("missing eGON.EXE header at flash offset 0x50000")
    image_size = struct.unpack_from("<I", header, 0x10)[0]
    if image_size < HEADER_SIZE or HEADER_OFFSET + image_size > len(source):
        raise SystemExit(f"unsafe eGON image size: 0x{image_size:x}")

    payload = source[HEADER_OFFSET + HEADER_SIZE:HEADER_OFFSET + image_size]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    report = {
        "schema": "ys4470.egon.extract.v1",
        "source_bytes": len(source),
        "source_sha256": digest(source),
        "header_offset": f"0x{HEADER_OFFSET:x}",
        "declared_image_bytes": image_size,
        "payload_offset": f"0x{HEADER_OFFSET + HEADER_SIZE:x}",
        "payload_bytes": len(payload),
        "payload_sha256": digest(payload),
        "write_scope": "new derived payload only; source image opened read-only",
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

