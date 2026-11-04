"""Deliberately narrow, read-only FEL probe for YS-4470 investigations.

Allowed device operations are only `--list` and `spiflash-info`; the program
contains no flash-write, RAM-exec, boot, or arbitrary memory-read path.
It is intended to confirm FEL transport availability, not to debug a running
firmware or capture its live RAM state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

EXPECTED_TOOL_SHA256 = "da14ffa7243767d9c8c5579618171fde2956c4b37b82139bb519932aba6e9375"
FEL_DEVICE = re.compile(r"^USB device\s+(\d+:\d+)\s+Allwinner F1C100s\s*$", re.MULTILINE)
EXPECTED_FLASH = re.compile(r"^Manufacturer: Winbond \(EFh\), model: 40h, size: 16777216 bytes\.$", re.MULTILINE)
ALLOWED_DEVICE_OPERATIONS = ("--list", "spiflash-info")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(tool: Path, *args: str) -> str:
    completed = subprocess.run(
        [str(tool), *args],
        check=False,
        text=True,
        capture_output=True,
        timeout=15,
    )
    if completed.returncode:
        raise RuntimeError(f"sunxi-fel failed ({completed.returncode}): {completed.stderr.strip()}")
    return completed.stdout


def self_test() -> None:
    listing = "USB device 001:048   Allwinner F1C100s \n"
    assert FEL_DEVICE.search(listing).group(1) == "001:048"
    assert EXPECTED_FLASH.search("Manufacturer: Winbond (EFh), model: 40h, size: 16777216 bytes.\n")
    # Device invocation is deliberately limited to this fixed allow-list.
    forbidden = {"spiflash-write", "write", "exec", "boot", "uboot", "spl"}
    assert not (set(ALLOWED_DEVICE_OPERATIONS) & forbidden)
    print(json.dumps({"passed": True, "scope": "offline policy/parser test; no USB call"}))


def probe(tool: Path) -> None:
    actual_hash = file_hash(tool)
    if actual_hash != EXPECTED_TOOL_SHA256:
        raise SystemExit("refusing unpinned sunxi-fel executable")
    listing = run(tool, "--list")
    matches = FEL_DEVICE.findall(listing)
    if len(matches) != 1:
        raise SystemExit("expected exactly one Allwinner F1C100s FEL device")
    flash = run(tool, "-d", matches[0], "spiflash-info")
    if not EXPECTED_FLASH.search(flash):
        raise SystemExit("unexpected SPI flash identification")
    print(json.dumps({
        "fel_device": matches[0],
        "device_line": FEL_DEVICE.search(listing).group(0),
        "flash_info": flash.strip(),
        "tool_sha256": actual_hash,
        "operations": list(ALLOWED_DEVICE_OPERATIONS),
        "scope": "FEL ROM transport and SPI identification only; no flash/RAM write, no RAM code execution, no running-firmware observation.",
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--probe", action="store_true", help="perform only pinned read-only FEL list/info calls")
    parser.add_argument("--tool", type=Path)
    args = parser.parse_args()
    if args.self_test:
        self_test()
        return
    if not args.probe or args.tool is None:
        parser.error("use --self-test or --probe --tool PATH")
    probe(args.tool)


if __name__ == "__main__":
    main()

