# Join the YS-4470 reverse-engineering project

People using any AI tool, or working manually, can contribute across the entire
project: firmware analysis, SoC references, emulation, reconstruction, tests,
hardware observations and documentation. The goal is full understanding and an
independently buildable, functionally equivalent firmware. The 1.0 patch release
is an earlier milestone, not completion of that goal.

## Start from current work

The integration branch is [`re/2026-11-04-pyghidra-fel`](https://github.com/NandorHU/YS4470-Firmware-RE/tree/re/2026-11-04-pyghidra-fel).
`main` currently contains an older project snapshot. Read these files on the
integration branch before choosing work:

1. [AGENTS.md](AGENTS.md): coordinator, branch and evidence rules.
2. [Current handoff](collaboration/CURRENT_HANDOFF.md): proven results and exact continuation.
3. [Task registry](collaboration/TASK_REGISTRY.json): current ownership and bounded tasks.
4. [REVERSE_ENGINEERING_STATUS.md](REVERSE_ENGINEERING_STATUS.md),
   [FUNCTION_DATABASE.json](FUNCTION_DATABASE.json) and the relevant method/evidence.

The original [V3.6/V3.8 images](original-firmware/README.md) are provided with
SHA-256 identities. Public-source tasks also exist for contributors who do not
want to download or execute firmware. The 1.0 Release image is a different input.

## Reserve a task without duplicating someone else's work

The registry on the integration branch is the single source of ownership.
Issue discussion carries requests and progress; it does not silently override it.

1. Read the latest registry directly from the upstream branch, not only your fork.
2. Choose an `available` task, or propose a new bounded task in any relevant subsystem.
3. Open a [GitHub issue](https://github.com/NandorHU/YS4470-Firmware-RE/issues/new) using
   [TASK_REQUEST_TEMPLATE.md](collaboration/TASK_REQUEST_TEMPLATE.md). A request
   identifies the person/agent, proposed scope, branch/fork, baseline and files.
4. The coordinator checks overlap and records one owner as `reserved`, then
   `in_progress`. Begin the reserved analysis once that ownership is published.
   Two simultaneous requests do not create two owners; the later request is
   redirected or the coordinator splits the scopes.
5. Put code, reports and partial progress under `contributions/<TASK-ID>/`.
   Respect exclusions and keep shared databases/status files for coordinator
   integration; propose their changes as a separate delta in your handoff.
6. Keep a short `STATUS.md` there with the last proven result, exact next step,
   latest commit and blockers. On pause, submit this partial handoff so the
   coordinator can release or reassign the task. Silence is not automatic release.

States are `available -> reserved -> in_progress -> review -> completed`;
`blocked` records missing inputs/access. The coordinator publishes transitions
against the latest registry revision without overwriting concurrent updates.
A submitted result is not completed until its evidence is reviewed/integrated.

## Work in a separate branch or fork

No external agent may push, merge, force-update or delete `main`, or advance the
coordinator's integration branch. Forks are the normal route without write access.
After forking on GitHub, a starting checkout can be prepared with:

```text
git clone --branch re/2026-11-04-pyghidra-fel --single-branch https://github.com/NandorHU/YS4470-Firmware-RE.git
cd YS4470-Firmware-RE
git remote rename origin upstream
git remote add origin https://github.com/YOUR-LOGIN/YS4470-Firmware-RE.git
git switch -c external/YOUR-AGENT/TASK-ID
```

Push to your own fork/branch. Open a pull request targeting `re/2026-11-04-pyghidra-fel`,
not `main`. Do not rewrite other people's branches. The coordinator reviews and
integrates accepted commits. GitHub branch permissions are a separate setting;
these documents do not claim to enforce them server-side.

## Minimal local setup

Python 3 is sufficient for documentation and hash checks. For the existing
analysis tests, install only the pinned small dependency set into a local venv:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r tools/analysis-requirements.txt
.venv/Scripts/python -m unittest discover -s tools -p test_reference_pipeline.py -v
```

The baseline has nine tests. Additional task-specific checks belong in the handoff.
The original-byte queue/renderer reproduction is documented in
[REFRESH_SIDE_EFFECTS.md](tools/REFRESH_SIDE_EFFECTS.md); substitute the two paths
under `original-firmware/V3.6` and `V3.8` in its input arguments.
Ghidra/PyGhidra, a JDK, an ARM compiler or reference downloads are needed only for
tasks that use them; see [reference setup](tools/F1C100S_REFERENCE_ANALYSIS.md).
Do not introduce paid external API dependencies into project automation.

## Return reviewable results

Use [HANDOFF_TEMPLATE.md](collaboration/HANDOFF_TEMPLATE.md) and the PR template.
Include the task ID, base/result commits, input hashes, linked addresses and raw
offsets, executed commands, generated evidence, models/stubs, failed checks and
next step. Say whether you actually ran each tool. Attach useful partial results
even if the intended proof failed.

Confidence must reflect evidence: a reference similarity is a candidate; bounded
original-code execution is proof only for the tested scope. Preserve existing
Ghidra names/comments. Do not infer whole-device behavior, physical timing or ADC
identity from a software case number or an emulated peripheral shadow.

Keep personal flash backups, calibration/device dumps, credentials and private
logs out of commits. The two owner-approved factory application images are the
explicit publication exception in [original-firmware/README.md](original-firmware/README.md).
Keep originals unchanged and document third-party provenance under [NOTICE.md](NOTICE.md)
and each reference's license. No repository-wide license is selected by this guide.

The reusable [AI starter prompt](collaboration/AI_STARTER_PROMPT.md) is independent
of the contributor's AI vendor and can be pasted into a fresh session.


Local-model contributors: read [LOCAL_LLM.md](collaboration/LOCAL_LLM.md) for the
actual tested setup, checked examples, failure receipts and current workload
limits. Source-cited drafts require coordinator review just like any other
external contribution.
