"""Audit completed local instruction drafts and export factory-byte-checked indexes."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_MODE_ARM, Cs

BASE = 0x7FFFFFE0
ORIGINALS = {
    "V3.6": "7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9",
    "V3.8": "7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290",
}
FIELDS = {"entry", "instruction_mode", "evidence_address", "quote", "limitation"}
MODEL = "qwen2.5-coder:14b"
LESSONS = "7b135d7b5b1e58e68fa7ba4283902106547b7d76fe9736baacb065a3653217c4"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def check_reply(attempt, entry, address, assembly):
    response = attempt["response"]
    message = response.get("message", {})
    if response.get("done") is not True or response.get("done_reason") != "stop":
        return "incomplete_response"
    if message.get("tool_calls"):
        return "unexpected_tool_call"
    try:
        draft = json.loads(message.get("content", ""))
    except (TypeError, ValueError):
        return "invalid_json"
    if not isinstance(draft, dict) or set(draft) != FIELDS or any(not isinstance(v, str) for v in draft.values()):
        return "invalid_schema"
    if (draft["entry"], draft["instruction_mode"], draft["evidence_address"]) != (entry, "ARM", address):
        return "wrong_identity"
    if draft["quote"] not in (assembly, f"{address} {assembly}"):
        return "non_exact_quote"
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, action="append", default=[])
    args = parser.parse_args()
    state, repo, output = args.state.resolve(), args.repo.resolve(), args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    images = {}
    for item in json.loads((repo / "original-firmware/manifest.json").read_bytes())["images"]:
        image = (repo / item["path"]).resolve()
        if not image.is_relative_to(repo / "original-firmware"):
            raise ValueError(f"Original outside expected directory: {image}")
        raw = image.read_bytes()
        assert len(raw) == item["size_bytes"] and sha(raw) == ORIGINALS[item["version"]]
        images[item["version"]] = raw
    assert images.keys() == ORIGINALS.keys()
    previous = set()
    for snapshot in args.baseline:
        old_count = len(previous)
        baseline = json.loads((snapshot / "review.json").read_bytes())
        assert baseline["firmware_sha256"] == ORIGINALS
        previous.update(row["address"] for row in baseline["excluded"])
        for chunk in baseline["exported_chunks"]:
            data = (snapshot / chunk["path"]).read_bytes()
            assert sha(data) == chunk["sha256"]
            previous.update(line.split("\t", 1)[0] for line in data.decode().splitlines()[1:])
        assert len(previous) - old_count == baseline["reviewed_drafts"]

    arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    seen, accepted, rejected, retry_counts = set(), [], [], Counter()
    catalogs = {}
    for path in sorted((state / "inbox").glob("*.json")):
        data = path.read_bytes()
        catalog = json.loads(data)
        assert catalog["schema"] == "ys4470.local-index-catalog.v1"
        catalogs[path.name] = (sha(data), catalog["instruction_bytes"])
    assert catalogs
    source = {}
    for name, (_, words) in catalogs.items():
        for address, encoded in words.items():
            if address in source:
                assert source[address][1] == encoded
            else:
                source[address] = (name, encoded)

    # Read only completed review markers. The running worker writes them atomically.
    reviews = sorted((state / "jobs").glob("*/index-review.json"))
    reviewed_batches = 0
    for review in reviews:
        job = review.parent
        manifest_bytes = (job / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        assert (manifest["schema"], manifest["model"], manifest["lessons_sha256"]) == (
            "ys4470.packet-worker.v1", MODEL, LESSONS,
        )
        checked = json.loads(review.read_bytes())
        assert checked["checked_firmware_sha256"] == ORIGINALS
        assert len(manifest["tasks"]) == len(checked["results"])
        if any(task["review_expected_address"] not in previous for task in manifest["tasks"]):
            reviewed_batches += 1
        for task, resident in zip(manifest["tasks"], checked["results"]):
            if task["review_expected_address"] in previous:
                continue
            address = task["review_expected_address"]
            assert address == resident["address"] and address not in seen
            seen.add(address)
            path = (state / task["packet"]).resolve()
            assert path.is_relative_to(job)
            packet_bytes = path.read_bytes()
            packet = json.loads(packet_bytes)
            assert sha(packet_bytes) == task["packet_sha256"]
            assert packet["binary"]["sha256"] == ORIGINALS["V3.8"]
            assert packet["instruction_mode"] == "ARM"
            catalog_name, expected_bytes = source[address]
            for line in packet["assembly"]:
                pc = int(line["address"], 16)
                assert pc % 4 == 0 and pc >= BASE
                raw = bytes.fromhex(line["bytes"])
                assert len(raw) == 4
                assert all(image[pc - BASE:pc - BASE + 4] == raw for image in images.values())
                insn, = arm.disasm(raw, pc)
                assert line["assembly"] == f"{insn.mnemonic} {insn.op_str}".strip()
            original, = (line for line in packet["assembly"] if line["address"] == address)
            assert original["bytes"] == resident["original_bytes"] == expected_bytes

            result = json.loads((job / (task["id"] + ".json")).read_bytes())
            assert result["manifest_sha256"] == sha(manifest_bytes)
            assert result["packet_sha256"] == task["packet_sha256"]
            attempts = result["attempts"]
            assert 1 <= len(attempts) <= 2
            retry_counts[len(attempts)] += 1
            reason = check_reply(attempts[-1], packet["entry"], address, original["assembly"])
            if reason is None and (result["state"] != "draft" or not resident["exact"]):
                reason = "resident_gate_rejected"
            if reason:
                rejected.append(dict(address=address, catalog=catalog_name, reason=reason))
            else:
                accepted.append((address, expected_bytes, original["assembly"], catalog_name))
    accepted.sort(key=lambda row: int(row[0], 16))
    rejected.sort(key=lambda row: int(row["address"], 16))
    chunks = []
    for start in range(0, len(accepted), 500):
        path = output / f"accepted-arm-index-{start // 500 + 1:02d}.tsv"
        rows = accepted[start:start + 500]
        data = ("address\tbytes_le\tassembly\tcatalog\n" +
                "".join("\t".join(row) + "\n" for row in rows)).encode()
        path.write_bytes(data)
        chunks.append(dict(path=path.name, rows=len(rows), sha256=sha(data)))
    summary = dict(schema="ys4470.resident-arm-index-review.v1", firmware_sha256=ORIGINALS,
                   model=MODEL, checked_lessons_sha256=LESSONS, reviewed_batches=reviewed_batches,
                   reviewed_drafts=len(seen), exact_extractions=len(accepted),
                   excluded_drafts=len(rejected), attempts_per_draft=dict(sorted(retry_counts.items())),
                   exclusions_by_reason=dict(Counter(row["reason"] for row in rejected)),
                   source_catalogs={name: dict(sha256=digest, addresses=len(words),
                                              exact=sum(row[3] == name for row in accepted),
                                              excluded=sum(row["catalog"] == name for row in rejected))
                                    for name, (digest, words) in catalogs.items()},
                   exported_chunks=chunks, excluded=rejected,
                   scope="Original-byte and exact-quote verification. No model-supplied semantic conclusions are published.")
    write(output / "review.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("source_catalogs", "excluded")}, indent=2))


if __name__ == "__main__":
    main()
