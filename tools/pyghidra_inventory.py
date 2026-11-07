"""Bounded PyGhidra inventory for YS-4470 raw ARM firmware images.

The program keeps raw inputs read-only.  It does not run broad auto-analysis by
default because the raw images contain mixed ARM/Thumb context that has produced
false boundaries in this project.  Instead it disassembles evidence-backed
seeds, creates local Ghidra functions, exports assembly/call edges/decompilation,
and marks names by confidence.

Example:
  python pyghidra_inventory.py --input V3.8=C:\\path\\f1c100s.bin \\
      --ghidra C:\\path\\ghidra_12.1.4_PUBLIC --out report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

LINK_BASE = 0x7FFFFFE0
# PyGhidra expects the LanguageID; the compiler spec is selected separately.
# The headless `-processor` spelling additionally contains `:default`.
LANGUAGE = "ARM:LE:32:v5t"

# Roles and confidence are imported from earlier bounded-disassembly evidence.
# Do not promote candidate names to factory symbols without new evidence.
SEEDS = (
    (0x800037C0, "ResultDispatch_entry", "confirmed", "result-dispatch entry; old0x800037bc was literal data"),
    (0x80003A0C, "DiodeValidityBranch", "confirmed", "diode-result validity branch"),
    (0x80004490, "MeasurementFSM", "confirmed", "eight-state reply/command FSM"),
    (0x8000489C, "TransactionBuilder", "confirmed", "measurement transaction state builder"),
    (0x8000553C, "KeyTaskCountdown", "confirmed", "key-task countdown/sound path"),
    (0x80005A78, "MainADCTask_candidate", "hypothesis", "previous task candidate"),
    (0x80005B6C, "GaugeTask_candidate", "hypothesis", "profile hook caller context"),
    (0x80006E4C, "SoundControlGate", "confirmed", "clamps sound selector after enable check"),
    (0x800073BC, "UART_RX_ISR", "confirmed", "measurement-frame UART receive ISR"),
    (0x8000D294, "HighspeedEventHandler", "confirmed", "factory Highspeed event handler"),
    (0x80010754, "Beta3SoundTableHook_candidate", "hypothesis", "Beta3 target reached from SoundControlGate"),
    (0x8005D048, "MeasurementRefreshCallback", "confirmed", "refresh callback;0x8005d1a0 is its ResultDispatch call site"),
    (0x80060130, "Beta3ResultValueHook_candidate", "hypothesis", "Beta3 target reached from ResultDispatch_entry"),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_input(value: str) -> tuple[str, Path]:
    try:
        version, raw_path = value.split("=", 1)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use VERSION=PATH") from exc
    return version, Path(raw_path)


def find_terminal_instruction(flat: Any, start: Any, maximum: int = 160) -> Any:
    """Return an inclusive, bounded function body end without crossing a return."""
    current = start
    last = start
    for _ in range(maximum):
        instruction = flat.getInstructionAt(current)
        if instruction is None:
            break
        last = instruction.getMaxAddress()
        flow = instruction.getFlowType()
        mnemonic = str(instruction.getMnemonicString()).lower()
        if flow.isTerminal() or mnemonic in {"bx", "pop", "ldmia"}:
            break
        current = instruction.getMaxAddress().add(1)
    return last


def instruction_records(program: Any, function: Any) -> tuple[list[dict[str, Any]], list[str]]:
    records: list[dict[str, Any]] = []
    calls: set[str] = set()
    iterator = program.getListing().getInstructions(function.getBody(), True)
    while iterator.hasNext():
        instruction = iterator.next()
        targets: list[str] = []
        for target in instruction.getFlows():
            targets.append(str(target))
            if instruction.getFlowType().isCall():
                calls.add(str(target))
        records.append(
            {
                "address": str(instruction.getAddress()),
                "assembly": str(instruction),
                "flow_targets": targets,
            }
        )
    return records, sorted(calls)


def decompile(program: Any, function: Any, monitor: Any) -> str | None:
    from ghidra.app.decompiler import DecompInterface

    interface = DecompInterface()
    try:
        interface.openProgram(program)
        result = interface.decompileFunction(function, 30, monitor)
        if result is None or not result.decompileCompleted():
            return None
        decompiled = result.getDecompiledFunction()
        return None if decompiled is None else str(decompiled.getC())
    finally:
        interface.dispose()


def inventory(version: str, raw_path: Path, out_dir: Path, ghidra_dir: Path, full_analysis: bool, reference_report: Path | None = None, labels_only: bool = False) -> dict[str, Any]:
    import pyghidra

    raw_bytes = raw_path.read_bytes()
    from reference_ghidra_labels import validated_labels, apply_labels
    approved_labels = validated_labels(reference_report, version, raw_bytes) if reference_report else []
    pyghidra.start(install_dir=ghidra_dir)
    project_root = out_dir / "ghidra-projects"
    project_root.mkdir(parents=True, exist_ok=True)
    project_name = f"ys4470_{version.replace('.', '_').replace('-', '_')}"

    with pyghidra.open_program(
        raw_path,
        project_location=project_root,
        project_name=project_name,
        program_name=raw_path.name,
        analyze=False,
        language=LANGUAGE,
        loader="ghidra.app.util.opinion.BinaryLoader",
    ) as flat:
        program = flat.getCurrentProgram()
        transaction = program.startTransaction("YS-4470 bounded inventory")
        try:
            desired_base = flat.toAddr(LINK_BASE)
            if program.getImageBase() != desired_base:
                program.setImageBase(desired_base, True)

            if full_analysis:
                flat.analyzeAll(program)

            functions = []
            for address, proposed_name, confidence, role in (() if labels_only else SEEDS):
                file_offset = address - LINK_BASE
                fixed_window = raw_bytes[file_offset:file_offset + 64]
                fixed_window_512 = raw_bytes[file_offset:file_offset + 512]
                # JPype otherwise narrows addresses >= 0x80000000 to signed Java int.
                entry = flat.toAddr(f"{address:08x}")
                flat.disassemble(entry)
                function = program.getFunctionManager().getFunctionAt(entry)
                if function is None:
                    # FlatProgramAPI locates a conservative body from decoded instructions.
                    function = flat.createFunction(entry, proposed_name)
                if function is None:
                    functions.append(
                        {
                            "address": f"0x{address:08x}",
                            "proposed_name": proposed_name,
                            "confidence": confidence,
                            "role": role,
                            "status": "not-created",
                            "fixed_window_bytes": len(fixed_window),
                            "fixed_window_sha256": hashlib.sha256(fixed_window).hexdigest(),
                            "fixed_window_512_bytes": len(fixed_window_512),
                            "fixed_window_512_sha256": hashlib.sha256(fixed_window_512).hexdigest(),
                        }
                    )
                    continue
                try:
                    source_type = __import__("ghidra.program.model.symbol", fromlist=["SourceType"]).SourceType
                    # Preserve analyst/imported labels. These seeds are analysis
                    # labels, not recovered vendor symbols.
                    if function.getSymbol().getSource() == source_type.DEFAULT:
                        function.setName(proposed_name, source_type.ANALYSIS)
                except Exception:
                    # Existing Ghidra name is kept; exported proposed_name remains the traceable label.
                    pass
                instructions, calls = instruction_records(program, function)
                asm_text = "\n".join(item["assembly"] for item in instructions)
                functions.append(
                    {
                        "address": f"0x{address:08x}",
                        "proposed_name": proposed_name,
                        "ghidra_name": str(function.getName()),
                        "confidence": confidence,
                        "role": role,
                        "status": "exported",
                        "body_end": str(function.getBody().getMaxAddress()),
                        "instruction_count": len(instructions),
                        "assembly_sha256": hashlib.sha256(asm_text.encode("utf-8")).hexdigest(),
                        "fixed_window_bytes": len(fixed_window),
                        "fixed_window_sha256": hashlib.sha256(fixed_window).hexdigest(),
                        "fixed_window_512_bytes": len(fixed_window_512),
                        "fixed_window_512_sha256": hashlib.sha256(fixed_window_512).hexdigest(),
                        "direct_call_targets": calls,
                        "assembly": instructions,
                        "decompiled_c": decompile(program, function, flat.getMonitor()),
                    }
                )
            reference_labels = apply_labels(program, flat, approved_labels)
            reference_function_exports = []
            for label in reference_labels:
                entry = flat.toAddr(label['address'].removeprefix('0x'))
                function = program.getFunctionManager().getFunctionAt(entry)
                if function is None:
                    continue
                instructions, calls = instruction_records(program, function)
                reference_function_exports.append({
                    'address': label['address'], 'name': str(function.getName()),
                    'label_status': label['status'], 'confidence': label['confidence'],
                    'evidence': label['evidence'], 'comment': function.getComment(),
                    'body_end': str(function.getBody().getMaxAddress()),
                    'assembly': instructions, 'direct_call_targets': calls,
                    'decompiled_c': decompile(program, function, flat.getMonitor()),
                    'limits': ['Ghidra inferred body; original-byte proof applies only to documented execution scope.'],
                })
        finally:
            program.endTransaction(transaction, True)
        # PyGhidra owns an import transaction for this context; reports are the
        # durable export, so do not force a save while that lock is still held.

    return {
        "schema": "ys4470.pyghidra.inventory.v1",
        "version": version,
        "input": {"name": raw_path.name, "bytes": raw_path.stat().st_size, "sha256": sha256(raw_path)},
        "import": {
            "loader": "BinaryLoader",
            "language": LANGUAGE,
            "link_base": f"0x{LINK_BASE:08x}",
            "analysis_mode": "full" if full_analysis else ("proof-labels-only" if labels_only else "bounded-seeded"),
            "seed_revision": "not-used" if labels_only else "2026-11-07-corrected-result-refresh-entries",
            "note": "Seed names are labels with explicit confidence; they are not recovered vendor symbols.",
        },
        "functions": functions,
        "reference_labels": reference_labels,
        "reference_function_exports": reference_function_exports,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", type=parse_input, required=True, metavar="VERSION=PATH")
    parser.add_argument("--ghidra", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--full-analysis", action="store_true")
    parser.add_argument("--reference-report", type=Path, help="Proof-gated reference-analysis.json; preserves existing analyst names")
    parser.add_argument("--labels-only", action="store_true", help="Export proof-labelled entries without repeating the seed inventory")
    args = parser.parse_args()
    if args.labels_only and not args.reference_report:
        parser.error("--labels-only requires --reference-report")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    failures: list[dict[str, str]] = []
    for version, raw_path in args.input:
        if not raw_path.is_file():
            failures.append({"version": version, "path": str(raw_path), "status": "missing-input"})
            continue
        report = inventory(version, raw_path, args.out_dir, args.ghidra, args.full_analysis, args.reference_report, args.labels_only)
        destination = args.out_dir / f"{version.replace('.', '_')}_inventory.json"
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"wrote {destination}")
    if failures:
        print(json.dumps({"missing_inputs": failures}, indent=2))
        raise SystemExit(2)


if __name__ == "__main__":
    main()
