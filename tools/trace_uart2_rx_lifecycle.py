"""Collect bounded, reproducible evidence for the UART2 RX buffer lifecycle.

The YS-4470 image is raw ARM code linked at ``0x7fffffe0``.  This helper
combines the deliberately limited PC-literal object tracing used elsewhere in
this repository with PyGhidra disassembly windows at every known producer and
consumer.  It does not execute firmware or access hardware.
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
RX_COUNT = 0x805AB938
RX_BUFFER = 0x805B408C

# The addresses below are evidence anchors, not asserted Ghidra function
# boundaries.  Their names describe why the fixed window is collected.
CONTEXTS = {
    "startup_handshake_count_writer": (0x80003DF0, 116),
    "rx_count_reset_and_buffer_consumer": (0x80003F00, 48),
    "measurement_fsm_entry_through_state_5": (0x80004480, 240),
    "synchronous_command_send_and_response_wait": (0x80005EF0, 160),
    "uart2_rx_isr": (0x800073BC, 40),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def arm_branch_target(address: int, word: int) -> int | None:
    """Decode an ARM B/BL immediate, without treating it as a call."""
    if ((word >> 25) & 0x7) != 0x5:
        return None
    displacement = word & 0x00FFFFFF
    if displacement & 0x00800000:
        displacement -= 0x01000000
    return (address + 8 + (displacement << 2)) & 0xFFFFFFFF


def word_at(image: bytes, address: int) -> int:
    return struct.unpack_from("<I", image, address - LINK_BASE)[0]


def static_assertions(image: bytes) -> dict[str, bool]:
    """Pin the small instruction sequence behind the reported frame rule."""
    expected_words = {
        # r7 is zero at MeasurementFSM entry; state 1 stores it through r10,
        # whose literal is the RX-count object.
        "fsm_entry_initializes_zero_register": (0x800044C0, 0xE3A07000),
        "fsm_state_1_clears_rx_count": (0x80004558, 0xE58A7000),
        # A separate startup/handshake path carries r6=0 to two RX-count
        # stores after loading the count object's literal into r4.
        "startup_path_initializes_zero_register": (0x80003E00, 0xE3A06000),
        "startup_path_first_clears_rx_count": (0x80003F24, 0xE5846000),
        "startup_path_second_clears_rx_count": (0x80003F44, 0xE5846000),
        # Commands 0x1b/0x1d select state 3 with a five-byte requirement.
        "special_command_sets_minimum_count_to_5": (0x80004614, 0xE3A00005),
        "special_command_stores_minimum_count": (0x80004618, 0xE5890028),
        "special_command_selects_state_3": (0x80004624, 0xE3A00003),
        "state_3_loads_required_count": (0x800046DC, 0xE5992028),
        "state_3_loads_rx_count": (0x800046E0, 0xE59AC000),
        "state_3_compares_required_and_received_counts": (0x800046E4, 0xE152000C),
        "state_3_branches_when_count_is_short": (0x800046E8, 0xCA00000C),
        "command_0x1d_requires_header_0x60": (0x80004700, 0xE3530060),
        "command_0x1b_requires_header_0x5e": (0x8000470C, 0xE353005E),
        "state_3_selects_state_5": (0x80004714, 0xE3A00005),
        "state_3_stores_state_byte": (0x80004718, 0xE5C90000),
        # State 5 consumes bytes 1, 2, and 3; the ORR sequence builds LE24.
        "state_5_reads_byte_1": (0x80004738, 0xE5DC4001),
        "state_5_reads_byte_2": (0x8000473C, 0xE5DC3002),
        "state_5_reads_byte_3": (0x80004740, 0xE5DC0003),
        "state_5_combines_low_16_bits": (0x80004744, 0xE1843403),
        "state_5_combines_high_8_bits": (0x80004748, 0xE1830800),
        # The synchronous command helper independently clears the same count
        # before it transmits its command descriptor.
        "synchronous_helper_clears_count_value": (0x80005F2C, 0xE3A00000),
        "synchronous_helper_stores_zero_to_rx_count": (0x80005F30, 0xE58A0000),
        # RX ISR uses the current count as buffer offset, then increments it.
        "rx_isr_uses_count_as_buffer_offset": (0x80007400, 0xE0833000),
        "rx_isr_increments_rx_count": (0x80007404, 0xE2800001),
        "rx_isr_stores_incremented_count": (0x80007408, 0xE5820000),
    }
    return {name: word_at(image, address) == expected for name, (address, expected) in expected_words.items()}


def disassembly_window(flat: Any, start: int, instruction_count: int) -> list[dict[str, Any]]:
    listing = flat.getCurrentProgram().getListing()
    memory = flat.getCurrentProgram().getMemory()
    rows: list[dict[str, Any]] = []
    for index in range(instruction_count):
        address = start + index * 4
        ghidra_address = flat.toAddr(f"{address:08x}")
        flat.disassemble(ghidra_address)
        instruction = listing.getInstructionAt(ghidra_address)
        word = memory.getInt(ghidra_address) & 0xFFFFFFFF
        target = arm_branch_target(address, word)
        row: dict[str, Any] = {
            "address": f"0x{address:08x}",
            "raw_word": f"0x{word:08x}",
            "assembly": "<not decoded>" if instruction is None else str(instruction),
        }
        if target is not None:
            row["arm_branch_target"] = f"0x{target:08x}"
        rows.append(row)
    return rows


def collect(image_path: Path, project_root: Path, ghidra_dir: Path) -> dict[str, Any]:
    import pyghidra

    image = image_path.read_bytes()
    pyghidra.start(install_dir=ghidra_dir)
    with pyghidra.open_program(
        image_path,
        project_location=project_root,
        project_name="ys4470_uart2_rx_lifecycle",
        program_name=image_path.name,
        analyze=False,
        language=LANGUAGE,
        loader="ghidra.app.util.opinion.BinaryLoader",
    ) as flat:
        program = flat.getCurrentProgram()
        transaction = program.startTransaction("bounded UART2 RX lifecycle trace")
        try:
            desired = flat.toAddr(f"{LINK_BASE:08x}")
            if program.getImageBase() != desired:
                program.setImageBase(desired, True)
            contexts = {
                label: disassembly_window(flat, start, count)
                for label, (start, count) in CONTEXTS.items()
            }
        finally:
            program.endTransaction(transaction, True)
    return {
        "schema": "ys4470.uart2-rx-lifecycle-trace.v1",
        "method": (
            "raw ARM PC-literal object scan plus fixed PyGhidra disassembly "
            "windows; incomplete by design and contains no hardware access"
        ),
        "input": {"name": image_path.name, "bytes": len(image), "sha256": sha256(image_path)},
        "link_base": f"0x{LINK_BASE:08x}",
        "objects": {
            "rx_count": trace_literal_object(image_path, LINK_BASE, RX_COUNT, {0}, 256),
            "rx_buffer": trace_literal_object(image_path, LINK_BASE, RX_BUFFER, {0}, 256),
        },
        "static_assertions": static_assertions(image),
        "derived_static_rule": {
            "scope": "MeasurementFSM command identifiers 0x1b and 0x1d only",
            "rx_count_requirement": "at least 5 bytes",
            "command_0x1b_header": "0x5e at RX buffer byte 0",
            "command_0x1d_header": "0x60 at RX buffer byte 0",
            "transition": "only after the applicable count and header checks does state 3 store state 5",
            "state_5_value_bytes": "RX buffer bytes 1..3 are combined little-endian into a signed 24-bit value",
            "limit": "This establishes a parser-entry rule, not a general UART frame-boundary protocol.",
        },
        "rx_count_lifecycle_scope": {
            "direct_reset_anchors": ["0x80003f24", "0x80003f44", "0x80004558", "0x80005f30"],
            "increment_anchor": "0x80007404",
            "limit": "These are bounded direct PC-literal access paths, not an interprocedural proof that no other aliasing writer exists.",
        },
        "contexts": contexts,
    }


def self_test() -> None:
    assert arm_branch_target(0x80000000, 0xEA000001) == 0x8000000C
    assert arm_branch_target(0x80000000, 0xE3A00000) is None
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

