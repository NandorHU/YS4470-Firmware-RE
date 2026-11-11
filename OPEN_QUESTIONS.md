# Open questions

## Current unresolved work (2026-11-07)

1. Prove FSM+0x30's cached reader0x800044a8 through r5 and elapsed-tick branches0x800046a8/0x800046c4/0x80004720 using real getter0x80061f84 and the verified critical helpers. Test threshold boundaries and32-bit tick wrap before assigning units or interpreting Beta3's30-to40 change. Keep blocked queues, waiters and remaining GUI/log leaves separate.
2. What initializes the filter history/count/retained median at power-on, and what physical scalar unit reaches it?
3. What is the alternate INTC table's role? Complete exception context restoration remains untested.
4. Recover remaining ADC scaling, autorange, measurement algorithms, GUI, calibration, storage and update subsystems.
5. Attribute remaining modified-version ranges and the nine changed V3.6/V3.8 data words.

## Historical investigation log

## Resolved static portion — 2026-11-05

The patches at `0x800045e0` and `0x80004738` are observer wrappers, not changed frame construction or changed signed-24-bit parsing. The `0x8000461c` patch conditionally changes the state-3 `+0x30` field from 30 to 40.

Remaining: identify every read/decrement of `0x805ac694+0x30`, determine the meaning of control bytes at `0x805abefc+0/+2/+7`, and trace the field to a physical timer or protocol cadence before claiming a latency effect.


## 2026-11-05 narrowed questions

- Which indirect callback, scheduler, or alias consumes `0x805ac694+0x30` after the FSM writes it?
- Which writer establishes `0x805abefc+0 = 3` for the Beta3 30→40 condition?
- What semantic mode/event does HighspeedEventHandler's `+2` toggle represent?

The direct PC-literal-object paths have been tested; do not repeat that direct scan before pursuing interprocedural flow.


## 2026-11-05 PIO questions

- Which command descriptors at `0x8006367c` correspond to IDs 0x09–0x0f, and what protocol payload does each send?
- Which F1C100S PIO port/pins correspond to MMIO word `0x01c208c4`?
- What external circuit responds to the two-bit patterns?
- Continue indirect tracing of `0x805ac694+0x30`; the `0x800031b8` route has been disproven as a scheduler path.


## 2026-11-05 descriptor questions

- Which response/state paths associate descriptor IDs 09–0f with user-visible measurement modes?
- What peripheral or software transport is implemented by byte-output candidate `0x80006dc8`?
- Why do parser selector handling and descriptor IDs 0d/0e intersect, if they do? No association is assumed yet.


## 2026-11-05 UART2 questions

- Where are UART2 pinmux, divisor, line-control, and interrupt-enable registers configured?
- Which external IC/device is attached to UART2, and what are its documented frame semantics?
- Which RX frame values correspond to descriptor IDs 09–0f?
- Does the FSM `+0x30` field define a timeout for this UART2 transaction, and if so where is it consumed?


## 2026-11-05 UART2 initialization questions

- What exact CCU/UART input clock is active when divisor `0x0249` is programmed, and what resulting baud does it produce?
- Does the first `0x60 0x60` UART2 sequence reset, synchronize, or select the external measurement device?
- Which interrupt controller line/vector reaches the UART2 RX ISR after init?
- What condition marks an RX frame complete before FSM state 5 parses it?


## 2026-11-05 RX lifecycle answers and remaining limits

Resolved: the static condition for state-5 parser entry is now known for command IDs `0x1b` and `0x1d`: RX count >= 5 plus byte-0 header `0x5e`/`0x60`. The UART ISR itself does not supply a semantic end-of-frame signal.

Remaining:
- What protocol operations and external-device modes do IDs `0x1b`, `0x1d`, headers `0x5e`, and `0x60` represent?
- Which command/response path supplies signed values to each user-visible measurement mode?
- What frame-completion logic applies to descriptor IDs 09–0f and non-state-5 UART2 messages?
- What timer unit/clock source determines state-3 timeout behavior and actual UART baud?


## 2026-11-05 command-1b/1d questions

Resolved: '0x1b' and '0x1d' transmit '5e5e' and '6060' respectively, with matching state-3 reply-header gates. Both frames are unchanged in Beta3.

Remaining:
- What external protocol operation is represented by repeated '5e' or '60' bytes?
- Why does UART bring-up also emit '6060'?
- Which input-record/dispatcher case corresponds to each physical measurement mode?
- Which consumers use the state-5 signed result after the parser stores it?


## 2026-11-06 result-flow questions

Resolved: state-5 output fields are '+0x1c' (value/sentinel) and '+0x20' (selector) in object '0x805ac714'; ResultDispatch and two formatting candidates consume them. The ResultDispatch sentinel branch calls SoundControlGate.

Remaining:
- Which exact drawing/UI primitive consumes the prepared text from the two formatting paths?
- Which command/config condition selects the state-5 saturation path?
- Does the ResultDispatch-to-SoundControlGate path generate audible diode/continuity behavior, and under which proven input conditions?


## 2026-11-06 saturation-path questions

Resolved: control '+0x08' values '0x0d/0x0e' plus unsigned parsed value >= '0x1389' cause state 5 to publish sentinel '0x007fffff'. The visible code is identical in V3.8 and Beta3.

Remaining:
- What upstream input-record field supplies the case-2 control value, and which user-visible selection sets it to '0x0d' or '0x0e'?
- Does sentinel '0x007fffff' mean over-range, open circuit, or another protocol condition?
- Under what exact configuration does ResultDispatch's sentinel branch call SoundControlGate, and what output does that gate produce?

## Added 2026-11-06: V3.6 data delta

- What is the semantic role of the nine modified 32-bit cells at `0x80063aa8..0x80063ac8`? The surrounding `EnumKey*` text and a pointer load from `0x80042d98` establish a data-region association only; do not call it calibration, timing, key mapping, or an algorithm parameter without a consumer trace.
- Run and retain the V3.6 seeded PyGhidra inventory, then compare its known function windows against V3.8. Raw equality is a strong baseline, not a complete function-boundary proof.

## Added 2026-11-06: live-device boundary

- What are the non-main regions of the verified 16 MiB SPI backup: boot asset, persistent settings, calibration, log, or unused flash? Classify from image structure before treating any region as safe test storage.
- A full backup proves recovery capability, but what minimal reversible E2 instrumentation would record a useful parser, sound, or ADC event without overwriting calibration or boot data?
- If original V3.6/V3.8 physical behavior is required, which verified original package and complete flash layout are needed before replacing the currently confirmed E2-modified main image?

## Updated 2026-11-06: V3.6/V3.8 comparison status

- The first 13 bounded seed exports are identical V3.6/V3.8. Which unseeded functions reference the nine changed data cells near 0x80063ac8, and do they affect a user-visible behavior?
- Extend function discovery only from evidence-backed call/target seeds; do not turn equal bounded exports into a whole-image semantic proof.
- Passive UART-TTL capture remains a future high-value input when the adapter can be connected safely in normal firmware mode.

## Added 2026-11-06: sample-discard counter producers

- Locate every producer/reset of control byte `0x805aae8c+1` and the input events that initialize it. Bounded execution proves sample suppression, but neither mode nor a physical time unit.
- Which physical/protocol paths can deliver negative signed-24 values while control word +8 is 13/14? Synthetic execution proves sentinel replacement; reachability and user-visible effects remain unknown.
- Preserve the boundary of the new harness: state-3 frame admission, shared state-7 update, scheduling, and interrupts are not emulated.

## Updated 2026-11-06: discard count origin established

- The input dispatcher initializes count=2 in software cases 2/5; cases 3/4 preserve it. Which UI or upstream event producers submit these records? Start with record-building helper 0x80006778 and its callers, mapping r0→record word +0, r1→byte +4, r2→byte +5.
- How many terminal 0x1d response cycles follow the initial command list, and what drives their cadence? This is needed to translate two discarded responses into any physical latency.
- The task's direct case-2/5 blocks are excluded by the tested normal selection guard. Alternate entries and later indirect flow remain unproven.
- Direct literal tracing is not complete alias analysis: the UART startup-buffer candidate was rejected, and whole-object reset/clear paths remain to inspect.

## Added 2026-11-07: name the Buzzer branch setting

- Trace writers, default initialization and persistent loading of settings word 0x805ac788 (object 0x805ac770+0x18). Which setting label or action changes it?
- GUI callback and selection API choose the special (5,0x22,0x13) event only for exact value 1. Determine why it selects this alternate command list.
- Establish the API contract of queue boundary 0x80061acc before naming its r2 argument (0 for event 3, 10 otherwise).
- The 31 direct aligned ARM BL candidates do not cover Thumb or indirect event submitters. Keep unsupported call-graph coverage explicit.
- The helper initializes only record bytes 0..5; determine whether any other record fields are used downstream.

## Updated 2026-11-07: Fast CONT identified

The former naming/default/storage questions for 0x805ac788 are answered: Fast CONT, invalid-record default 1, CRC32-protected record at flash 0xf00000. The historical E2 snapshot has value 1 and valid CRC.

Remaining bounded questions:
- Follow the additional Fast CONT read at 0x80003878 in ResultDispatch: how does it change result-to-sound handling?
- Trace SoundControlGate 0x80006e4c through 0x800060d0 to the first peripheral-facing operation.
- What is the physical difference between the Fast CONT command list and the ordinary Buzzer list, and what drives their response cadence?
- When is settings save 0x800082c0 invoked after a UI change? The record format is proven, but the full save-trigger policy is not.
- Inspect later loader metadata updates and remaining settings fields separately; do not treat the whole 0xf00000 sector as classified.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

Resolved: Fast CONT result qualification, gate arguments, first peripheral-facing sound access and PWM-off semantics. Open: helper0x80007c88 three-slot history/range selection; fresh-response versus call cadence; actual clock/acoustic delay; user-visible labels for duty word +0x0c and sound-enable word +0x10. Modified nine-cell version data remains unclassified; it is not the PWM prescaler table.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

New reference track: resolve INTC vector/handler indirection around0x80005260/0x80005274 and timer setup around0x800071a8 using path-aware CFGs and original-code tests. Validate reference inconsistencies against exact-chip documentation. Extend comparison to resolved literal values and relocation targets, genuine boundaries, Thumb and indirect calls before strengthening identity claims. Current normalized/masked comparison finds no accepted candidates among97 functions per image. Preserve the pending Fast CONT helper0x80007c88 task and physical-cadence/acoustic-delay questions.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

Resolved: INTC vector dispatch/registration, exact timer-configure entry, startup register programming, timer0 status helper, and the Fast CONT history/retained-median algorithm. Still open: original power-on filter state; source scalar's unit; how each helper call relates to new UART data; tick/scheduler internals; FSM+0x30 timing semantics. The alternate registration table's role is unassigned. The nominal timer period is not a live baud/cadence/acoustic measurement.

Next bounded investigation: Trace fresh-result admission from ResultDispatch call0x80003970 into helper0x80007c88. Determine whether repeated calls can reuse one parsed UART result. Separately bound tick/scheduler0x80061fa4/0x800612f8 and the consumer/decrement of FSM field0x805ac694+0x30 before assigning timing units.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

Resolved in the scoped model: refresh calls can reuse a stored result; UI warmup and parser discard counters are independent; actual caller arguments are0..999; rejected/sentinel results bypass history reset. Open: real renderer/queue effects on this state and live scheduling/freshness. UI notification states1/2 and factory history initialization are not covered.

An inspected static FSM reader is now located at0x800044a8: LDR r5,[r1,#0x30], with r1=sb via ADD#0 at0x8000449c. The older simple-MOV literal tracer's bounded negative result was not a global absence proof. Its timing consumers are not executed in this run.

Next: Audit real renderer0x8000326c and enqueue path0x80006778 for side effects excluded from the refresh model. Then prove FSM+0x30's cached read at0x800044a8 (r1=sb via ADD#0), its elapsed-tick comparisons and tick getter0x80061f84; do not assign milliseconds before that contract is validated.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

Resolved in the new bounded scope: real available-queue send/copy and renderer-state code preserve the repeated-result example; queue init requests10*68-byte slots; critical nesting/IRQ-mask behavior is executed. Still open: timed full queues, waiting-task wakeups/context switches, real heap behavior, remaining graphics/text/log leaves and live timing.

Next: Prove FSM+0x30's cached reader0x800044a8 through r5 and elapsed-tick branches0x800046a8/0x800046c4/0x80004720 using real getter0x80061f84 and the verified critical helpers. Test threshold boundaries and32-bit tick wrap before assigning units or interpreting Beta3's30-to40 change. Keep blocked queues, waiters and remaining GUI/log leaves separate.

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

Resolved within the tested originals: +0x30 is a cached deadline duration for the
three wait branches; +0x2c is its start snapshot; equality expires; subtraction
uses unsigned modulo32. A complete state3 reply is checked before the deadline.
The real getter's counter, critical protection, setup durations and conditional
ACK settling durations are now executed, with an independent C reconstruction.

Still open: physical counter frequency; actual FSM task-loop cadence; complete
tick wrap-list/ready-list scheduling; real send completion/arrival timing;
state6 retry cadence; live concurrent RX publication; actual modified Beta3
behavior. Cache intervention is a host experiment, not a proven race.

Next reserved task COORD-ADC-CADENCE: Validate the MainADCTask candidate 0x80005a78 and actual callers of FSM 0x80004490; bound one task-loop iteration and the delay candidate 0x80060fbc before assigning a polling cadence. Keep GUI callback periods, live clock frequency and acoustic latency separate.


## 2026-11-08 continuation

The original GaugeCmdTask wrapper is0x80003dbc;0x80005b6c remains a service candidate, now linked to that wrapper. COORD-ADC-CADENCE should trace service/FSM/delay placement without assuming that the separate MainADCTask candidate is the diode UART-result producer. Global writers/readers outside the six-packet index remain incomplete. Base+highspeedv2 physical latency, clock units and modified-build provenance are unresolved. Full context improved this small instruction lookup test, not overall project completion. Do not repeat the22 cutoff historical replies or already reviewed comparison tasks.


## 2026-11-08 public-input support / profile checkpoint

The private Beta3 full-backup prerequisite is removed for the two pinned factory applications. Other application hashes remain unsupported pending evidence; request only the inspect text, not personal backups. Mr.Yang-updater installation, V3.6 physical behavior and unknown bootloaders remain unverified. E2 profile input b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1 matches its local manifest; source reproduction and the equal-Highspeed event matrix are still required. No Base-versus-Direct/Auto/Ready cause or new offline speed fix is established yet.


## 2026-11-08 installer boundaries and research continuation

The English self-contained Release is public; no manual firmware dump is needed in its normal workflow. Physical validation of the new beta installer/FEL binary, real USB-driver setup, and GUI visual verification remain unestablished. Simulation, compiled-resource/Tcl and runtime-component checks passed. A local LLM extraction request timed out after45s; no draft or claim was accepted. The E2 build reproduction and equal-Highspeed active/requested-profile event matrix are still outstanding; resume the pinned COORD-ADC-CADENCE checkpoint.


## 2026-11-08: equal-Highspeed profile evidence

The equal-Highspeed matrix and public recorded-edit reproduction are complete for pinned E2. The reported physical Base+highspeedv2 advantage remains unresolved: installed-image identity, external conversion response/restart behavior, real task order/counter rate and short-tone audibility are missing. The immediate-responder model favors Direct sound initiation and reveals shorter Auto/Ready pulses. Do not change ADC deadlines or add an OPEN tone hold from that hypothesis. Historical source generators and full transitive caller/global/indirect-call coverage remain unverified. See contributions/COORD-ADC-CADENCE/STATUS.md.


## 2026-11-09: original UART correlation proof

Original UART framing/ready polling and ISR append are now dynamically checked, with independent C/Python agreement. The same-header late-response counterexample is proven for controlled original-code schedules, while real frequency and ADC restart/buffering remain unknown. Next inspect count/read/parse stability between state3 admission and state5, and actual callers of synchronous helper0x80005f14 before claiming a feasible shared-buffer clear race. Its clear anchors are prepared as a static source index. The reported physical Base advantage and installed application identity remain open. New local-model RX/synchronous indexing jobs are frozen but encountered a refused localhost API; do not treat their failed responses as results.


## 2026-11-09: admitted-frame stability and caller ownership

Admission-to-parse append stability is now bounded; known synchronous call ownership is better classified, including a previously absent tail edge0x8000404c→0x80005f14. A shared RX pointer alone is insufficient to claim a feasible live clear race: tested service paths gate fallback entry on idle. Next execute the synchronous helper for reachable command/caller preconditions and trace actual producers/other aliases before claiming system-wide exclusion. External ADC restart/buffering, installed identity and physical Base advantage remain unresolved. The existing local-model service issue has not been re-polled or presented as a new failure.


## 2026-11-09: local model restored and startup-helper execution

The local API availability question is resolved: the existing portable runtime/models were found under the legacy project's local-ai directory and the hidden loopback server was started. No reinstall/download was needed. Synchronous helper execution is now bounded for the two proven startup arguments9/19, including header-only success and final-sleep ordering. Remaining work: other reachable deferred-handler command arguments/message producers, buffer aliases/global ownership, installed-meter identity and external conversion/physical timing. One local-model semantic error was caught despite exact source grounding; further local work stays small and reviewed.


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

The four tested producer-bound paths now have 16 original ARM926 cases across V3.6/V3.8. Next trace the `0x28`/`0x29` producers at `0x8000e50c`/`0x8000e5a0` through the handler's extended path beginning at `0x80003eb8`. The longer status loop, type-6 producer reachability, indirect aliases, real scheduling and external ADC behavior remain open. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json).

## 2026-11-09: extended deferred status

The `0x28`/`0x29` replay establishes the ACK/status split and the local status write contract. The consumer of `0x805ab920`, the type-6 producer and external peer semantics remain open. Next validate the reader candidate at `0x8005dac4` reached via the literal load at `0x8005dabc`. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

The [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json) binds the status consumer and the two UI producers. The [producer index](contributions/COORD-ADC-CADENCE/synchronous/control-producer-index.json) lists 31 aligned immediate ARM branch candidates per original, with local type arguments 0–5. Type-6 reachability through alternate queue writers or indirect code remains open, along with full hardware calibration behavior.

## 2026-11-09: original control queue and type 6

The [queue reference index](contributions/COORD-ADC-CADENCE/synchronous/control-queue-index.json) finds one immediate direct call to the task-context send routine `0x80061acc`, at `0x800067b8`, across the aligned ARM B/BL and ARMv5 Thumb BLX scans. The [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json) establishes type-6 behavior after host injection. Native type-6 creation, synthesized/indirect calls and alternate writer routines remain open.

## 2026-11-09: dynamic type-2 selection and compiled plan

The [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json) binds a writer of the dynamic UI byte and verifies the complete clamp. Other writers and the physical behavior selected by UART descriptors `0x13..0x19` remain open. Test a complete type-2 configuration followed by native refresh-produced type-3 requests to link the discard counter to the first fresh publication.

## 2026-11-09: refresh and first publication

The [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json) closes the tested configuration-to-first-publication path. Next execute the downstream `0x800037c0` conversion and `0x8000326c` renderer on these same schedules and separate the actual rendering outcome from the stored-result read. Peer conversion, physical timing and complete scheduler behavior remain open.

## 2026-11-09: refresh rendering and sound

The [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json) links a single publication to three Fast CONT updates in a controlled mode-4 fixture. Next trace native mode entry and filter-reset writers, then test which transitions actually invalidate the prior stored result. Numeric string conversion and final widget updates are modeled in this replay.

## 2026-11-10 — Native mode entry and sound expiry

Follow the first two original refresh callbacks after native mode 4 entry, with absent and valid replies, to determine when retained history influences sound before fresh publication. The aligned literal scan covers named state pointers only. Synthesized aliases and paths in other tasks remain open. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).

## 2026-11-10 — First refreshes after native Fast CONT entry

Test the ordering of the original measurement-task countdown and the UI timer refresh around expiry. Measure the modeled countdown reload and duty shadow in both orders. Native scheduling interleaves, peer internals and physical time remain open. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-first-refresh-validation.json).

## 2026-11-10 — KeyTask and Fast CONT refresh ordering

Execute `0x80060fbc` and its original queue/yield paths under known scheduler preconditions. The KeyTask loop supplies argument 50 at `0x80005534`. The KeyTask and timer ordering fixture leaves preemption, clock units and acoustic timing open. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/key-task-fast-cont-order-validation.json).

## 2026-11-10 — Scheduler delays and task wakeup

Run the original interrupt vector and tick branch under controlled interrupt-controller and saved-context fixtures. The static binding at `0x8000232c` loads `0x80061fa4` from `0x800023a8` before the indirect call at `0x80002334`. Clock units and actual device cadence remain open. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-delay-wake-validation.json).

## 2026-11-10 — Installed vectors and scheduler context

Join the original Timer0 startup configuration to the installed vectors and pending-bit routing in one replay. Bind the ordinary IRQ vector handler and Timer0 tick branch under distinct pending states. A 24 MHz source and physical interrupt timing still require independent evidence. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-context-validation.json).

## 2026-11-10 — Timer0 and UART2 through the installed IRQ route

Drive the original queue/service loop as a scheduled task so the original wake/IRQ paths replace direct host FSM calls. Continue tracing fallback `0x80003dd8` and helper `0x80005f14` with proven producers and idle conditions. Mixed-pending hardware arbitration, peer internals and physical timing remain open. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-irq-validation.json).

## 2026-11-10 — Scheduled GaugeCmdTask service and fallback

Continue through the original longer-delay fallback branches, including the 200-count type-0 wait or the 600/500-count type-1 path. Bind reachable producers and track which UART replies are consumed. External peer conversion and physical latency remain open. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-service-validation.json).

## 2026-11-10 — Scheduled long fallback and status waits

Run calibration timer `0x8005da88` against status written in the same scheduled execution, including while the status wait is in progress. The existing UI evidence uses explicit status snapshots. Peer conversion, later status schedules and physical timing remain separate questions. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-long-fallback-validation.json).

## 2026-11-10 — Live calibration status and UI timer

After the original calibration reset stores, exercise the zero-status and zero-flag UI callback through the real measurement queue in the same emulator. Keep hardware timing and peer conversion outside the software proof. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration reset to fresh measurement

Exercise the full original calibration button callbacks at `0x8000e4c8` and `0x8000e55c` through their original queue drain when a measurement or another calibration request is already queued. Preserve separate external peer and physical timing questions. [Shared ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration buttons and pending queue

Trace indirect producers and alternate queue primitives for the still-host-supplied type-6 record. The direct producer index at `0x800067b8` alone cannot establish native type-6 reachability. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-button-queue-validation.json).

## 2026-11-10 — Queue entry candidates and full-queue waits

The raw candidate `0x8009ef10` decodes as an interior branch. Its surrounding bytes and raw inbound candidates lack a proven executable path. Native type-6 reachability and indirect or inlined queue writers remain open. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/queue-interior-full-validation.json).

## 2026-11-10 — Direct control producers and result-block writer

The bounded direct caller suffixes emit types 0–5. Indirect and synthesized producers, the `0x80046548` field signature and native type-6 provenance remain open. The original `0x8005d35c` writer targets the result block on the tested path. [Factory hashes, original bytes and ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-producer-suffix-replay.json).

## 2026-11-10 — GUI field provenance at 0x80046548

The two non-queue field-signature candidates now have bounded original execution evidence. The raw `0x8009ef10` match falls inside a factory glyph bitmap verified by original lookup. Synthesized or register-indirect handle aliases and native type-6 record creation remain open. [Original replay, instruction bytes and firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/gui-field-provenance.json).

## 2026-11-10 — Registered GUI callbacks and indirect queue producers

The first GUI table resolves ten concrete register-indirect producers. The second block resolves the event-to-record path of `0x8000d294` for eight binary flag combinations. Other callbacks, synthesized control-queue aliases and native type-6 creation remain open. [Original instruction bytes, factory hashes and replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-event-validation.json).

## Diode/Buzzer continuation (2026-11-11)

Trace the writers of 0x805ac788 and verify the enabled 0x8005f254 route from the registered 0x8000cfd0 callback with realistic queue preconditions. Keep other indirect sends and native type-6 provenance open. [Bounded ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

## Secondary channel continuation (2026-11-11)

Trace the device-ready and busy-clear producers for 0x805aac40 and 0x805aac70. Replay the original 0x8005fc08 channel-1 sender with bounded modeled peripheral state. Keep native type-6 provenance open. The register and actual timing remain outside the current replay. [ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).

## Secondary USB receive continuation (2026-11-11)

Replay the original mode-1 USB RX endpoint through 0x800603f4 and 0x800606e0 to verify FIFO copy, guard-word initialization and RX status handling. Then trace the mode-1 producer paths that originate native type-6 control-queue records; keep hardware timing open. [Verified TX and IRQ boundary](contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-lifecycle-validation.json).
