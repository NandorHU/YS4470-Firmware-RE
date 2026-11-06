"""Collect bounded static evidence for consumers of the FSM result object.

This helper does not execute the raw image.  It scans direct PC-literal loads
of the result object and records selected PyGhidra ARMv5T windows around the
state-5 writer and early consumer candidates.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Any

from trace_arm_literal_object import analyze as trace_literal_object


LINK_BASE = 0x7FFFFFE0
LANGUAGE = "ARM:LE:32:v5t"
RESULT_OBJECT = 0x805AC714
CONTEXTS = {
    "result_dispatch": (0x800037B0, 104),
    "state_5_result_write": (0x80004760, 40),
    "sound_control_gate": (0x80006E40, 132),
    "ui_result_consumer_candidate": (0x80045240, 88),
    "highspeed_result_control": (0x8005DC20, 136),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def word_at(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - LINK_BASE)[0]


def static_assertions(image: bytes) -> dict[str, bool]:
    """Bind the reported result-field flow to exact raw ARM words/literals."""
    expected = {
        "state_5_result_object_literal": (0x80004820, RESULT_OBJECT),
        "state_5_special_result_store": (0x800047A8, 0xE58C001C),
        "state_5_special_selector_store": (0x800047AC, 0xE58C7020),
        "state_5_normal_result_store": (0x800047B4, 0xE58C001C),
        "state_5_normal_selector_store": (0x800047B8, 0xE58C1020),
        "result_dispatch_result_object_literal": (0x80003AD0, RESULT_OBJECT),
        "result_dispatch_reads_selector": (0x800037E0, 0xE5971020),
        "result_dispatch_reads_value": (0x800037FC, 0xE597001C),
        "result_dispatch_uses_saturation_sentinel": (0x80003AD8, 0x007FFFFF),
        "result_dispatch_calls_sound_gate": (0x80003854, 0xEB000D7C),
        "text_path_result_object_literal": (0x800453B0, RESULT_OBJECT),
        "text_path_reads_selector_byte": (0x8004526C, 0xE5DC2020),
        "text_path_reads_value": (0x800452E0, 0xE59C001C),
        "highspeed_path_result_object_literal": (0x8005DEFC, RESULT_OBJECT),
        "highspeed_path_reads_selector": (0x8005DC44, 0xE5980020),
        "highspeed_path_reads_value": (0x8005DC78, 0xE598001C),
    }
    return {name: word_at(image, address) == value for name, (address, value) in expected.items()}


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
        rows.append({
            "address": f"0x{address:08x}",
            "raw_word": f"0x{word:08x}",
            "assembly": "<not decoded>" if instruction is None else str(instruction),
        })
    return rows


def collect(image_path: Path, project_root: Path, ghidra_dir: Path) -> dict[str, Any]:
    import pyghidra

    pyghidra.start(install_dir=ghidra_dir)
    with pyghidra.open_program(
        image_path,
        project_location=project_root,
        project_name="ys4470_measurement_result_flow",
        program_name=image_path.name,
        analyze=False,
        language=LANGUAGE,
        loader="ghidra.app.util.opinion.BinaryLoader",
    ) as flat:
        program = flat.getCurrentProgram()
        transaction = program.startTransaction("bounded result flow trace")
        try:
            desired = flat.toAddr(f"{LINK_BASE:08x}")
            if program.getImageBase() != desired:
                program.setImageBase(desired, True)
            contexts = {name: disassembly_window(flat, start, count) for name, (start, count) in CONTEXTS.items()}
        finally:
            program.endTransaction(transaction, True)
    return {
        "schema": "ys4470.measurement-result-flow.v1",
        "method": "bounded ARM PC-literal object trace and fixed PyGhidra disassembly windows; no firmware execution or device access",
        "input": {"name": image_path.name, "sha256": sha256(image_path)},
        "link_base": f"0x{LINK_BASE:08x}",
        "result_object": f"0x{RESULT_OBJECT:08x}",
        "direct_access_trace": trace_literal_object(image_path, LINK_BASE, RESULT_OBJECT, {0x1C, 0x20}, 256),
        "static_assertions": static_assertions(image_path.read_bytes()),
        "derived_static_flow": {
            "state_5_fields": {"value": "+0x1c", "selector": "+0x20"},
            "saturation_value": "0x007fffff for the special state-5 threshold path",
            "consumers": [
                "ResultDispatch 0x800037c0 reads value and selector; its saturation branch calls SoundControlGate 0x80006e4c",
                "text-preparation candidate 0x80045264 reads selector and conditionally value",
                "highspeed formatting candidate 0x8005dc3c reads value and selector",
            ],
            "limit": "Formatting/drawing callees and physical measurement names are not asserted by this bounded trace.",
        },
        "contexts": contexts,
    }


def self_test() -> None:
    assert RESULT_OBJECT == 0x805AC714
    assert CONTEXTS["state_5_result_write"][0] == 0x80004760
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
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()

