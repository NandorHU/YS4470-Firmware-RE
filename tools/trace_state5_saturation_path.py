"""Trace the bounded state-5 saturation control path in the V3.8 image.

The trace ties writes of control object ``0x805aae8c+0x08`` to the state-5
comparison that may replace a parsed result with ``0x007fffff``.  It records
only direct static evidence and does not execute firmware or use hardware.
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
CONTROL_OBJECT = 0x805AAE8C
RESULT_OBJECT = 0x805AC714
CONTEXTS = {
    "input_command_dispatcher": (0x80004390, 64),
    "task_command_dispatcher": (0x80005B90, 88),
    "state_5_saturation_branch": (0x80004760, 28),
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
    expected = {
        "input_dispatch_control_object_literal": (0x8000448C, CONTROL_OBJECT),
        "input_case_2_compare": (0x800043C8, 0xE3500002),
        "input_case_2_branch": (0x800043D0, 0x0A000023),
        "input_case_2_writes_control_word": (0x80004464, 0xE5831008),
        "input_case_5_writes_constant_0x22": (0x800043E4, 0xE3A01022),
        "input_case_5_stores_control_word": (0x800043E8, 0xE5831008),
        "task_control_object_literal": (0x80005D18, CONTROL_OBJECT),
        "task_case_2_compare": (0x80005C18, 0xE3500002),
        "task_case_2_writes_control_word": (0x80005C58, 0xE5841008),
        "task_case_2_sequence_contains_terminal_0x1d_register": (0x80005C64, 0xE8800026),
        "task_case_5_sets_terminal_0x1d": (0x80005BA4, 0xE3A0501D),
        "task_case_5_sets_control_0x22": (0x80005BAC, 0xE3A08022),
        "task_case_5_stores_control_word": (0x80005C7C, 0xE5848008),
        "state_5_control_object_literal": (0x8000481C, CONTROL_OBJECT),
        "state_5_loads_control_word": (0x80004784, 0xE59C3008),
        "state_5_compares_0x0e": (0x8000478C, 0xE353000E),
        "state_5_compares_0x0d": (0x80004790, 0x1353000D),
        "state_5_threshold_literal": (0x80004824, 0x00001389),
        "state_5_saturation_literal": (0x80004828, 0x007FFFFF),
        "state_5_saturation_store": (0x800047A8, 0xE58C001C),
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
        rows.append({"address": f"0x{address:08x}", "raw_word": f"0x{word:08x}", "assembly": "<not decoded>" if instruction is None else str(instruction)})
    return rows


def collect(image_path: Path, project_root: Path, ghidra_dir: Path) -> dict[str, Any]:
    import pyghidra

    image = image_path.read_bytes()
    pyghidra.start(install_dir=ghidra_dir)
    with pyghidra.open_program(
        image_path,
        project_location=project_root,
        project_name="ys4470_state5_saturation_path",
        program_name=image_path.name,
        analyze=False,
        language=LANGUAGE,
        loader="ghidra.app.util.opinion.BinaryLoader",
    ) as flat:
        program = flat.getCurrentProgram()
        transaction = program.startTransaction("bounded state-5 saturation trace")
        try:
            desired = flat.toAddr(f"{LINK_BASE:08x}")
            if program.getImageBase() != desired:
                program.setImageBase(desired, True)
            contexts = {name: disassembly_window(flat, start, count) for name, (start, count) in CONTEXTS.items()}
        finally:
            program.endTransaction(transaction, True)
    return {
        "schema": "ys4470.state5-saturation-path.v1",
        "method": "bounded direct PC-literal object traces plus fixed PyGhidra windows; no firmware execution or hardware access",
        "input": {"name": image_path.name, "sha256": sha256(image_path)},
        "link_base": f"0x{LINK_BASE:08x}",
        "objects": {
            "control": trace_literal_object(image_path, LINK_BASE, CONTROL_OBJECT, {0x1, 0x8}, 256),
            "result": trace_literal_object(image_path, LINK_BASE, RESULT_OBJECT, {0x1C, 0x20}, 96),
        },
        "static_assertions": static_assertions(image),
        "derived_static_rule": {
            "control_field": "0x805aae8c+0x08",
            "saturation_selector_values": ["0x0d", "0x0e"],
            "threshold": "0x1389 (comparison is unsigned: parsed_value >= threshold)",
            "replacement_value": "0x007fffff",
            "setup_relation": "Both input/task dispatcher case 2 paths store an input-derived r1 to the control field and build a sequence whose last register is r5=0x1d; case 5 instead stores constant 0x22.",
            "limit": "Input fields and dispatcher cases have no physical measurement-mode names in this trace.",
        },
        "contexts": contexts,
    }


def self_test() -> None:
    assert CONTROL_OBJECT == 0x805AAE8C
    assert RESULT_OBJECT == 0x805AC714
    assert CONTEXTS["state_5_saturation_branch"][0] == 0x80004760
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

