"""Run a resident, review-only Ollama index queue for hash-pinned YS-4470 evidence."""

import argparse
import hashlib
import json
import msvcrt
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from capstone import CS_ARCH_ARM, CS_GRP_CALL, CS_GRP_JUMP, CS_MODE_ARM, Cs

BASE = 0x7FFFFFE0
MODEL = "qwen2.5-coder:14b"
DIGEST = "9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849"
LESSONS = "7b135d7b5b1e58e68fa7ba4283902106547b7d76fe9736baacb065a3653217c4"
ENDPOINT = "http://127.0.0.1:11435"
OWNER = "codex-ys4470-20261109-01a1c110"
SCOPE = "COORD-ADC-CADENCE original instruction index"
ORIGINALS = {
    "V3.6": "7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9",
    "V3.8": "7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_bytes())


def write_json(path, value):
    data = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)
    return digest(data)


def load_images(repo):
    manifest = read_json(repo / "original-firmware/manifest.json")
    images = {}
    for item in manifest["images"]:
        path = (repo / item["path"]).resolve()
        if not path.is_relative_to(repo / "original-firmware"):
            raise ValueError(f"Input outside original-firmware: {path}")
        raw = path.read_bytes()
        if len(raw) != item["size_bytes"] or digest(raw) != ORIGINALS[item["version"]]:
            raise ValueError(f"Factory image mismatch: {item['version']}")
        images[item["version"]] = raw
    if images.keys() != ORIGINALS.keys():
        raise ValueError("Both factory images are required")
    return images


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def model_available():
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(ENDPOINT + "/api/tags", timeout=5) as response:
            return any(x["name"] == MODEL and x["digest"] == DIGEST for x in json.load(response)["models"])
    except (OSError, ValueError, KeyError):
        return False


class ResidentQueue:
    def __init__(self, state, repo):
        self.state, self.repo = state, repo
        self.inbox = state / "inbox"
        self.jobs = state / "jobs"
        for directory in (self.inbox, self.jobs):
            directory.mkdir(parents=True, exist_ok=True)
        self.images = load_images(repo)
        self.arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        self.arm.detail = True
        source = repo / "contributions/COORD-FUNCTION-PACKETS"
        wrapper = state / "contributions/COORD-FUNCTION-PACKETS"
        wrapper.mkdir(parents=True, exist_ok=True)
        for name in ("LESSONS.md", "completion_gate.py", "packet_worker.py"):
            data = (source / name).read_bytes()
            if name == "LESSONS.md" and digest(data) != LESSONS:
                raise ValueError("Checked lessons hash mismatch")
            (wrapper / name).write_bytes(data)
        self.worker = wrapper / "packet_worker.py"
        self.earlier = set()
        for pattern in ("ys4470-*/owned-job/manifest.json", "local-job-*/manifest.json"):
            for manifest in state.parent.glob(pattern):
                for task in read_json(manifest).get("tasks", ()):
                    if task.get("review_expected_address"):
                        self.earlier.add(int(task["review_expected_address"], 16))

    def catalog(self):
        catalog = {}
        for path in sorted(self.inbox.glob("*.json")):
            item = read_json(path)
            if item["schema"] != "ys4470.local-index-catalog.v1":
                raise ValueError(f"Unsupported catalog: {path.name}")
            for address, encoded in item["instruction_bytes"].items():
                pc, data = int(address, 16), bytes.fromhex(encoded)
                offset = pc - BASE
                if pc % 4 or len(data) != 4 or offset < 0:
                    raise ValueError(f"Invalid ARM word: {address}")
                if any(raw[offset:offset + 4] != data for raw in self.images.values()):
                    raise ValueError(f"Factory bytes mismatch at {address}")
                insns = list(self.arm.disasm(data, pc))
                if insns:
                    inst, = insns
                    assembly = f"{inst.mnemonic} {inst.op_str}".strip()
                    priority = 0 if inst.group(CS_GRP_CALL) else 1 if inst.group(CS_GRP_JUMP) else 2
                    catalog[pc] = (data.hex(), assembly, priority)
        return catalog

    def make_job(self, targets, catalog):
        name = "-".join(f"{pc:08x}" for pc in targets)
        job = self.jobs / name
        job.mkdir(exist_ok=True)
        tasks = []
        for pc in targets:
            neighbors = [a for a in range(pc - 8, pc + 12, 4) if a in catalog]
            lines = [dict(address=hex(a), bytes=catalog[a][0], assembly=catalog[a][1]) for a in neighbors]
            entry = lines[0]["address"]
            tid = f"index-{pc:08x}"
            packet = dict(binary={"version": "V3.8", "sha256": ORIGINALS["V3.8"]},
                          entry=entry, instruction_mode="ARM", assembly=lines,
                          limits=["Address index only. A finite window does not prove runtime reachability or timing."],
                          name="Verified original ARM address window", name_evidence_status="window only",
                          decompiled_c="", direct_callees=[], literal_refs=[])
            packet_path = job / f"{tid}-packet.json"
            packet_sha = write_json(packet_path, packet)
            tasks.append(dict(id=tid, context="full_packet", packet=packet_path.relative_to(self.state).as_posix(),
                              packet_sha256=packet_sha, binary_sha256=ORIGINALS["V3.8"],
                              review_expected_address=hex(pc),
                              question=f"Find and quote the original instruction at {pc:#x}. "
                                       f"The packet entry is {entry}. Use the exact assembly text. "
                                       "State one limit of the local evidence."))
        write_json(job / "manifest.json", dict(schema="ys4470.packet-worker.v1", endpoint=ENDPOINT, model=MODEL,
                                                 lessons_sha256=LESSONS, owner=OWNER, scope=SCOPE, tasks=tasks))
        return job

    def check_drafts(self, job, catalog):
        receipts = []
        for task in read_json(job / "manifest.json")["tasks"]:
            pc = int(task["review_expected_address"], 16)
            result = read_json(job / (task["id"] + ".json"))
            attempt = result["attempts"][-1]
            draft = attempt["gate"]["parsed"]
            exact = result["state"] == "draft" and draft["evidence_address"] == hex(pc) and draft["quote"] in (
                catalog[pc][1], f"{pc:#x} {catalog[pc][1]}",
            )
            receipts.append(dict(address=hex(pc), original_bytes=catalog[pc][0], draft=draft, exact=exact,
                                 finish=attempt["response"].get("done_reason"), attempts=len(result["attempts"])))
        write_json(job / "index-review.json", dict(checked_firmware_sha256=ORIGINALS, results=receipts,
                                                    semantic_review="pending coordinator review"))

    def state_record(self, status, pending, completed, **fields):
        write_json(self.state / "status.json",
                   dict(state=status, pid=os.getpid(), updated_utc=datetime.now(timezone.utc).isoformat(),
                        pending_instructions=pending, completed_batches=completed, **fields))

    def run(self):
        while not (self.state / "stop.request").exists():
            catalog = self.catalog()
            frozen = sorted(self.jobs.glob("*/manifest.json"))
            used = self.earlier | {
                int(task["review_expected_address"], 16)
                for manifest in frozen for task in read_json(manifest)["tasks"]
            }
            pending = sorted(catalog.keys() - used, key=lambda pc: (catalog[pc][2], pc))
            complete = sum((p.parent / "index-review.json").exists() for p in frozen)
            unresolved = [p.parent for p in frozen if not (p.parent / "index-review.json").exists()]
            runnable = [job for job in unresolved if not (job / "running.lock").exists()
                        and not (job / "failure.json").exists()]
            if not runnable and not pending:
                self.state_record("idle", 0, complete, unresolved=[p.name for p in unresolved])
                time.sleep(15)
                continue
            if not model_available():
                self.state_record("waiting_for_pinned_ollama", len(pending), complete)
                time.sleep(15)
                continue
            job = runnable[0] if runnable else self.make_job(pending[:2], catalog)
            self.state_record("running", len(pending), complete, active_job=job.name)
            try:
                completed = subprocess.run(
                    [sys.executable, "-B", str(self.worker), "--job", str(job)],
                    cwd=self.repo, capture_output=True, text=True, timeout=180, check=True,
                )
                self.check_drafts(job, catalog)
                print(f"{job.name} {completed.stdout.strip()}", flush=True)
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, IndexError) as error:
                write_json(job / "failure.json", {"type": type(error).__name__, "message": str(error)})
                print(f"{job.name} failed: {error}", flush=True)
                time.sleep(5)
        self.state_record("stopped", 0, len(list(self.jobs.glob("*/index-review.json"))))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    state = args.state.resolve()
    state.mkdir(parents=True, exist_ok=True)
    with (state / "resident.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"\0")
            lock.flush()
        lock.seek(0)
        try:
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise SystemExit("An Ollama index queue already holds the resident lock.") from None
        queue = ResidentQueue(state, args.repo.resolve())
        try:
            queue.run()
        except (OSError, ValueError, KeyError) as error:
            queue.state_record("failed", 0, len(list(queue.jobs.glob("*/index-review.json"))),
                               error=f"{type(error).__name__}: {error}")
            raise


if __name__ == "__main__":
    main()
