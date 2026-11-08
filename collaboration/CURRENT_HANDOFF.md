# Current shared handoff â€” 2026-11-08

Coordinator: the current Codex agent in the ongoing YS-4470 conversation.
Integration branch: [`re/2026-11-04-pyghidra-fel`](https://github.com/NandorHU/YS4470-Firmware-RE/tree/re/2026-11-04-pyghidra-fel).
Baseline read for this tooling/packet session: `9cdcfea5c5a12ee1884eda2b472c3cb0e0e2fc93`.
Read live ownership in [TASK_REGISTRY.json](TASK_REGISTRY.json); this handoff is
a research snapshot, not a substitute for current reservations.

## Goal and artifacts

Continue full V3.6/V3.8 reverse engineering and independent source reconstruction.
Beta3/1.0 are modified builds, not evidence of full reconstruction. Do not restart
from the earlier patch-only README/HANDOFF notes.

- [Current status](../REVERSE_ENGINEERING_STATUS.md) and [progress](../RE_PROGRESS.md).
- [60-entry function database](../FUNCTION_DATABASE.json), with evidence levels and relations.
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

Latest linked refresh example (2026-11-07): five original refresh callbacks enqueue five event4
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

## Latest completed timed-state proof

[COORD-FSM-TIMEOUT](../contributions/COORD-FSM-TIMEOUT/README.md) now has13,302
checks, four Ghidra exports and a second independently buildable C component.
See [report](../contributions/COORD-FSM-TIMEOUT/fsm-timeout.json) and [source](../reconstruction/fsm_timeout.c).

FSM+0x2c is start, +0x30 is duration cached in R5. States2/3/4 compare unsigned
modulo elapsed against duration; equality expires. Complete valid state3 frames
are admitted before the deadline check. Original setup commands0x1b/0x1d seed30
and required5; other tested commands seed80; ACK9..15 seeds settle50 or100.
The real getter reads0x805abbc8 under the original critical helpers. No
milliseconds, actual Beta3 execution or live acoustic behavior was established.
Tick prefix/list scheduling and modeled UART send remain separate limits.

## Reserved next task

COORD-FSM-TIMEOUT is completed. COORD-ADC-CADENCE is reserved to the current
coordinator. Validate the MainADCTask candidate 0x80005a78 and actual callers of FSM 0x80004490; bound one task-loop iteration and the delay candidate 0x80060fbc before assigning a polling cadence. Keep GUI callback periods, live clock frequency and acoustic latency separate.

Read live ownership in [TASK_REGISTRY.json](TASK_REGISTRY.json). Five external
tasks remain available; passive UART capture remains blocked. No external agent
was assigned in this run. All prior completed evidence above should be reused.


## Local helper state â€” 2026-11-08

Read [LOCAL_LLM.md](LOCAL_LLM.md) before assigning more local work. The six-case
source audit is completed and reviewed; the local client remains an optional
small-task helper. Examples changed the tiny check from0/2 to1/2 without weight
training; semantic reliability remains insufficient for autonomous ARM analysis.
The main coordinator proceeds with COORD-ADC-CADENCE. Do not rerun completed
batches or treat earlier profile drafts as firmware proof.


## 2026-11-08 packet/tool handoff

The completion/retry/resume gate and six original-hash-bound GaugeCmdTask/sound/GUI function packets are verified. See contributions/COORD-FUNCTION-PACKETS/README.md (360 instruction-byte checks, 388 CFG edges, four bounded original executions, 13 tests). GaugeCmdTask's static name binding reaches 0x80003dbc; its outer loop calls the still-candidate service0x80005b6c. The local index covers six packets; no global-data equivalence or physical timing is inferred.

Next reserved task: COORD-ADC-CADENCE. Reuse the completed FSM proof and packets to validate the task/serviceâ†’FSMâ†’delay placement before assigning raw polling cadence. Do not repeat local comparisons or infer milliseconds, acoustic speed, or a whole-firmware percentage.

Reuse [packet index](../contributions/COORD-FUNCTION-PACKETS/packet-index.json), [original-byte/execution checks](../contributions/COORD-FUNCTION-PACKETS/validation.json), [completion audit](../contributions/COORD-FUNCTION-PACKETS/legacy-completion-audit.json), and [local comparison review](../contributions/COORD-FUNCTION-PACKETS/comparison-review.json). The completion worker passed13 tests and resumed with zero new calls.22/31 historical replies stay incomplete; old files were unchanged. The controlled full/short context scores do not establish general reasoning or speed gains.

The function database now has60 records. No live-device timing, firmware installation, training or external agent assignment occurred. Five external tasks remain available; check live ownership before taking one. Installed tools/REA limits are in [LOCAL_LLM.md](LOCAL_LLM.md). No new heavy emulator or vector index was needed.
