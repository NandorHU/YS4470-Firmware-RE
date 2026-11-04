"""Report contiguous byte differences between equal-layout raw firmware images."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("left", type=Path)
    parser.add_argument("right", type=Path)
    parser.add_argument("--base", type=lambda value: int(value, 0), required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    left, right = args.left.read_bytes(), args.right.read_bytes()
    if len(left) != len(right):
        raise SystemExit("raw layouts differ in length; extract/normalize before byte diff")
    ranges = []
    index = 0
    while index < len(left):
        if left[index] == right[index]:
            index += 1
            continue
        start = index
        while index < len(left) and left[index] != right[index]:
            index += 1
        end = index
        ranges.append({
            "file_offset_start": f"0x{start:x}",
            "file_offset_end_exclusive": f"0x{end:x}",
            "arm_address_start": f"0x{args.base + start:08x}",
            "arm_address_end_exclusive": f"0x{args.base + end:08x}",
            "length": end - start,
            "left_sha256": sha256(left[start:end]),
            "right_sha256": sha256(right[start:end]),
        })
    output = {
        "schema": "ys4470.raw-diff.v1",
        "left": {"name": args.left.name, "bytes": len(left), "sha256": sha256(left)},
        "right": {"name": args.right.name, "bytes": len(right), "sha256": sha256(right)},
        "link_base": f"0x{args.base:08x}",
        "different_ranges": ranges,
        "different_byte_count": sum(item["length"] for item in ranges),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"{len(ranges)} ranges / {output['different_byte_count']} bytes")


if __name__ == "__main__":
    main()

