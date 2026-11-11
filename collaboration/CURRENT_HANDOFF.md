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

## Signed AC samples, selector clamp and display cutoffs (2026-11-11)

The original UART parser sign-extends the 24-bit sample at `0x8000474c` and clamps selector bytes above 6 to 6 at `0x80004764`. Configuration 9 keeps negative values and explicit signs. Configuration 10 zeroes scaled results below 2.5, or below 5.5 when settings `+0x14` equals 1. Values equal to the active cutoff survive. Both use V for all seven effective selectors. Wire sample `0x7fffff` becomes `.OL` and clears the unit. The 936 synthetic UART cases execute the original checkbox, UART IRQ, parser, dispatcher and renderer in both factory images. The settings word is seeded, and the formatter and display sinks are modeled. Trace the factory settings +0x14 checkbox registration, label and save/load path into the configuration-10 display cutoff. Compare the separate highspeed formatter at 0x8005dc3c once the normal display setting is proven. Keep native type-6 producer provenance and physical timing open. [Original replay evidence](../contributions/COORD-ADC-CADENCE/synchronous/ac-result-boundaries-validation.json).

## AC result text from the native renderer (2026-11-11)

The original result dispatcher at `0x800037c0` reaches renderer `0x8000326c` after the native checkbox, UART and refresh path. In 16 ARM926 cases, configuration 9 requests signed three-place formatting and configuration 10 requests three-place formatting without an explicit positive sign. Both use V in the tested selectors. A delayed UART reply can leave the previous stored result on screen until a later refresh. Each factory image now initializes its own unit table. The harness models formatter and GUI sinks. Pixel output and physical scaling remain open. Extend the original AC result presentation to signed samples and unit/scale boundaries. Keep native type-6 producer provenance and physical timing open. [Original replay evidence](../contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-renderer-validation.json).

## Factory settings research (2026-11-11)

Original registration `0x8001b2d0` binds the settings save callback `0x800453c8` to GUI context `+0x394`. In the three tested event codes, event 1 reaches the original CRC and storage routine. The other tested events leave the record unchanged. A Fast CONT checkbox update alone changes the RAM word. The tested global volume field survives the factory loader. A safe separate diode-volume location remains open. Registry revision 52 links the evidence from the diode-volume task. [Settings evidence](../contributions/COORD-DIODE-VOLUME/factory-settings-ui-validation.json) · [Global volume](../contributions/COORD-DIODE-VOLUME/factory-volume-slider-validation.json).

## AC refresh and last-request behavior (2026-11-11)

The original timer enqueues a type-3 measurement after the AC checkbox configuration. The first valid reply consumes the remaining discard slot. The next valid reply publishes, and a missing reply delays publication by one request. The modeled view receives the latest stored result on a later native refresh. A second AC release during an active measurement produces a type-2 record. The original service defers that record until the old FSM is idle. An admitted old reply can still publish before the new configuration starts. With two additional releases, the earlier request is drained from the queue or replaced in the deferred slot, and only the last reaches the UART in the tested schedules. Registry revision 51 advances the owned task. Execute the native result dispatcher and renderer on the already verified AC refresh schedules. Keep conversion units and physical timing open; retain native type-6 provenance as a separate question. [Refresh evidence](../contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-refresh-validation.json) · [Rapid-toggle evidence](../contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-rapid-toggle-validation.json).

## AC checkbox release and UART configuration (2026-11-11)

The AC checkbox class at `0x80068e70` and its base handler `0x80035428` execute the original release-to-value-change path. Checkable release event 8 toggles widget state bit 0 and emits nested event `0x1c`, which reaches the registered callback `0x8000f3b4`. The same original queue record goes through service, FSM and modeled Timer0/UART2 IRQs without host re-enqueue. Registry revision 50 advances the owned task. Follow original 0x8005d048 refresh after the verified AC checkbox release and type-2 UART configuration. Determine which later measurement frames publish and preserve the type-6 provenance question. Review candidate alternate queue writers when a credible code path appears. [Dynamic evidence](../contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-uart-validation.json) · [Address index](../contributions/COORD-ADC-CADENCE/synchronous/control-synthesized-references.json).

## Original USB receive and second GUI callback block (2026-11-11)

The original USB mode-1 RX handler copies 64-byte type-3 reports from the modeled endpoint-2 FIFO, updates both guard words and stores the 61-byte record at `0x805ac640`. In the eight packet-ready cases across both images the original builder prepares the echo. Four idle cases write it to the channel-1 FIFO and four busy cases suppress that write. The second GUI registration block now has bounded original-dispatch replays for all ten callbacks. The eight newly exercised callbacks add 64 cases and 24 sends across V3.6 and V3.8. Every new send has record type 2. The 0x1c handler `0x8000f3b4` uses widget bit 0 to select argument 9 or 10 and writes timer-object value 2000. Registry revision 49 advances the same coordinator's task. Bound additional Thumb-to-ARM and synthesized references to control producer 0x80006778, then classify credible indirect or alternate queue writers. Keep native type-6 provenance open unless demonstrated from an original caller. [USB replay](../contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-rx-validation.json) · [GUI replay](../contributions/COORD-ADC-CADENCE/synchronous/control-gui-second-final-validation.json).

## Secondary USB send and busy lifecycle (2026-11-11)

The original source-26 registration suffix `0x8005fa64` installs `0x800606ec`. In one ARM926 state, original submit `0x80060ccc` and sender `0x8005fc08` write the frame, a second submit is suppressed while busy, and a ready TX interrupt clears the flag at `0x800606d4`. A subsequent submit writes its frame. The IRQ vector and exception return execute original bytes. Registry revision 48 advances the owned task. Replay the original mode-1 USB RX endpoint through 0x800603f4 and 0x800606e0 to verify FIFO copy, guard-word initialization and RX status handling. Then trace the mode-1 producer paths that originate native type-6 control-queue records; keep hardware timing open. [Native lifecycle evidence](../contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-lifecycle-validation.json).

## Diode/Buzzer setting writer and secondary command (2026-11-11)

Both factory images pass 48 ARM926 cases in total. The original writer `0x8005a3bc` stores bit 0 of the halfword at widget `+0x20` into `0x805ac788`. The registered callback uses that word to select the type-5 or type-2 record. The separate secondary command builds a 64-byte frame and reaches the original sender `0x80060ccc`. The hardware-facing `0x8005fc08` call is modeled. Registry revision 47 records the next bounded step. Trace the device-ready and busy-clear producers for 0x805aac40 and 0x805aac70. Replay the original 0x8005fc08 channel-1 sender with bounded modeled peripheral state. Keep native type-6 provenance open. [ARM926 replay](../contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).

## Registered Diode/Buzzer callback (2026-11-11)

The original second registration block and dispatcher route event 1 from GUI object `+0x2b8` to `0x8000cfd0`. Both factory images agree in 24 ARM926 cases. Mode 3 with word `0x805ac788 == 1` sends type 5 (`05 00 00 00 22 13`). Mode 3 with word 0 or 2 and mode 4 with any tested word send type 2 (`02 00 00 00 0e 19`). Event 2 leaves the callback and queue untouched. The scheduler is idle and selected UI leaves are modeled. Registry revision 46 advances the same coordinator's task. Trace the writers of 0x805ac788 and verify the enabled 0x8005f254 route from the registered 0x8000cfd0 callback with realistic queue preconditions. Keep other indirect sends and native type-6 provenance open. [ARM926 replay and original hashes](../contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

Latest analysis: [registered GUI callbacks](../contributions/COORD-ADC-CADENCE/synchronous/README.md#registered-gui-callbacks-and-indirect-queue-producers)
replays 56 event cases and verifies 26 indirect queue sends across both
images. The live registry is at revision 44. Next dispatch `0x8000cfd0`
through the verified second registration block.

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
