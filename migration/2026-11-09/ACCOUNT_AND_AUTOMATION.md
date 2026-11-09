# Account and automation migration

The prepared kit moves project knowledge, public source/history, approved inputs
and reproducibility instructions. It does not transfer a ChatGPT subscription,
chat memory, plugin connection, GitHub ownership, Windows account or login.

## Owner checklist

1. Give the new agent the kit and NEXT_AGENT_PROMPT_HU.txt. Prefer the extracted
   fresh checkout/ready-workspace. Confirm which account and machine will run it.
2. Connect the new account to GitHub with its own authorized credentials. Connect
   REA/native execution/computer-use only if available and needed. Confirm actual
   tools rather than assuming the old account's tool names or permissions exist.
3. Same Windows user/PC: inventory paths can reuse existing Python/Ghidra/Java,
   Ollama/model directories. Different Windows user/PC: provide appropriate file
   access or reinstall tool dependencies; replace every machine-specific path.
   Model weights and Ghidra project databases are not automatically in the ZIP.
4. Disable the old daily automation before enabling a new duplicate. The old
   automation was observed ACTIVE and **was not changed** by this handoff.
5. Start the successor with the owner-approved takeover prompt. The new
   coordinator reads live tasks/issues/PRs and records its unique identity and
   ownership against the latest head. Prevent simultaneous primary coordinators.
6. Preserve the old private device backups locally. They are excluded from the
   public kit. If later hardware work needs them, the owner must separately
   provide private access and verify device/image identity; never upload them
   to GitHub or substitute them for the two public original applications.

Do not copy .codex authentication, browser cookies/sessions, OAuth/API/SSH keys,
Ollama private keys or cloud credentials. Use normal sign-in/reconnection in the
destination account. GitHub repo ownership transfer is a separate explicit owner
operation and has not been performed. All references still use NandorHU/YS4470-Firmware-RE.
If its URL later changes, update remotes/automation/registry links deliberately.

## Existing daily automation

- ID: ys-4470-n-ll-napi-firmware-visszafejt-s-projekt-https-github-com-nandor
- Name: Folytasd az YS-4470 visszafejtését
- Observed: ACTIVE, heartbeat, every day at08:00, Europe/Budapest.
- Existing workspace: the old2026-11-04 project directory, which is a partial
  file snapshot. A new automation should use the new real dev checkout.
- It does not migrate automatically to another account. No new automation was
  created, and the old one was not paused/deleted/edited during this handoff.

Use the destination app's automation settings/tools, not a copied internal auth
file. Suggested **prompt content** for the new daily job after takeover:

> Continue the existing YS-4470 project from migration/2026-11-09/README.md.
> Read AGENTS.md, CONTRIBUTING.md, live development-branch task registry,
> current handoff and latest research status first. Check open issues/PRs and
> avoid duplicate ownership. Complete one bounded new firmware-analysis task,
> preferably the current COORD-ADC-CADENCE continuation. Reuse completed evidence;
> give the local model only a new small owned source-extraction task when useful,
> with checked lessons and deterministic review. Test original-code conclusions,
> preserve firmware hashes, mark hypotheses, and update the seven continuity
> documents plus RE_PROGRESS.md. Commit/publish accepted work on a development
> branch only. No main mutation, paid APIs, private dump publication or physical
> firmware/RAM writes. Record the exact next step. Notify the owner only for a
> meaningful result, failure or required action.

That text is a suggested job prompt, not a newly installed schedule.

## What the kit intentionally does not contain

- Personal16MiB backups, device calibration, private original archives beyond the
  two owner-approved application images, arbitrary vendor SDK/BROM binaries.
- Multi-GB model weights, complete portable software distributions, virtualenvs,
  package caches, browser profile, account tokens, the complete old chat archive.
- Manual Ghidra project databases. Their local paths are inventoried; accepted
  hash-bound packets, decompiler/assembly/CFG exports and repro scripts are in Git.

On the same machine these installations remain available at the inventoried
paths. On another machine the bundle/source and evidence are self-contained,
but executing analyses still requires the documented dependencies. The kit's
public source history may reference older paths; use the current handoff as the
entry point. A full original-vendor source reconstruction still does not exist.
