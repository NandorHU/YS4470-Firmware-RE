# Roadmap

## Current next bounded task

Prove FSM+0x30's cached reader0x800044a8 through r5 and elapsed-tick branches0x800046a8/0x800046c4/0x80004720 using real getter0x80061f84 and the verified critical helpers. Test threshold boundaries and32-bit tick wrap before assigning units or interpreting Beta3's30-to40 change. Keep blocked queues, waiters and remaining GUI/log leaves separate.

## Near term

1. Prove cached FSM timeout/tick comparisons with the original tick getter.
2. Bound tick/scheduler and FSM timeout consumers.
3. Continue original measurement scaling/autorange reconstruction and remaining version-patch attribution.
4. Reuse the completed parser, settings, PWM, INTC/timer and C filter harnesses.

## Later milestones

- Establish task/interrupt map and startup flow.
- Validate ADC task, range logic, resistance/voltage/current/capacitance algorithms.
- Reconstruct GUI, settings, storage, calibration, and update flow.
- Build a separately compilable functional reconstruction with test fixtures; never replace or flash original firmware automatically.


## Updated next bounded task (2026-11-05)

Find the consumer(s) of `0x805ac694+0x30` and prove whether the field is decremented by a scheduler tick, checked as a protocol timeout, or exported to another subsystem. Then map the three selector bytes at `0x805abefc+0/+2/+7` to their writers. This is the shortest path to establishing whether the Beta3 30→40 change affects measurement cadence rather than only metadata.


## Updated next bounded task (2026-11-05, after literal trace)

Trace the event/scheduler path originating at `0x800031b8` and its callbacks to find an indirect consumer of FSM object `+0x30`. In parallel, follow the dynamic write at `0x8000d74c` and related writers until a proven `0x805abefc+0 = 3` source is found. Preserve the distinction between a static state-field value and physical time.


## Updated next bounded task (2026-11-05, after PIO trace)

Decode the descriptor records at `0x8006367c + 8*command_id` for IDs `0x09..0x0f`. Establish command bytes/lengths, link the two observed PIO patterns to protocol commands, and only then attempt a measurement-mode mapping. Keep the unresolved FSM `+0x30` indirect-consumer search separate.


## Updated next bounded task (2026-11-05, after descriptor decoding)

Trace `0x80006dc8` to identify the byte transport and its completion/timing contract. Then follow response parsing for descriptor IDs `0x09..0x0f`, especially 0d/0e, to map a command/PIO/frame path to observed measurement behavior without guessing UI labels.


## Updated next bounded task (2026-11-05, after UART2 trace)

Trace UART2 initialization: locate the writes to `0x01c25800` register offsets (divisor/LCR/FCR/IER and pinmux setup), then trace the RX-buffer completion path from `0x805b408c` into parser state 5. This should establish wire configuration and command/response transaction boundaries without hardware interaction.


## Updated next bounded task (2026-11-05, after UART2 initialization)

Trace the RX-buffer frame-completion path: identify every writer/reset of `0x805ab938` and every caller that invokes parser state 5 at `0x80004738`. Output a verified frame-boundary rule before assigning command/response semantics to UART2 frames.


## Updated next bounded task (2026-11-05, after RX lifecycle trace)

Trace the descriptor-table entries and callers for FSM command IDs `0x1b` and `0x1d`. Establish their transmitted frames, their state-3 headers (`0x5e`/`0x60`), and the consumers of the signed-24-bit result without assigning a physical measurement name prematurely. Keep descriptors 09–0f separate until their own response path is proven.


## Updated next bounded task (2026-11-05, after command-1b/1d extraction)

Trace the state-5 result stores and their consumers: resolve the literals at '0x8000481c..0x80004820', follow the signed value and selector written at '0x800047b4..0x800047b8', and connect them to a UI/result structure. Do not infer diode, continuity, or any physical range name from dispatcher case values without a proven downstream mapping.


## Updated next bounded task (2026-11-06, after result-flow trace)

Trace the special state-5 saturation branch backward: resolve the object at '0x805aae8c+0x08', prove which command/config values select IDs 0x0d/0x0e, and determine when threshold '0x1389' causes sentinel '0x007fffff'. Then separately trace ResultDispatch's SoundControlGate call conditions without equating them to a physical buzzer event.


## Updated next bounded task (2026-11-06, after saturation-path reconstruction)

Trace the ResultDispatch sentinel branch at '0x800037fc..0x80003854' into SoundControlGate '0x80006e4c' and its immediate callees. Prove call arguments, gate conditions, and the first hardware-facing sound-control operation. Keep the distinction between a sentinel-triggered software call and audible buzzer behavior.

## Updated next bounded task (2026-11-06, after V3.6 intake)

Run the existing bounded PyGhidra seed inventory on the verified original V3.6 input and compare it with V3.8. Separately trace the literal-pool consumer beginning at `0x80042d98` to classify the nine changed V3.6/V3.8 data cells. Keep the already scheduled ResultDispatch → SoundControlGate trace independent; do not infer buzzer timing or a physical measurement mode from the version-data delta.

## Updated next bounded task (2026-11-06, after live FEL identification)

Use the verified local flash backup to classify the regions outside the main eGON image, beginning with header and signature scans plus known package assets. In parallel, restore the bounded PyGhidra V3.6 inventory environment and compare V3.6/V3.8 known function windows. Do not flash any image merely to accelerate analysis: the current device is confirmed E2-modified, and its backup must remain the recovery baseline.

## Updated next bounded task (2026-11-06, after PyGhidra V3.6/V3.8 baseline)

Trace SoundControlGate at 0x80006e4c into direct callee 0x800060d0 and continue until the first hardware-facing sound-control operation is proven. The relevant bounded V3.6/V3.8 exports are identical, so perform this once against V3.8 and carry the evidence to V3.6 only within that bounded scope. Keep passive UART-TTL capture as a separate future validation task.

## Updated next bounded task (2026-11-06, after real-byte ARM926 execution)

Trace the writers of sample-discard byte `0x805aae8d`, starting from the verified control-object literal loads. Determine what sets/reset its initial count and which input modes can reach it. Reuse the new 5,952-case parser harness for regression rather than redoing parser disassembly. The separate SoundControlGate → 0x800060d0 hardware-control trace remains pending.

## Updated next bounded task (2026-11-06, after countdown lifecycle)

Trace the record-building helper at 0x80006778 and its direct callers. Establish which input events produce software cases 2/5, and which source values fill record bytes +4/+5. Preserve physical measurement names as hypotheses until a UI/string or explicit hardware mapping supports them. Reuse the completed lifecycle/parser harnesses; do not repeat their disassembly. SoundControlGate → 0x800060d0 remains a separate pending hardware-control task.

## Updated next bounded task (2026-11-07, after GUI event-source linkage)

Trace settings word 0x805ac788 through writers/defaults/storage and seek its GUI label. This is the shortest next step to explain why the Buzzer UI can select either [0x0e,0x19,0x1d] or [0x0c,0x22,0x13,0x1d]. Reuse the validated event-builder/dispatcher/parser harnesses. Queue timing and SoundControlGate hardware ownership remain separate pending tasks.

## Updated next bounded task (2026-11-07, after Fast CONT identification)

Trace the Fast CONT-dependent result consumer starting at 0x80003870/0x80003878, then connect its sound-gate conditions and arguments to 0x80006e4c → 0x800060d0. Recover the first peripheral-facing sound operation without assigning a millisecond delay or acoustic outcome. The named setting/default/record format is now established; reuse the Fast CONT and event-source harnesses rather than repeating that work.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

Next: reconstruct/test helper0x80007c88 with persistent histories, invalid/threshold values and range-table choices; feed its calls into the now-validated gate. Do not rerun completed parser, Fast CONT setting or gate analysis. Reference-based SoC signature tooling is an authorized parallel workstream within the continuing project.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

Immediate reference continuation: validate INTC dispatch0x80005260 and registration region0x80005274, then timer setup near0x800071a8. These are candidates, not established full function bounds. Use the register map and exported graph to choose paths; resolve literals/relocations before matching more functions. Carry forward Fast CONT helper0x80007c88 persistent-history tests as the pending measurement task. Reuse completed parser/setting/PWM harnesses; no full-device emulation or firmware installation is authorized by a similarity lead.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

Completed the previously queued INTC/timer and Fast CONT helper investigations. Reuse4446 hardware/control-flow tests and3958 original/Python/C filter steps; do not redo these disassemblies. New pure-C component is a first verified reconstruction component, not a complete firmware image.

Next bounded task: Trace fresh-result admission from ResultDispatch call0x80003970 into helper0x80007c88. Determine whether repeated calls can reuse one parsed UART result. Separately bound tick/scheduler0x80061fa4/0x800612f8 and the consumer/decrement of FSM field0x805ac694+0x30 before assigning timing units.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

Completed the stored-result reuse counterexample and caller conversion contract. Reuse the752-case/step freshness runner, earlier filter C tests and hardware harnesses. Update all future analysis to ResultDispatch0x800037c0 and callback0x8005d048; the old0x800037bc/0x8005d1a0 seeds must not be interpreted as correct function entries.

Next: Audit real renderer0x8000326c and enqueue path0x80006778 for side effects excluded from the refresh model. Then prove FSM+0x30's cached read at0x800044a8 (r1=sb via ADD#0), its elapsed-tick comparisons and tick getter0x80061f84; do not assign milliseconds before that contract is validated.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

The queue/renderer core audit is complete within its stated scopes. Reuse the2396-check side-effect runner and previous freshness/filter/INTC harnesses. Do not return to the two top-level stubs as if their original bodies had never been checked. Keep graphics/text/log models and blocking queues explicit.

Next bounded task: Prove FSM+0x30's cached reader0x800044a8 through r5 and elapsed-tick branches0x800046a8/0x800046c4/0x80004720 using real getter0x80061f84 and the verified critical helpers. Test threshold boundaries and32-bit tick wrap before assigning units or interpreting Beta3's30-to40 change. Keep blocked queues, waiters and remaining GUI/log leaves separate.

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

Completed COORD-FSM-TIMEOUT with 13,302 checks, four real Ghidra exports and nine
provenance tests. Reuse the runner and the pure-C timed-state component; do not
repeat the old missing-reader investigation or treat +0x30 as a per-call decrement.
The prior filter, queue/renderer and INTC evidence remains valid in its scopes.

Next reserved task COORD-ADC-CADENCE: Validate the MainADCTask candidate 0x80005a78 and actual callers of FSM 0x80004490; bound one task-loop iteration and the delay candidate 0x80060fbc before assigning a polling cadence. Keep GUI callback periods, live clock frequency and acoustic latency separate.

The six external tasks remain available and the physical UART task remains
blocked; no external assignment or live hardware test was manufactured.


## 2026-11-08 completed tooling scope / next work

- Completed COORD-LOCAL-TOOLS: isolated pinned promptfoo/DSPy/MCP, measured local calibration and a scoped REA request.
- Completed COORD-FUNCTION-PACKETS: strict completion/checkpoint/retry/resume, six original-hash-bound local CFG packets,13 tests,360 instruction-byte checks,388 edges, four bounded original runs and a six-row SQLite/FTS5 index.
- Continue coordinator-reserved COORD-ADC-CADENCE from GaugeCmdTask0x80003dbc→service0x80005b6c and the established FSM/tick evidence. Keep MainADCTask, GUI periods and physical acoustic delay separate.
- Extend the packet/index corpus only for an owned research question. Heavy emulators, vector retrieval and weight training remain deferred until a concrete measured gap requires them.


## 2026-11-08 public factory patcher complete

COORD-PUBLIC-PATCHER provides a standard-library CLI, Windows launcher, bilingual instructions, reversible exact-hash sparse application edits and tested public Release provenance. No private backup, boot/logo replacement, device installer or new firmware behavior is shipped. Resume coordinator-owned COORD-ADC-CADENCE from its pinned E2/source checkpoint; the requested four-profile timing matrix remains unfinished.


## 2026-11-08 installer milestone completed

COORD-EASY-INSTALLER published the English self-contained1.1.0-beta.2 Release with factoryV3.8, runtime/FEL/driver helper, automatic private backup/verification/recovery, source archives and SHA256SUMS. Clean Windows CI passed19 installer/driver-launch tests and14 patcher tests; no device write occurred. Source tag is installer-v1.1.0-beta.2. The full firmware RE project remains unfinished. Continue coordinator-owned COORD-ADC-CADENCE; do not repeat completed packaging work as firmware research.


## 2026-11-08: equal-Highspeed profile evidence

COORD-ADC-CADENCE remains in progress after the64-case equal-Highspeed matrix,64 profile switches and16 existing-candidate comparisons. Next resolve installed identity and whether repeated0x60 requests restart or buffer the external conversion; absent hardware, add explicitly hypothetical response-source/phase-order variants without treating any as physical truth. The public installer remains unchanged1.0 firmware. Do not rerun the completed matrix/local extraction unless code, inputs or unresolved guards change. Exact checkpoint: contributions/COORD-ADC-CADENCE/STATUS.md.


## 2026-11-09: original UART correlation proof

Continue COORD-ADC-CADENCE from contributions/COORD-ADC-CADENCE/STATUS.md and uart/README.md. Completed now:12,704 three-way original/C/Python transport cases,184 arrival schedules,12 explicit ISR interleaves,4 two-frame concatenations and six fresh Ghidra function exports. Next bound the original shared-buffer admission-to-parse interval and synchronous helper0x80005f14 actual callers/writers. Reuse existing packets and prepared local source indexes; do not repeat the completed profile or transport matrices without a code/input/guard change. External conversion behavior still blocks a justified physical speed/correlation fix.


## 2026-11-09: admitted-frame stability and caller ownership

Completed the bounded admission-to-parse step:1,200 original-code cases,24 service-gate cases, nine classified BL sites plus one tail branch, and95-instruction static synchronous-helper context per original. Next trace fallback message producers/other aliases and execute synchronous helper success/failure under reachable caller/idle preconditions. Keep broad physical ADC/latency questions separate. Do not rerun the completed transport/profile/admission matrices without changed code, inputs or unresolved guards. Exact continuation: contributions/COORD-ADC-CADENCE/STATUS.md.


## 2026-11-09: local model restored and startup-helper execution

Reuse the40 completed startup-helper cases and prior profile/transport/admission proofs. Next bound further reachable deferred-handler arguments/message producers before extending helper semantics or claiming global RX ownership. For local assistance, the service is restored at127.0.0.1:11435; use synchronous/start_local_server.ps1 with explicit existing exe/models/writable-state paths for recovery. Give new small tasks the checked base lessons plus local-heldout/LESSONS-UART.md; do not rerun frozen completed batches or grant model shell/device tools.


## 2026-11-09: account-migration handoff prepared

The owner requested a complete transfer to another account. See
[migration/2026-11-09/README.md](migration/2026-11-09/README.md), its detailed
AGENT_HANDOFF.md, tool/setup inventory and machine-readable ARTIFACTS.json.
Research baseline remains a2e5e7ebd2f661f37f88507f55a62a14c5df3f9f;
62 function records. No new firmware finding or changed hardware claim is
introduced by this documentation session. The existing memory/hardware/
algorithm evidence and uncertainties remain as recorded above.

A fresh public checkout passed14 patcher tests,40 existing startup-helper
cases and six-packet validation (360 byte checks/388 CFG edges/four outer-loop
runs); READINESS_VALIDATION.json records this portability check. Originals were
rehashed. A full-history bundle/source kit and local environment inventory are
prepared separately without private dumps, credentials or model weights.
The beta.2 GitHub Release currently returns404 although its tag/source remain;
the exact previously published Windows ZIP is retained locally with its pinned
hash. No republishing, main/device write or automation change was performed.

Next research task remains COORD-ADC-CADENCE: further reachable deferred-handler
arguments/record producers and aliases before broader shared-buffer claims;
startup IDs9/19 are already proven. The old daily automation is still active
at08:00 Europe/Budapest and must be deliberately switched during account takeover.
The prepared handoff does not silently release ownership or start a second agent.

## 2026-11-09: original deferred producer paths

COORD-ADC-CADENCE now covers four original deferred paths and 16 ARM926 executions across V3.6/V3.8. Continue with the `0x28`/`0x29` caller suffixes and idle path at `0x80003eb8`. Capture the extended reply handling and separate the queue, sleep and UART models from original execution. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json).
