"""Compare bounded PyGhidra exports by evidence-labelled function, not raw address."""
from __future__ import annotations

import argparse
import itertools
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("schema") != "ys4470.pyghidra.inventory.v1":
        raise SystemExit(f"unsupported inventory schema: {path}")
    return report


def validate_provenance(reports: list[dict[str, Any]]) -> None:
    versions = [r['version'] for r in reports]
    if len(versions) != len(set(versions)):
        raise ValueError('duplicate version labels; no input may be silently overwritten')
    revisions = {r['import'].get('seed_revision', 'legacy-unversioned') for r in reports}
    modes = {r['import']['analysis_mode'] for r in reports}
    if len(revisions) != 1 or len(modes) != 1:
        raise ValueError('incompatible seed revisions/analysis modes; re-export with matching provenance before inferring firmware changes')


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", action="append", type=Path, required=True)
    parser.add_argument("--expected-version", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    reports = [load(path) for path in args.report]
    try:
        validate_provenance(reports)
    except ValueError as exc:
        parser.error(str(exc))
    by_version = {report["version"]: report for report in reports}
    names = sorted({fn["proposed_name"] for report in reports for fn in report["functions"]})
    rows = []
    for name in names:
        entries = []
        fingerprints: dict[str, list[str]] = defaultdict(list)
        windows: dict[str, list[str]] = defaultdict(list)
        for version, report in by_version.items():
            fn = next((candidate for candidate in report["functions"] if candidate["proposed_name"] == name), None)
            if fn is None:
                entries.append({"version": version, "status": "not-exported"})
                continue
            fingerprint = fn.get("assembly_sha256")
            entries.append(
                {
                    "version": version,
                    "address": fn.get("address"),
                    "status": fn.get("status"),
                    "instruction_count": fn.get("instruction_count"),
                    "assembly_sha256": fingerprint,
                    "fixed_window_sha256": fn.get("fixed_window_sha256"),
                    "fixed_window_512_sha256": fn.get("fixed_window_512_sha256"),
                    "direct_call_targets": fn.get("direct_call_targets", []),
                }
            )
            if fingerprint:
                fingerprints[fingerprint].append(version)
            if fn.get("fixed_window_sha256"):
                windows[fn["fixed_window_sha256"]].append(version)
        changed = len(fingerprints) > 1
        window_changed = len(windows) > 1
        rows.append(
            {
                "function": name,
                "classification": "changed-or-boundary-different" if changed else "identical-in-exported-body",
                "fixed_window_classification": "changed-in-first-64-bytes" if window_changed else "identical-first-64-bytes",
                "fingerprint_groups": [{"assembly_sha256": digest, "versions": versions} for digest, versions in fingerprints.items()],
                "fixed_window_groups": [{"sha256": digest, "versions": versions} for digest, versions in windows.items()],
                "versions": entries,
            }
        )

    present = sorted(by_version)
    expected = sorted(set(args.expected_version))
    output = {
        "schema": "ys4470.pyghidra.function-compare.v1",
        "comparison_method": "Functions are paired by explicit evidence-labelled proposed_name; raw address equality is not required.",
        "present_versions": present,
        "missing_expected_versions": [version for version in expected if version not in by_version],
        "inputs": {
            report["version"]: {
                "bytes": report["input"]["bytes"],
                "sha256": report["input"]["sha256"],
                "link_base": report["import"]["link_base"],
                "analysis_mode": report["import"]["analysis_mode"],
                "seed_revision": report["import"].get("seed_revision", "legacy-unversioned"),
            }
            for report in reports
        },
        "functions": rows,
        "pairwise_exported_body": {
            f"{left}__{right}": {
                "identical": sorted(
                    row["function"] for row in rows
                    if all(
                        next((item.get("assembly_sha256") for item in row["versions"] if item["version"] == version), None)
                        == next((item.get("assembly_sha256") for item in row["versions"] if item["version"] == left), None)
                        for version in (left, right)
                    )
                ),
                "different_or_missing": sorted(
                    row["function"] for row in rows
                    if next((item.get("assembly_sha256") for item in row["versions"] if item["version"] == left), None)
                    != next((item.get("assembly_sha256") for item in row["versions"] if item["version"] == right), None)
                ),
            }
            for left, right in itertools.combinations(present, 2)
        },
        "pairwise_first_64": {
            f"{left}__{right}": {
                "identical": sorted(
                    row["function"] for row in rows
                    if all(
                        next((item.get("fixed_window_sha256") for item in row["versions"] if item["version"] == version), None)
                        == next((item.get("fixed_window_sha256") for item in row["versions"] if item["version"] == left), None)
                        for version in (left, right)
                    )
                ),
                "different": sorted(
                    row["function"] for row in rows
                    if next((item.get("fixed_window_sha256") for item in row["versions"] if item["version"] == left), None)
                    != next((item.get("fixed_window_sha256") for item in row["versions"] if item["version"] == right), None)
                ),
            }
            for left, right in itertools.combinations(present, 2)
        },
        "pairwise_first_512": {
            f"{left}__{right}": {
                "identical": sorted(
                    row["function"] for row in rows
                    if all(
                        next((item.get("fixed_window_512_sha256") for item in row["versions"] if item["version"] == version), None)
                        == next((item.get("fixed_window_512_sha256") for item in row["versions"] if item["version"] == left), None)
                        for version in (left, right)
                    )
                ),
                "different_or_missing": sorted(
                    row["function"] for row in rows
                    if next((item.get("fixed_window_512_sha256") for item in row["versions"] if item["version"] == left), None)
                    != next((item.get("fixed_window_512_sha256") for item in row["versions"] if item["version"] == right), None)
                ),
            }
            for left, right in itertools.combinations(present, 2)
        },
        "limits": [
            "Only bounded seeded bodies are compared in this first pass.",
            "A different fingerprint can be a real change or a changed function boundary; inspect assembly before semantic claims.",
            "Only versions present in inputs have comparison evidence; absent versions cannot be inferred.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, indent=2), encoding="utf-8")
    changed = sum(row["classification"] != "identical-in-exported-body" for row in rows)
    print(f"wrote {args.out}; {len(rows) - changed} identical, {changed} changed/boundary-different")


if __name__ == "__main__":
    main()
