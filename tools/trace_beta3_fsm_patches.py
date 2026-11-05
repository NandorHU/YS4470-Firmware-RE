"""Trace selected Beta3 changes in the ARM measurement FSM.

The report deliberately records raw ARM words alongside Ghidra's disassembly.
This prevents a recovered function boundary from becoming evidence by itself.
It has no device or firmware-write operations.
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
PATCH_SITES = (0x800045E0, 0x8000461C, 0x80004738)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def word_at(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - LINK_BASE)[0]


def arm_bl_target(address: int, word: int) -> int | None:
    # ARM B/BL immediate encoding.  This intentionally rejects non-branches.
    if ((word >> 25) & 0x7) != 0x5:
        return None
    immediate = word & 0x00FFFFFF
    if immediate & 0x00800000:
        immediate -= 0x01000000
    return (address + 8 + (immediate << 2)) & 0xFFFFFFFF


def disassembly_window(flat: Any, address: int, instruction_count: int) -> list[dict[str, str]]:
    """Decode a fixed sequence of ARM addresses without following control flow."""
    listing = flat.getCurrentProgram().getListing()
    output: list[dict[str, str]] = []
    for index in range(instruction_count):
        current_address = address + index * 4
        current = flat.toAddr(f"{current_address:08x}")
        flat.disassemble(current)
        instruction = listing.getInstructionAt(current)
        raw = flat.getCurrentProgram().getMemory().getInt(current) & 0xFFFFFFFF
        if instruction is None:
            output.append({"address": str(current), "raw_word": f"0x{raw:08x}", "assembly": "<not decoded>"})
            continue
        output.append({"address": str(current), "raw_word": f"0x{raw:08x}", "assembly": str(instruction)})
    return output


def collect_windows(image_path: Path, project_root: Path, ghidra_dir: Path) -> dict[str, Any]:
    import pyghidra

    image = image_path.read_bytes()
    pyghidra.start(install_dir=ghidra_dir)
    with pyghidra.open_program(
        image_path,
        project_location=project_root,
        project_name="ys4470_beta3_fsm_patch_trace",
        program_name=image_path.name,
        analyze=False,
        language=LANGUAGE,
        loader="ghidra.app.util.opinion.BinaryLoader",
    ) as flat:
        program = flat.getCurrentProgram()
        transaction = program.startTransaction("bounded patch-site trace")
        try:
            desired = flat.toAddr(f"{LINK_BASE:08x}")
            if program.getImageBase() != desired:
                program.setImageBase(desired, True)
            items: dict[str, Any] = {}
            for site in PATCH_SITES:
                word = word_at(image, site)
                target = arm_bl_target(site, word)
                items[f"0x{site:08x}"] = {
                    "raw_word": f"0x{word:08x}",
                    "branch_target": None if target is None else f"0x{target:08x}",
                    "site_window": disassembly_window(flat, site - 16, 12),
                    "target_window": [] if target is None else disassembly_window(flat, target, 24),
                }
            contexts = {
                "fsm_timeout_setup": disassembly_window(flat, 0x800045F0, 34),
                "transaction_builder_and_following": disassembly_window(flat, 0x8000482C, 84),
                "measurement_fsm_task": disassembly_window(flat, 0x80005B70, 88),
                "measurement_fsm_caller_pre": disassembly_window(flat, 0x80005C60, 48),
                "measurement_fsm_caller": disassembly_window(flat, 0x80005D00, 40),
                "profile_control_setup": disassembly_window(flat, 0x8000CFE8, 58),
                "profile_control_writer_a": disassembly_window(flat, 0x8000CE7C, 58),
                "highspeed_event_handler": disassembly_window(flat, 0x8000D294, 76),
                "profile_control_writer_b": disassembly_window(flat, 0x8000D53C, 58),
            }
        finally:
            program.endTransaction(transaction, True)
    return {"sha256": sha256(image_path), "sites": items, "contexts": contexts}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v38", type=Path, required=True)
    parser.add_argument("--beta3", type=Path, required=True)
    parser.add_argument("--ghidra", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    project_root = args.out.parent / "ghidra-projects"
    left = collect_windows(args.v38, project_root / "v38", args.ghidra)
    right = collect_windows(args.beta3, project_root / "beta3", args.ghidra)
    deltas = []
    for site in PATCH_SITES:
        key = f"0x{site:08x}"
        deltas.append({
            "address": key,
            "v38_raw_word": left["sites"][key]["raw_word"],
            "beta3_raw_word": right["sites"][key]["raw_word"],
            "v38_branch_target": left["sites"][key]["branch_target"],
            "beta3_branch_target": right["sites"][key]["branch_target"],
        })
    args.out.write_text(json.dumps({
        "schema": "ys4470.beta3-fsm-patch-trace.v1",
        "method": "bounded raw-word and PyGhidra disassembly windows; no broad auto-analysis",
        "link_base": f"0x{LINK_BASE:08x}",
        "v38": left,
        "beta3": right,
        "deltas": deltas,
    }, indent=2), encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

