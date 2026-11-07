# Current shared handoff — 2026-11-07

Coordinator: the current Codex agent in the ongoing YS-4470 conversation.
Integration branch: [`re/2026-11-04-pyghidra-fel`](https://github.com/NandorHU/YS4470-Firmware-RE/tree/re/2026-11-04-pyghidra-fel).
Technical baseline before this onboarding publication: `7e173ffdaa7dffd67a2d998f3fa8b28036e99485`.
Read live ownership in [TASK_REGISTRY.json](TASK_REGISTRY.json); this handoff is
a research snapshot, not a substitute for current reservations.

## Goal and artifacts

Continue full V3.6/V3.8 reverse engineering and independent source reconstruction.
Beta3/1.0 are modified builds, not evidence of full reconstruction. Do not restart
from the earlier patch-only README/HANDOFF notes.

- [Current status](../REVERSE_ENGINEERING_STATUS.md) and [progress](../RE_PROGRESS.md).
- [58-entry function database](../FUNCTION_DATABASE.json), with evidence levels and relations.
- [Memory](../MEMORY_MAP.md), [hardware](../HARDWARE_MAP.md),
  [measurement algorithms](../MEASUREMENT_ALGORITHMS.md),
  [questions](../OPEN_QUESTIONS.md) and [roadmap](../ROADMAP.md).
- [Pinned SoC references](../references/f1c100s/README.md), source lock and register map.
- [Original input manifest](../original-firmware/manifest.json).

Both originals have 5,943,296 bytes. V3.6 SHA-256 is
`7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9`; V3.8 is
`7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`. Raw linked base is `0x7fffffe0`.
The application images are published at the owner's request; private 16 MiB
recovery backups are not included. The Release ZIP contains the different,
modified 1.0 image. Hardware observation is not available merely by cloning.

## Completed results to reuse

| Established bounded work | Method and evidence |
|---|---|
| F1C100S reference acquisition, licensing, MMIO candidates and proof-gated labels | [Method](../tools/F1C100S_REFERENCE_ANALYSIS.md), [report](../evidence/2026-11-07-f1c100s-reference/reference-analysis.json) |
| INTC/timer original-code paths: 4,446 reported cases | [Method](../tools/INTC_TIMER_PATH.md), [report](../evidence/2026-11-07-intc-timer-path.json) |
| Fast CONT history/retained median with independent Python/C reconstruction: 3,958 reported steps | [Method](../tools/FAST_CONT_FILTER.md), [C component](../reconstruction/README.md), [report](../evidence/2026-11-07-fast-cont-filter.json) |
| Stored-result reuse and caller conversion: 752 reported cases/steps | [Method](../tools/RESULT_FRESHNESS.md), [report](../evidence/2026-11-07-result-freshness.json) |
| Queue construction/send, critical helpers and renderer state: 2,396 checks, 14 Ghidra exports and nine provenance tests | [Method](../tools/REFRESH_SIDE_EFFECTS.md), [report](../evidence/2026-11-07-refresh-side-effects.json), [Ghidra](../evidence/2026-11-07-refresh-side-effects-ghidra.json) |

These are different experiments and units; do not sum their counts into a
whole-firmware completion percentage. Consult their matrices, guard conditions
and models before reusing a result.

Latest linked example: five original refresh callbacks enqueue five event4
records into the original-code-constructed queue without a parser entry. Filter
fill is [0,0,1,2,3], while stored raw14023 and discard2 remain unchanged. The final
retained value is5 and the emulated sound-active flag is1. This establishes
stored-result reuse in the bounded execution, not a measured live device delay.

Factory queue setup requests 10 items of 68 bytes. Original constructor/list
initialization, copy/send, critical nesting and renderer state helpers execute.
Allocator, formatting/widget/logging leaves, blocking/waiter paths and live
scheduling remain explicit limits. No whole-device emulation is established.

## Corrections that must carry forward

- ResultDispatch entry is `0x800037c0`; `0x800037bc` was a bad data seed.
- Refresh callback entry is `0x8005d048`; `0x8005d1a0` is a callsite.
- Fast CONT helper `0x80007c88` retains an earlier median when history is unstable.
  Its caller accepts 0..999; invalid/sentinel values bypass it and preserve history.
- Changed data cells are at file `0x63ac8..0x63ae8`, linked
  `0x80063aa8..0x80063ac8`. Pointer `0x80042d98` reaches the unchanged PWM
  table `0x80063acc`, not those changed cells.
- The reference survey's `follow_literal` already supports immediate ADD/SUB.
  A separate older MOV-only trace missed an ADD-zero alias; do not conflate them.
- PIO/PWM in emulation are inert memory shadows. Do not assign milliseconds or an
  acoustic outcome without the missing clock/scheduling/physical evidence.

## Reserved next task

`COORD-FSM-TIMEOUT` is reserved to the coordinator, not offered as parallel work.
No new timeout execution is claimed by this documentation session.

Prove FSM+0x30's cached reader at `0x800044a8` through R5 and elapsed-tick branches
`0x800046a8/0x800046c4/0x80004720`, using real tick getter `0x80061f84` and the
verified critical helpers. Test threshold boundaries and 32-bit wrap before
assigning units or interpreting Beta3's 30-to-40 change. Keep queue blocking,
waiters and remaining GUI/log leaves separate.

Six independent available tasks and one blocked hardware task are specified in
[TASK_REGISTRY.json](TASK_REGISTRY.json). New subsystems may be proposed using
[TASK_REQUEST_TEMPLATE.md](TASK_REQUEST_TEMPLATE.md). Publish one owner per scope
before starting; use a task directory and return evidence through the coordinator.

Publication validation from an isolated checkout: nine existing provenance tests
pass, and all 2,396 original-byte checks reproduce the previously committed
fingerprints using the two repository input paths. The 61 checked relative links
resolve. Details: `evidence/2026-11-07-collaboration-publication.json`.
