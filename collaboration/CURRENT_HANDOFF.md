# Account-transfer entry point — 2026-11-09

Read [the complete migration handoff](../migration/2026-11-09/README.md) first.
It pins the transfer's research commit a2e5e7ebd2f661f37f88507f55a62a14c5df3f9f,
62 function records, restored local model,40 startup-helper cases and exact next
COORD-ADC-CADENCE step. Earlier sections below are historical snapshots.
The local transfer kit contains full public Git history, approved originals,
checksums and a tool inventory; private backups/credentials/model weights stay out.
Beta.2 Release API currently404; retained historical installer is documented.
The owner confirmed the old daily automation was stopped. The new coordinator
`codex-ys4470-20261109-01a1c110` is recorded in upstream registry revision 19.

Latest analysis: [calibration status UI](../contributions/COORD-ADC-CADENCE/synchronous/README.md#calibration-status-ui)
links the `0x28`/`0x29` commands to their original button text and exercises
the result callback at `0x8005da88` and its timer. Next trace the general
type-1 path from `0x8000e36c` and search for alternate type-6 queue writers.

---

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


## Public patcher published / exact profile continuation (2026-11-08)

The public factory-input patcher in patcher/ now accepts pinned original V3.6/V3.8 applications and personalized16 MiB containers, without a private Beta3 backup.14 regression tests and12 bounded original ARM926 loader-window cases passed. V3.8 continuous matches the downloaded public1.0 application; V3.6 retains version-specific factory bytes and is offline-tested only. No bootloader/logo replacement or device operation is performed.

Reuse contributions/COORD-PUBLIC-PATCHER/validation.json and loader-validation.json; do not rebuild from a private full backup. The source can regenerate patch-data.json using only public originals and the SHA-pinned public Release ZIP. New installation compatibility is not claimed.

COORD-ADC-CADENCE remains in progress and owned by the coordinator. I read E2 builders and legacy pipeline tests, checked the actual E2 application hash against its manifest, and then followed the owner's distribution request. No legacy profile tests were imported/executed, no four-profile event trace or new latency explanation exists. Resume at contributions/COORD-ADC-CADENCE/STATUS.md; source hashes are in profile-inputs.json. The next step is a side-effect-free build reproduction followed by same-Highspeed, requested/active-profile event traces and one new bounded local-LLM extraction job.


## Installer release / continuation (2026-11-08)

The English Windows installer is published as [1.1.0-beta.2](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/installer-v1.1.0-beta.2) ([Windows ZIP](https://github.com/NandorHU/YS4470-Firmware-RE/releases/download/installer-v1.1.0-beta.2/YS4470-Installer-1.1.0-beta.2-Windows-x64.zip)). It includes factory V3.8, its Python/Tcl/Tk runtime, the pinned FEL utility and the official driver helper. Automatic backup/second-read confirmation/application-only writes/full readback are covered by19 simulated transport/driver-launch tests; the public patcher has14 original-input regression tests. The clean GitHub Windows build passed and all four uploaded asset digests were verified before publication. No device was written; GUI visual control was not established, and this new installer/FEL package is physically untested.

The published source commit is c12fdef3fcb56c1f6b504ac1330f02965e6bc727 on release/easy-installer-1.1; the successful workflow run is42499845896. The prior beta.1 draft remains unpublished after its draft-lookup failure. The corrected workflow verifies uploads by release ID and does not overwrite existing releases. A driver-launch UAC issue was corrected with explicit runas and three mocked launcher tests. See contributions/COORD-EASY-INSTALLER/ for public download/CI receipts and local limits. No private backups are in either asset ZIP.

Resume COORD-ADC-CADENCE from its existing E2/source hash checkpoint. No new four-profile comparison, physical latency explanation or offline speed fix was established in this redirected distribution session. Keep the new installer beta's host tests separate from the historical1.0 device result. The local helper request timed out; do not repeat it or promote nonexistent output.


## 2026-11-08: equal-Highspeed profile evidence

The next usable checkpoint is now contributions/COORD-ADC-CADENCE/STATUS.md. The public-stock recorded-edit chain,64-case equal-Highspeed matrix,64 active/requested switches and16 candidate comparisons passed268 assertion groups. Direct removes the observed GUI audio wait; Auto/Ready alter request cadence and brief-pulse width. Neither proves physical Base superiority. Task remains coordinator-owned/in_progress; resolve installed identity and actual external response behavior before another speed patch. All active-path observations are pinned E2; original idle service executes separately on3.6/3.8. No main/Release/device change.


## 2026-11-09: original UART correlation proof

Latest coordinator checkpoint: contributions/COORD-ADC-CADENCE/STATUS.md, with new uart/README.md, validation.json and six Ghidra exports.12,704 three-way transport cases and controlled original-code retry/interleave cases passed. A stale same-header frame can be accepted after retry; two queued frames publish only the first, with the tail lost at next state1 clear. Task stays coordinator-owned/in_progress. Next bound admission-to-parse buffer stability and synchronous0x80005f14 actual callers. The earlier64-case E2/profile result remains intact and is not rerun. The local checksum draft was reviewed; two new small RX/synchronous index requests hit a refused localhost service and remain without model findings. No device/main/Release change.


## 2026-11-09: admitted-frame stability and caller ownership

Latest bounded result is contributions/COORD-ADC-CADENCE/admission/:1,200 original admission/parser cases,24 service gates, nine classified BL sites and one newly recorded tail edge0x8000404c→0x80005f14. The admitted RX prefix is stable against append-only ISR arrivals under stated conditions. Tested fallback control-handler entry is idle-gated; no feasible active-acquisition synchronous-clear race is inferred. New database records are scoped analyst roles, not full reconstructions. Continue with reachable synchronous-helper execution and message producer/alias ownership; preserve external ADC/physical timing uncertainty.


## 2026-11-09: local model restored and startup-helper execution

Latest bounded work is contributions/COORD-ADC-CADENCE/synchronous/: restored local service, two reviewed extraction responses, one new in-context held-out exercise, and40 original startup-helper cases for arguments9/19. The previous refused-service issue is resolved; old failures remain intact for provenance. The helper's one-byte ACK, two-attempt/500-per-attempt check/sleep order and late-final-check boundaries are established only for tested startup descriptors. Continue reachable deferred-handler/message-producer analysis; keep measurement FSM admission, ADC behavior and physical latency separate. No main/device/Release change.
