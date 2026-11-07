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

- Preserve original firmware and its SHA-256 identities. Do not upload private firmware or device backups as part of a handoff.
- Support technical claims with firmware version, binary address, code or artifact references, and actual test results. Mark unproven function names and roles as hypotheses.
- Follow the project's existing physical-device restrictions; this coordination policy does not grant permission to flash firmware or execute unreviewed device code.

Coordination policy recorded from the project owner's instruction on 2026-11-07.

