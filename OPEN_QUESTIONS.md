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
