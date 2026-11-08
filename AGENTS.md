# YS-4470 agent coordination

These instructions apply to the entire repository.

## Coordinator

- The current Codex agent in the ongoing YS-4470 project conversation is the primary coordinator.
- The coordinator selects bounded tasks, tracks dependencies, reviews evidence and tests, and integrates accepted changes on a development branch.
- External agents return their work to the coordinator for review; they do not integrate their own work into the coordinator's shared branch.

## External agent isolation

- Each external agent must work on its own development branch or in its own fork. Use a distinct branch such as `external/<agent>/<topic>` and an isolated checkout when working concurrently.
- External agents must not modify, push to, merge into, force-update, or delete `main` in the project repository. Treat it as read-only.
- All development, including coordinator work, stays off `main`, as required by the existing project instructions.
- External agents must not rewrite another contributor's branch or overwrite unrelated work.
- Submit a branch or fork URL, the base and result commit SHAs, changed paths, reproducible validation commands and results, and any remaining hypotheses or limitations. A pull request may be used as the handoff.
- The coordinator reviews the diff and evidence, runs relevant validation, and integrates accepted commits into the development branch. An external result is not established evidence merely because it was submitted.

## Firmware evidence and preservation

- Preserve original firmware and its SHA-256 identities. The owner explicitly authorized publication of the two SHA-256-pinned original V3.6/V3.8 application images on 2026-11-07; see original-firmware/manifest.json. Do not upload any other private firmware, personal full-flash backups, calibration/device dumps or credentials as part of a handoff.
- Support technical claims with firmware version, binary address, code or artifact references, and actual test results. Mark unproven function names and roles as hypotheses.
- Follow the project's existing physical-device restrictions; this coordination policy does not grant permission to flash firmware or execute unreviewed device code.

Coordination policy recorded from the project owner's instruction on 2026-11-07.

## Shared task ownership and onboarding

- Read CONTRIBUTING.md, collaboration/CURRENT_HANDOFF.md and the live upstream collaboration/TASK_REGISTRY.json before selecting work. Any relevant subsystem may be proposed; contributors may use any AI tool or work manually.
- The registry on `re/2026-11-04-pyghidra-fel` is the ownership authority. Issue requests and fork/local copies do not assign tasks. The coordinator records one owner and publishes status changes against the latest branch head; do not overwrite concurrent registry updates.
- External contributors request a bounded scope using collaboration/TASK_REQUEST_TEMPLATE.md. Work starts after the coordinator publishes ownership. COORD-FSM-TIMEOUT is reserved; do not duplicate it.
- Use contributions/<TASK-ID>/ for isolated code, evidence and STATUS.md. Keep central databases/status documents coordinator-owned; return proposed deltas with collaboration/HANDOFF_TEMPLATE.md.
- At each coordinator session, read current registry and open GitHub issues/PRs before assigning or integrating work. A claim remains pending until explicitly recorded. Review/integrate on the development branch; never infer task release from silence.
- Reuse completed experiments and preserve their limits. Follow the input manifest; the original images and modified Release inputs are not interchangeable.


## Local model work policy

- Read collaboration/LOCAL_LLM.md before starting local batches. The helper code and raw drafts live on the separate external branch snapshot linked there.
- The primary coordinator continues binary execution and integration. Give local models only a small owned extraction/index/draft task; exact arithmetic, hashes, quotations and line locations belong to deterministic tools.
- Apply the checked lesson wrapper for new local requests. This is in-context preparation, not a trained weight adapter. Never reuse a completed job or automatically expand batches before accuracy and review time justify it.
- A valid JSON response or matching source quote does not establish a semantic finding. Treat token-limit replies as incomplete and keep unsupported claims out of shared databases.
