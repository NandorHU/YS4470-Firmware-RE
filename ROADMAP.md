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

## 2026-11-09: extended deferred status

The extended `0x28`/`0x29` fallback is now exercised on both originals. Follow the `0x805ab920` reader candidate at `0x8005dac4` to bind decoded statuses to their consumers before naming the peer operation. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

The [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json) closes the local status-to-label path. Next trace the remaining reachable type-1 record at producer call `0x8000e36c` through the general fallback chain and identify alternate queue writers that could supply type 6. Use the [producer index](contributions/COORD-ADC-CADENCE/synchronous/control-producer-index.json) to exclude the already classified immediate branch sites.

## 2026-11-09: original control queue and type 6

Continue from the original queue and fallback evidence in the [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json). Trace type-2 and type-5 producer sites `0x8000d0c8`/`0x8000d0a0` through deferred dispatcher `0x80004390` into the measurement builder. Keep native type-6 reachability separate from the scoped synthetic execution and [queue reference index](contributions/COORD-ADC-CADENCE/synchronous/control-queue-index.json).

## 2026-11-09: dynamic type-2 selection and compiled plan

The dynamic type-2 producer, adjacent callback and record-byte clamp are covered in the [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json). A pure command-plan C component is checked in the [compiled-plan differential](contributions/COORD-ADC-CADENCE/synchronous/measurement-plan-validation.json). Next exercise consecutive native refresh-produced type-3 measurements after type-2 configuration to identify the first published sample.

## 2026-11-09: refresh and first publication

The [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json) covers refresh-produced measurement requests through discard and first publication. Next replace the `0x800037c0` and `0x8000326c` boundaries with bounded original conversion and renderer execution on the same lifecycle schedules.

## 2026-11-09: refresh rendering and sound

After the [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json), trace native Fast CONT mode entry and filter resets before attributing result freshness or proposing a change. Reuse the original queue, parser, renderer and PWM fixtures to isolate which event actually invalidates stored data.

## 2026-11-10 — Native mode entry and sound expiry

Carry the retained history from native mode 4 entry into the first two original refresh callbacks. Compare absent and valid replies before first fresh publication and inspect any sound reactivation through the original filter and PWM shadow. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).

## 2026-11-10 — First refreshes after native Fast CONT entry

Link the original countdown suffix to its measurement task loop and place expiry on either side of an original Fast CONT callback. Track raw scheduler counts and register shadow independently of physical latency. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-first-refresh-validation.json).

## 2026-11-10 — KeyTask and Fast CONT refresh ordering

Trace `0x80060fbc` from the KeyTask and GaugeCmdTask service call boundaries into the scheduler. Test arguments 50 and 1 with known task state, and keep raw counter deadlines separate from physical timing. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/key-task-fast-cont-order-validation.json).

## 2026-11-10 — Scheduler delays and task wakeup

Follow the byte-checked IRQ branch at `0x8000232c` to the original tick helper and context selection. Establish source and ordering with a controlled pending IRQ and saved task context. Keep modeled raw ticks distinct from hardware elapsed time. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-delay-wake-validation.json).

## 2026-11-10 — Installed vectors and scheduler context

Link the known Timer0 startup configuration and ordinary IRQ vector dispatch to the validated low-vector/context replay under separate pending-bit cases. Keep raw scheduler counters, GUI refresh and physical time separate. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-context-validation.json).

## 2026-11-10 — Timer0 and UART2 through the installed IRQ route

Reuse the linked IRQ ingress to run a bounded original service-loop schedule with real queue admission and delay. Then follow the remaining fallback producers and the helper under proven idle conditions, with separate evidence for the external peer. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-irq-validation.json).

## 2026-11-10 — Scheduled GaugeCmdTask service and fallback

Extend the scheduled harness to longer fallback waits and trace original producers for the status command chains. Preserve the distinction between scheduler counts, protocol progression and physical time. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-service-validation.json).

## 2026-11-10 — Scheduled long fallback and status waits

Link the scheduled status path to the original calibration UI timer without copying status snapshots between emulators. Check the waiting label and selected result before and after the final fallback cleanup. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-long-fallback-validation.json).

## 2026-11-10 — Live calibration status and UI timer

Continue the live calibration chain through the original reset stores, the type-3 enqueue at `0x8005dc38`, and the scheduled measurement reply. Preserve original UI formatting and separate the controlled GUI runner from hardware timing. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration reset to fresh measurement

Extend the linked replay to the full original button callbacks and real queue drain under a bounded pending-work schedule. The current writer starts at known producer suffixes after drain. [Shared ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration buttons and pending queue

Return to the remaining fallback producer search. Resolve indirect queue aliases for the original type-6 handler and test any new producer under the original idle gate. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-button-queue-validation.json).

## 2026-11-10 — Queue entry candidates and full-queue waits

Resolve executable provenance and indirect dataflow for remaining queue-write candidates. Link any genuine additional producer to original arguments and queue admission before assigning native type-6 reachability. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/queue-interior-full-validation.json).

## 2026-11-10 — Direct control producers and result-block writer

Trace the `r4` object at `0x80046548` and its stored value from `0x80030ad0`, then follow register-indirect and synthesized queue-handle candidates. Keep the original result-block stores at `0x8005d35c` outside the control-writer candidate set for the tested base provenance. [Factory hashes, original bytes and ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-producer-suffix-replay.json).

## 2026-11-10 — GUI field provenance at 0x80046548

Trace register-indirect and synthesized control-queue aliases and the native type-6 producer. The GUI field, result-block field and glyph bytes at `0x8009ef10` now have bounded provenance. [Original replay, instruction bytes and firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/gui-field-provenance.json).

## 2026-11-10 — Registered GUI callbacks and indirect queue producers

Use the verified second registration block at `0x800517f4` to replay `0x8000cfd0` from the original event dispatcher. Keep remaining register-indirect paths and native type-6 provenance separate. [Original instruction bytes, factory hashes and replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-event-validation.json).

## Current bounded continuation (2026-11-11)

Trace the writers of 0x805ac788 and verify the enabled 0x8005f254 route from the registered 0x8000cfd0 callback with realistic queue preconditions. Keep other indirect sends and native type-6 provenance open. [ARM926 replay and firmware identities](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

## Secondary channel continuation (2026-11-11)

Trace the device-ready and busy-clear producers for 0x805aac40 and 0x805aac70. Replay the original 0x8005fc08 channel-1 sender with bounded modeled peripheral state. Keep native type-6 provenance open. [Last verified experiment](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).

## Secondary USB receive continuation (2026-11-11)

Replay the original mode-1 USB RX endpoint through 0x800603f4 and 0x800606e0 to verify FIFO copy, guard-word initialization and RX status handling. Then trace the mode-1 producer paths that originate native type-6 control-queue records; keep hardware timing open. [Verified transmit lifecycle](contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-lifecycle-validation.json).

## Native type-6 provenance continuation (2026-11-11)

Bound additional Thumb-to-ARM and synthesized references to control producer 0x80006778, then classify credible indirect or alternate queue writers. Keep native type-6 provenance open unless demonstrated from an original caller. [Last GUI replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-second-final-validation.json).

## AC measurement refresh continuation (2026-11-11)

Follow original 0x8005d048 refresh after the verified AC checkbox release and type-2 UART configuration. Determine which later measurement frames publish and preserve the type-6 provenance question. Review candidate alternate queue writers when a credible code path appears. [Last verified ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-uart-validation.json).

## AC native result presentation (2026-11-11)

Execute the native result dispatcher and renderer on the already verified AC refresh schedules. Keep conversion units and physical timing open; retain native type-6 provenance as a separate question. [Last refresh replay](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-refresh-validation.json).

## Factory settings follow-up (2026-11-11)

Any independent diode-volume persistence needs a proven field or a versioned storage contract and an explicit write policy. The factory save path and its simulated short-transfer behavior now have reproducible evidence. [Storage evidence](contributions/COORD-DIODE-VOLUME/factory-settings-sector-validation.json) · [Failure boundary](contributions/COORD-DIODE-VOLUME/factory-settings-write-failure-validation.json).

## AC result text from the native renderer (2026-11-11)

Extend the original AC result presentation to signed samples and unit/scale boundaries. Keep native type-6 producer provenance and physical timing open. [Original replay evidence](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-renderer-validation.json).

## Signed AC samples, selector clamp and display cutoffs (2026-11-11)

Trace the factory settings +0x14 checkbox registration, label and save/load path into the configuration-10 display cutoff. Compare the separate highspeed formatter at 0x8005dc3c once the normal display setting is proven. Keep native type-6 producer provenance and physical timing open. [Original replay evidence](contributions/COORD-ADC-CADENCE/synchronous/ac-result-boundaries-validation.json).

## Factory Filter and the separate highspeed AC label (2026-11-11)

Execute original numeric formatting after the C runtime locale initializer at 0x800001d0, and compare normal and highspeed AC text with the modeled formatter. Keep native type-6 producer provenance and physical timing open. [ac-highspeed-result-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-highspeed-result-validation.json).

## Original AC formatter and native highspeed fallback callers (2026-11-11)

Follow the regular renderer call to 0x80045184 through 0x8005f1a8 and the original channel-1 sender, checking report text, units and USB gates. Keep native type-6 producer provenance and physical timing open. [ac-native-formatter-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-native-formatter-validation.json).

## Native AC widget storage and USB export (2026-11-11)

Map the original export category and unit routing outside AC configurations 9 and 10, then follow widget layout after native text storage. Keep native type-6 producer provenance and physical timing open. [ac-usb-export-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-usb-export-validation.json) · [ac-widget-text-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-widget-text-validation.json).

## USB report reconstruction and original AC label geometry (2026-11-11)

Recover the actual AC label construction and font/style bindings for GUI offsets +0x2f4 and +0x2f8. Use those bindings to extend the native layout replay. Keep native type-6 producer provenance and physical timing open. [ac-widget-layout-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-widget-layout-validation.json).

## Factory AC label bindings, wrapping and glyphs (2026-11-11)

Follow native label event 0x15 through 0x800158c4 and 0x800265bc. Verify clipping, alignment and glyph positions before the raster callback. Keep native type-6 producer provenance and physical timing open. [factory-bound-ac-layout-validation](contributions/COORD-ADC-CADENCE/synchronous/factory-bound-ac-layout-validation.json) · [factory-ac-font-glyphs-validation](contributions/COORD-ADC-CADENCE/synchronous/factory-ac-font-glyphs-validation.json).

## Native AC draw event and packed-alpha boundary (2026-11-11)

Execute the original 4-bit packed-alpha compositor at 0x80014688 (branch 0x800149d4) into an isolated RGB565 buffer, using the verified draw context and glyph inputs. Compare clipped output with the original bitmap nibbles. Keep physical LCD timing and native type-6 producer provenance open. [Original draw evidence](contributions/COORD-ADC-CADENCE/synchronous/factory-ac-draw-validation.json).

## Original 4-bit glyph expansion to blend input (2026-11-11)

Execute the actual blend callback installed at draw context +0x54 (0x8002a0bc) after 0x800289f8 into an isolated RGB565 buffer. Reuse the verified alpha regions and compare changed and untouched pixels. Keep physical LCD timing and native type-6 producer provenance open. [Original ARM926 evidence](contributions/COORD-ADC-CADENCE/synchronous/ac-alpha-mask-validation.json).
