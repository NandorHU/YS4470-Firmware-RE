# Measurement algorithms

## Parsed measurement frame (confirmed static behavior)

At `0x80004738`, the parser constructs a 24-bit little-endian value from frame bytes 1–3 and sign-extends it if bit 23 is set. It reads a code from byte 4, limiting normal codes to 6; a control path treats `0x1b` specially. The parser writes output fields under `0x805ac714`. For selectors `0x0d`/ `0x0e`, unsigned values at or above `0x1389` are stored as sentinel `0x007fffff`.

The physical quantity, scale, and whether 5001 is an overload threshold remain unknown.

## Diode / continuity sound path

The established result-branch call site is `0x80003a74`, which calls `SoundControlGate` at `0x80006e4c`. Beta3 replaces the factory selected sound-table halfword at `0x80006e80` with helper `0x80010754`. The helper applies `0x529` only when called from return address `0x80003a78`.

This is evidence of a diode/continuity-branch sound-parameter adjustment. It is not evidence yet of physical frequency, duty cycle, timer period, perceived loudness, or reduced delay. The next analysis must trace the remaining FSM changes and the lower sound routine before any latency claim.


## Beta3 FSM phase-3 selector (confirmed static control flow)

In the command path that stores FSM state 5 and then state 3, V3.8 writes `0x1e` to the FSM object's `+0x30` field. Beta3 calls `0x80058750` instead. The helper reads bytes at offsets 0, 7, and 2 of `0x805abefc`; it yields `0x28` exactly for `(3, 0x0e, 1)`, otherwise `0x1e`. The caller stores the result at `0x805ac694+0x30` and sets FSM state 3.

The nearby FSM also writes 0x50, 0x32, or 0x64 to the same field, supporting a phase-budget/interval interpretation. It does not establish the tick unit, nor whether this affects diode/continuity audible latency.


## FSM field-usage result

The phase-3 selector output is stored at `0x805ac694+0x30`. Direct static tracing establishes initialization/reset sites, but not a direct reader: 80 is written on one command path, 30/40 before state 3, 50/100 on a later reply path, and TransactionBuilder clears the field. The nearby driver task reads `+0x34`, not `+0x30`.

Consequently, the field is still an interval/budget candidate rather than a proven timer. This result rules out a direct, locally visible countdown load but not consumption through callbacks, aliases, or another task.


## Command-dependent PIO selection

Before the send routine at `0x80005e84`, FSM state 1 indexes descriptor table `0x8006367c` with command ID. For IDs `0x0b..0x0f`, it sets PIO bit 3 and clears bit 2; for IDs `0x09..0x0a`, it clears bit 3 and sets bit 2. TransactionBuilder initially clears both.

This is a concrete range/mode-control candidate, but command IDs have not yet been mapped to physical measurements. It must not be labeled as diode, continuity, or autorange control until table payloads and board wiring provide evidence.


## Static command framing for IDs 09–0f

For the command IDs associated with the two observed PIO patterns, the table stores two source bytes. The send helper appends the modulo-256 sum of those bytes:

| ID | Source | Checksum | Wire frame |
|---:|---|---:|---|
| 09 | `58 03` | `5b` | `58 03 5b` |
| 0a | `58 04` | `5c` | `58 04 5c` |
| 0b | `58 01` | `59` | `58 01 59` |
| 0c | `58 07` | `5f` | `58 07 5f` |
| 0d | `58 09` | `61` | `58 09 61` |
| 0e | `58 0a` | `62` | `58 0a 62` |
| 0f | `58 0b` | `63` | `58 0b 63` |

V3.8 and Beta3 produce identical frames for all seven IDs. Their physical measurement-mode meaning remains unknown.


## Measurement command/response transport

The command frame built by `0x80005e84` is sent byte-by-byte through UART2. The send primitive waits on `UART2+0x7c` bit 1, then writes to `UART2+0x00`. RX ISR `0x800073bc` receives from the same UART2 base and appends bytes to the parser buffer.

Thus the FSM's descriptor command, PIO selection, and response parser form one static UART2 transaction path. No baud, framing, or response-to-command mapping is claimed yet.


## UART2 transaction bring-up

Before regular command frames, the firmware initializes UART2 and transmits two startup bytes `60 60`. It supplies a baud argument of 19200 to the divisor calculation and programs `0x0249` into the UART divisor latches. The PIO mux path sets PE7/PE8 to function 3, consistent with UART2 TX/RX.

This establishes a configured UART2 command/response link, not the semantic meaning of `60 60` or the external device protocol reset behavior.


## State-5 measurement-value admission

The signed-24-bit parser at `0x80004738` has a now-proven entry gate, but only for transaction command IDs `0x1b` and `0x1d`.

1. State 1 sets required RX count to 5 and enters state 3 for these command IDs.
2. State 3 waits until `0x805ab938 >= 5`.
3. It requires RX buffer byte 0 to be `0x5e` for `0x1b`, or `0x60` for `0x1d`.
4. It then enters state 5, which constructs a little-endian signed 24-bit value from bytes 1..3.

The rule has not been demonstrated for descriptor IDs 09–0f or for other UART2 messages. Header bytes and command IDs are protocol facts, not yet names of diode, continuity, voltage, or any other physical measurement.


## Wire frames for state-5 command paths

| Command ID | Source bytes | Checksum | UART2 wire frame | State-3 expected header |
|---:|---|---|---|---|
| '0x1b' | '5e' | '5e' | '5e 5e' | '5e' |
| '0x1d' | '60' | '60' | '60 60' | '60' |

The direct descriptor result is identical in V3.8 and Beta3. Static dispatchers select these IDs in several software cases, but those cases are not yet correlated with rotary-switch positions, UI labels, diode/continuity behavior, or ADC modes.


## State-5 result publication and consumers

After state-5 admission, the parser publishes its signed 24-bit value at result object '+0x1c' and a byte-4-derived bounded selector at '+0x20'. For a special threshold path it publishes '0x007fffff' instead of the parsed value.

ResultDispatch consumes both fields and has a sentinel branch that calls SoundControlGate. Separate text-formatting candidates also consume them, including one with a nearby '%.3f' format string. This connects parser output to presentation/control software without assigning a physical unit or measurement name.


## State-5 saturation rule

For the visible state-5 path:

1. Read control word '0x805aae8c+0x08'.
2. Continue with saturation only if it is '0x0d' or '0x0e'.
3. Compare the parsed signed result as an unsigned value to '0x1389'.
4. If it is greater than or equal, publish sentinel '0x007fffff' and selector 0; otherwise publish the normal parsed value and selector.

Case-2 command setup supplies the control word from an input-derived value and includes terminal command '0x1d'. This is a reproducible software relationship, but input/command names and physical electrical interpretation remain unknown.

## 2026-11-06 V3.6/V3.8 algorithm baseline

Raw comparison of the two original releases found no changed instruction bytes. The only payload-data delta is nine unclassified 32-bit values at `0x80063aa8`; consequently this evidence neither proves a measurement-algorithm change nor rules out a behavior change caused by configuration data. The previously recovered UART2/FSM/result rules are byte-identical candidates for V3.6 pending a seeded PyGhidra export.

## 2026-11-06 active-hardware scope correction

The currently flashed device image is confirmed as modified beta-diode-profiles-e2, not an original V3.6/V3.8 image. Any future physical measurement observation from this device must be labelled **E2-modified build** unless the verified original image is deliberately restored. The FEL backup provides recovery evidence; it does not itself expose ADC, diode, continuity, or buzzer runtime values.

## 2026-11-06 original-version comparison scope

The bounded PyGhidra V3.6/V3.8 comparison found identical exports for the currently seeded MeasurementFSM, MainADCTask_candidate, DiodeValidityBranch, ResultDispatch, SoundControlGate, UART_RX_ISR, and related support regions. Therefore no algorithm change is evidenced for those bounded code bodies. This does not classify the nine changed data cells or establish physical measurement equivalence.

## 2026-11-06: executable state-5 reconstruction

Executed the original 34-instruction parser slice against its high-level arithmetic reconstruction on Unicorn ARM926 in V3.6 and V3.8. All 5,952 cases passed, covering signed-24 boundaries, 5000/5001, selector 6/7, all selector bytes, all byte-valued control modes and countdowns, and 512 deterministic random cases per version.

The exact publication rule is now:

1. Decode signed little-endian 24-bit value; use selector 0 for command 1b or min(RX[4],6) for command 1d.
2. If control byte +1 was nonzero on entry, decrement it and retain the prior published value and selector. Entry value 1 also discards this sample.
3. Otherwise, control word +8 of 13/14 replaces every value whose **unsigned 32-bit representation** is >=5001 with 0x007fffff and selector 0. This includes every negative decoded value.
4. Other cases publish the decoded value and selector.

The counter's physical meaning and initialization are unresolved. These synthetic tests do not prove that every tested input tuple is reachable in normal operation or identify units, ADC conversion, or audible timing. Evidence: [state-5 ARM926 experiment](evidence/2026-11-06-state5-arm926-emulation.json).

## 2026-11-06: discard-window initialization and publication sequence

Input-dispatcher cases 2 and 5 initialize the discard count to two. Case 2 passes commands [input byte 4, normalize(input byte 5), 0x1d] and writes input byte 4 to control +8. Normalization retains 0x13..0x18; all other byte values become 0x19. Case 5 writes control 0x22 and passes [0x0c,0x22,0x13,0x1d].

Persistent execution confirms the sequence count 2→1 (old result retained), 1→0 (old result retained), 0→0 (publish), then another publication on the fourth admitted state-5 entry. This was checked across 96 scenarios, including threshold and negative values. Cases 3/4 preserve the existing control fields in the tested input dispatcher.

The task normally defers cases 2/5 before invoking this dispatcher later; its duplicate stores must not be treated as ordinary immediate routing. Whether sample suppression serves analog settling remains a hypothesis. The tests do not establish physical modes or delay in milliseconds. Evidence: [lifecycle report](evidence/2026-11-06-state5-discard-lifecycle.json).

## 2026-11-07: Diode/Buzzer UI-to-parser route

The established count=2 path now has a static GUI source:

| UI-associated branch | Setting word 0x805ac788 | Record (word +0, byte +4, byte +5) | Dispatcher command list |
|---|---|---|---|
| Diode tail | any tested value | (2,0x0e,0x19) | [0x0e,0x19,0x1d] |
| Buzzer tail | not equal to 1 | (2,0x0e,0x19) | [0x0e,0x19,0x1d] |
| Buzzer tail | exactly 1 | (5,0x22,0x13) | [0x0c,0x22,0x13,0x1d] |

The event-record builder and the selected GUI tails execute original ARM instructions; decoded records are then handed to the already tested dispatcher and parser harness. Both dispatcher lists set count=2, so the first two admitted parser entries retain the previous result. Control +8 is 0x0e for the first route and 0x22 for the special Buzzer route; this also changes whether the unsigned saturation gate is eligible.

This is a verified software route with UI-label association. Queue transport, complete GUI dispatch, physical mode behavior, sample cadence, and acoustic latency are not measured. The flag is intentionally not called a speed, calibration, or buzzer-enable setting until its writers are recovered.

## 2026-11-07: name and persistence of the Buzzer branch flag

The selector previously described only as settings word 0x805ac788 is **Fast CONT**. Its GUI handler reads widget state bit 0, stores normalized 0/1, and invokes the sound gate for UI feedback. The invalid-settings default is 1, and the historical E2 backup also stores 1 with valid CRC.

Fast CONT=1 selects Buzzer event (5,0x22,0x13), yielding command list [0x0c,0x22,0x13,0x1d]. Fast CONT=0 selects event (2,0x0e,0x19), yielding [0x0e,0x19,0x1d]. Both feed the already proven two-response discard rule; naming the option does not establish the latency of either path.

Configuration uses a 72-byte record with CRC32 over the first 68 bytes and checksum at +0x44. Independent zlib calculation matches the original CRC loops; 144 single-bit-damaged records were rejected across the two originals.

An edge distinction is preserved: valid CRC does not impose a 0/1 field range. Synthetic stored values 2/0xffffffff restore a checked widget, but the Buzzer consumer requires exact 1 for its special route. Normal checkbox interaction normalizes the value. The observed device snapshot has the canonical value 1.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

Tone requests use table [2000,2222,2444,2666,2888,3110,3332,3554,3776,4000]. period_ns=floor(1e9/frequency); duty uses signed half-setting and original float32 rounding. For selector5/setting90: 2888Hz requested, period346260ns, duty155816ns. Off sets duty0; it does not clear PWM enable. Result qualification and sentinel-off (0,0) call setup are executed; measurement thresholds, formatting and helper0x80007c88 are outside this experiment.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

Reference matching adds hardware-context leads, not new measurement-ADC semantics. UART2 remains the evidenced measurement transport; KEYADC/RTP references do not establish an internal converter role. The completed parser, Fast CONT setting, sound/PWM and new watchdog experiments are separate bounded proofs. Fast CONT helper0x80007c88 history/range-selection reconstruction remains pending; no millisecond/physical latency is assigned.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

Fast CONT helper0x80007c88 writes a three-value ring; input>1000 resets fill to0/history to1000/median to-1 without resetting the index, then inserts that input. Valid count0 requires three calls before median recalculation. With full history, signed min/max products are compared as unsigned64 values: low*120 >= high*100 in their two's-complement representations. On pass, median-of-three replaces the stored median. On fail, the previous median remains.

Selectors from the retained value:0..19→10,20..39→8,40..59→6,60..79→4,80..99→2; other/unmatched values request off. Each call tailcalls the separately proven sound gate; its settings enable and active-state behavior still apply. The physical scalar unit is unassigned.

Persistent example: stable[5,5,5] establishes selector10; the first two subsequent500 inputs retain that tone, the third establishes median500/off. Alternating500/5 preserves the previous tone through the tested16 unstable inputs. Input1001 resets immediately;1000 takes the regular ring path. There is no independent expiry of the retained median in this helper.

Own C component: `reconstruction/fast_cont.c` / `.h`, no board SDK/libc/peripheral access. Compiled ARM926 C, independent Python and original ARM agree after every tested input, including every history field and full original sound/PWM effect. Contract: index0..2/count0..3. The earlier two-discard parser lifecycle must not be converted into an additive millisecond delay without proving fresh-result coupling.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

The callback at0x8005d048 queues event4 for config0x22, independently of a new result. After UI warmup byte+9 reaches2 it calls ResultDispatch. The parser's discard byte is a different address and is not consumed by this path. With stored raw14023 and no parser step, five callback invocations give filter fills0,0,1,2,3 and retained median5/on. Thus three filter calls cannot be counted as three newly published UART samples.

An interleaved admitted-command0x1b sequence proves discard2→1→0 preserves the previous result while callbacks continue filtering it. The next parser entry publishes raw1402300; three callback uses of that one stored publication establish median500/off. The tests do not model an actual UART ISR, queue delivery or scheduler.

Caller conversion: float32(raw)/float32(2804.60009765625), observed negative-bit clamp, reject>=1000.0, then truncate accepted values to0..999. Raw2804600 produces999 after the actual float32 path;2804601 is rejected. The0x007fffff sentinel also bypasses the filter. Both off paths preserve its prior history/median, so returning to an accepted value can reuse that retained state on the next call. This qualifies the earlier standalone helper result: its>1000 reset exists but this accepted caller path does not reach it. Source scalar units remain unassigned.

Renderer/queue/printf/creation side effects are API boundaries. The original memclr, numeric conversion, parser slice, filter and sound/PWM instructions execute. No additive two-discard+three-new-sample or millisecond latency formula follows.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

The freshness counterexample now survives original renderer-state and queue-copy execution. In five callbacks, five event4 records are copied to the factory-sized queue; no receiver/parser task is run. Stored raw14023 and discard2 remain unchanged while filter fills[0,0,1,2,3] and retained value5 enables the emulated sound path. An enqueued request is distinct from a published measurement.

The renderer's direct state and helpers preserve UI warmup+9, parser discard+1, raw result/selector, Fast CONT active/index/count/median/history and RX bytes in1152 states per original. Mode0/1/3/4, UI+3 flag, record+0x40 flag, saved-mode match, counters and cold/full auxiliary histories are varied. The raw UI flags are not assigned unproven menu names. Renderer-owned memo/four/eight-value storage changes independently of the Fast CONT ring.

Graphics/text/log leaves and heap allocation remain models. Waiting-task, blocking-queue and asynchronous UI effects are not covered. The C filter component is unchanged; this run strengthens its caller/context evidence rather than claiming a complete GUI or firmware reconstruction.

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

The original FSM caches start and duration at entry and computes
uint32(now-start) >= duration using the real tick getter.

| State/path | Before expiry / admitted input | On expiry |
|---|---|---|
| 2, no positive RX count or wrong expected header | Retain state2 | Set state6 |
| 2, expected header for command9..15 | Record new start; state4, duration100 for13/14 or50 otherwise | Prior deadline is not consulted on that admitted branch |
| 2, expected header for other tested commands | Clear PIO bits3/2, advance index, clear retry, state1 | Prior deadline is not consulted |
| 3, insufficient signed RX count | Retain state3 | Set state6 |
| 3, sufficient count | Header0x5e for0x1b /0x60 for0x1d admits state5; mismatched header sets6; other tested selectors admit5 | Complete-frame branch does not call the getter |
| 4 | Retain state4 | Clear PIO bits3/2, advance index, clear retry, state1 |

State1 after the UART-send call captures a tick snapshot. Commands0x1b/0x1d set
required length5 and duration30, then state3; other tested commands set expected
header from the TX table and duration80, then state2. No new parser data is
invented by these transitions; state5 parsing runs on a subsequent invocation.

Across both originals, 12,914 state cases agree after every step between original,
Python and compiled C. Synthetic signed-length/index boundaries do not assert
that extreme RX counts are physically reachable. Setup, getters and cache
interventions have separate check counts.

For incomplete state3 replies, a duration40 fixture retains state3 at elapsed30
and39 where duration30 selects6; both expire by40. A complete, valid reply can
still be admitted without waiting for the budget. This is a conditional grace
window, not an unconditional ten-tick delay. The actual Beta3 image was not
executed, and no conversion to milliseconds follows.


## 2026-11-08: GaugeCmdTask outer wrapper

Original entry0x80003dbc is bound to GaugeCmdTask by the startup argument setup. Its outer wrapper calls0x80005d24, calls0x80005f14 with9 then19, and loops over service0x80005b6c. Two loop iterations execute with return-only callee models in both originals. This does not prove measurement-command completion, service/FSM timing or Base+highspeedv2 physical performance. See contributions/COORD-FUNCTION-PACKETS/validation.json. Reuse the full local CFG packets for the reserved service/FSM/delay trace.


## 2026-11-08 distribution scope

The factory-input patcher applies the already published1.0 application changes. It does not add a new measurement-speed algorithm or establish why Base+highspeedv2 is perceived faster than other profiles. V3.6's differing factory bytes stay unchanged. Continue the hash-pinned E2 service/FSM/event analysis from contributions/COORD-ADC-CADENCE/STATUS.md.


## 2026-11-08 distribution milestone

Installer1.1.0-beta.2 prepares/installs the existing1.0 application using the bundled originalV3.8 or a matched device application. It adds no new measurement algorithm, profile policy or physical speed result. V3.6's version-specific bytes remain intact under the guarded port. The Base+highspeedv2 versus Direct/Auto/Ready question remains with COORD-ADC-CADENCE.


## 2026-11-08: equal-Highspeed profile evidence

At equal Highspeed=1, Base/Direct share poll times; Direct moves audio from the next GUI stored-result callback to accepted-frame handling. In one modeled OPEN→contact case acceptance is106 for both, sound125/106 respectively; renderer125 for both. Auto/Ready poll more often and can shorten the brief-contact sound-control pulse (ON/OFF110/118 and107/113 versus Base125/150). This is a possible perception-related mechanism, not a proved physical explanation. Header rejection, incomplete deadlines, holdoff drops and busy GUI-poll drops are counted separately in contributions/COORD-ADC-CADENCE/profile-validation.json and traces/.


## 2026-11-09: original UART correlation proof

A newly executed original retry sequence on both versions admits a deliberately old same-command frame: request0, incomplete deadline30, retry selection31, RX clear/resend32, old frame33..37, raw50 publication38. Counter values are synthetic. A cross-command0x5e frame in a0x1d transaction rejects; the tested path distinguishes command header, not request instance. Concatenated frames publish only the first; the trailing frame is lost at the next state1 clear. See contributions/COORD-ADC-CADENCE/uart/validation.json. No timing/correlation patch is justified without actual external-response semantics.


## 2026-11-09: admitted-frame stability and caller ownership

Original state3-admitted frames retain their first five bytes through state5 while the original ISR appends at five controlled positions, including between value-byte reads.1,200 cases match the previous independent parser contract, including saturation/selector limits and buffer-cap crossing. Thus an append-only ISR alone is not a demonstrated prefix-corruption cause.24 service cases and classified known call sites also do not demonstrate an active-acquisition clear race from the synchronous helper. The earlier delayed matching-header acceptance remains a separate, valid counterexample.


## 2026-11-09: local model restored and startup-helper execution

Synchronous startup helper0x80005f14 accepts a matching first-byte ACK immediately for tested IDs9/19; its500 constant bounds per-attempt check/sleep iterations, not a mandatory delay.40 original-code cases verify immediate/wrong/missing/late/second-attempt replies, at most two sends and up to1,000 requested sleep(1) calls. A header arriving after the final sleep can miss the last check. Keep this startup ACK contract distinct from the asynchronous measurement FSM's five-byte parser admission. No physical time unit or Base-profile cause is inferred.


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

With the FSM idle, type 0 requests `sleep(200)` at `0x80004038` before the `0x26` tail call. The three tested type-1 paths enter the helper directly via `0x80003eac`. Across 16 V3.6/V3.8 ARM926 cases, a matching first byte gave success with zero helper sleeps. No reply produced two sends and 1,000 requested helper sleeps. The sleep arguments describe the software path. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json).

## 2026-11-09: extended deferred status

A successful `0x28`/`0x29` helper ACK reaches two RX clears followed by a status loop with up to 230 requested sleep(1000)/check iterations. At `0x80003f68`, the loop reads RX byte 0. A recognized `a0`/`a1` header takes the `0x26` exit even if its second byte maps to no status. An unknown first byte remained in place under modeled append-only arrivals, so later valid bytes did not exit the loop. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

In the [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json), status 0 with the control flag set shows `Calibration ...` and keeps the initial timer period of 2000. Codes 1–7 show result text and set period 200. With both words zero, the callback queues a type-3 request and the raw-sentinel fixture produces `.OL`. The original due gate was exercised one counter unit before and at each deadline, including wrap.

## 2026-11-09: original control queue and type 6

Original queue order controls admission in the [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json). A type-3 or type-4 record ahead of a synthetic type-6 record starts the measurement builder, deferring type 6 until the FSM is idle. If type 6 arrives first, the pending flag blocks the later immediate record. Two deferred records occupy one pending slot after queue drain, so only the last reaches the fallback in the tested orders.

## 2026-11-09: dynamic type-2 selection and compiled plan

The type-2 dispatcher at `0x80004390` preserves record byte +5 in `0x13..0x18` and selects `0x19` otherwise. The [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json) checks all 256 bytes on each original through the second UART send. The [compiled-plan differential](contributions/COORD-ADC-CADENCE/synchronous/measurement-plan-validation.json) checks the pure list and control-update plan independently of UART and scheduling.

## 2026-11-09: refresh and first publication

The [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json) shows that a valid configuration-terminal frame consumes the first of two discard slots. With matching replies, the first refresh frame consumes the other and the second refresh measurement publishes. If the first refresh receives no accepted frame, first publication moves to the third refresh measurement. Reconfiguration re-arms this sequence.

## 2026-11-09: refresh rendering and sound

The [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json) matches original float32 scaling on 18 lifecycle schedules. In the Fast CONT fixture the same stored raw 14023 becomes helper input 5 on three callbacks. Fill reaches 3, median becomes 5, and the original sound gate receives selector 10 and action 1. No additional UART frame is admitted in those three callbacks.

## 2026-11-10 — Native mode entry and sound expiry

For the tested UI mode transitions 1 to 4 and 4 to 3, `0x8000cfd0` sets warmup to 1 while preserving the stored result and filter history. The deferred configuration starts with discard 2 and its terminal frame leaves discard 1. Countdown expiry clears active sound state while preserving the measurement and filter snapshot. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).

## 2026-11-10 — First refreshes after native Fast CONT entry

The second refresh passes scaled input 5 from retained raw 14023 to `0x80007c88`. A populated ring keeps median 5 and requests sound with arguments (10, 1). The empty filter receives the same input, advances to fill 1 and calls the gate with (0, 0). Neither case has a newly published measurement by that callback. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-first-refresh-validation.json).

## 2026-11-10 — KeyTask and Fast CONT refresh ordering

The retained reading can reload the Fast CONT countdown to 3 before fresh UART publication. If KeyTask runs first, count 1 causes an off transition before the refresh re-arms sound. If refresh runs first, KeyTask decrements 3 to 2 without requesting off. Each later KeyTask iteration decrements once until expiry. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/key-task-fast-cont-order-validation.json).

## 2026-11-10 — Scheduler delays and task wakeup

In the tested scheduler state the KeyTask and GaugeCmdTask delay requests become deadlines at counter plus 50 and plus 1 respectively. Wrapped deadlines use the overflow list. The task becomes ready on the matching applied tick. UI refresh uses a separate timer path. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-delay-wake-validation.json).

## 2026-11-10 — Installed vectors and scheduler context

Original SVC handling makes the other ready task current after the `GaugeCmdTask` or `KeyTask` delay. At the deadline the original tick IRQ restores the blocked task, and the delay returns to its saved continuation after 1 or 50 injected interrupts. The host supplies the interrupts and banked exception entry state. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-context-validation.json).

## 2026-11-10 — Timer0 and UART2 through the installed IRQ route

The original FSM at `0x80004490` consumes the buffer produced by the installed UART2 IRQ path. Valid `0x1d` and `0x1b` replies publish raw 74565 with selectors 6 and 0, respectively, or consume discard 1 without publishing. The wrong-header frame triggers a retry and the four-byte prefix remains pending in the bounded schedule. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-irq-validation.json).

## 2026-11-10 — Scheduled GaugeCmdTask service and fallback

When a type-3 measurement precedes a type-1 record, the service retains the fallback while the measurement FSM is busy. If another type-1 record is drained before the FSM goes idle, it replaces the deferred record. In the tested cases only the replacement command is sent. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-service-validation.json).

## 2026-11-10 — Scheduled long fallback and status waits

The scheduled type-1 status chain clears the original RX buffer twice. Status behind the ACK and status arriving during the 10,000-count wait are removed in the fixtures. The next poll consumes the first two bytes received after the second clear and stores 2 for `a0 02` or 7 for `a1 04`. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-long-fallback-validation.json).

## 2026-11-10 — Live calibration status and UI timer

The original UI timer reports `Calibration ...` for live status zero with flag 1. Fresh status 2 or 7 takes precedence over the flag, generates the corresponding original text, and changes the period to 200. In the `0x29` schedule the first result is visible while the flag remains 1. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration reset to fresh measurement

When both reset words are zero, the original calibration callback adds a real type-3 request. The next scheduled service pass drains it, and an IRQ-fed matching reply replaces the seeded measurement with raw 74565 and selector 3. [Shared ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration buttons and pending queue

A queued type-3 measurement and older type-1 command are both drained before the new calibration request. An active measurement completes first and leaves the calibration fallback pending until the FSM becomes idle. With the drain allocation forced to fail and room in the queue, both old records stay ahead of the new request. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-button-queue-validation.json).

## 2026-11-10 — Queue entry candidates and full-queue waits

A full queue rejects the original producer's type-3 zero-wait record immediately. The native `0x27` producer waits up to ten counts and either returns zero on timeout or stores its record after a competing receive frees a slot. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/queue-interior-full-validation.json).

## 2026-11-10 — Direct control producers and result-block writer

The original suffix at `0x8005d118` loads the local state byte and sends type 4 for `0x22` or type 3 for `0x21` in the tested cases, with both argument bytes zero. Type 3 supplies zero wait to the queue API. Other tested types supply ten counts. [Factory hashes, original bytes and ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-producer-suffix-replay.json).

## 2026-11-10 — GUI field provenance at 0x80046548

The bounded initialization path preserves the control queue and its pending records while setting up GUI labels. The `0x80046548` signature is excluded from control-record producer candidates for this path. [Original replay, instruction bytes and firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/gui-field-provenance.json).

## 2026-11-10 — Registered GUI callbacks and indirect queue producers

With two records pending, each matched callback drains both and enqueues one new control record. The original callbacks emit types 0 and 1. The callback at `0x8000e5f0` emits prefix `000000000913`; the neighboring event-code probe leaves the queue unchanged. The second block's `0x8000d294` toggles its flag in every tested state. Three of the eight states emit type 2. [Original instruction bytes, factory hashes and replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-event-validation.json).

## Diode/Buzzer configuration records (2026-11-11)

The original second registration block and dispatcher route event 1 from GUI object `+0x2b8` to `0x8000cfd0`. Both factory images agree in 24 ARM926 cases. Mode 3 with word `0x805ac788 == 1` sends type 5 (`05 00 00 00 22 13`). Mode 3 with word 0 or 2 and mode 4 with any tested word send type 2 (`02 00 00 00 0e 19`). Event 2 leaves the callback and queue untouched. The scheduler is idle and selected UI leaves are modeled. Each dispatched case drains the two seeded records and appends the selected record. These observations end at enqueue. [ARM926 replay and firmware identities](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

## Diode/Buzzer setting and secondary frame (2026-11-11)

The original callback sends the verified control-queue record independently of the secondary sender outcomes tested. The separate frame starts `00 10 40 02 04 04 ff ff` when moving to mode 4 and `00 10 40 02 04 03 ff ff` when moving to mode 3, followed by 56 zero bytes. [Original-image replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).

## Secondary command transport boundary (2026-11-11)

The 64-byte secondary frame can be transmitted by the original channel-1 sender and subsequent frames are suppressed while its busy byte is set. In the recorded lifecycle a ready USB TX interrupt releases that gate; these tests end at the USB register and IRQ boundary. The original primary measurement-queue result was established in the earlier dispatcher replay. [USB lifecycle](contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-lifecycle-validation.json).

## Second GUI registration block, complete callback coverage (2026-11-11)

The second GUI registration block now has bounded original-dispatch replays for all ten callbacks. The eight newly exercised callbacks add 64 cases and 24 sends across V3.6 and V3.8. Every new send has record type 2. The 0x1c handler `0x8000f3b4` uses widget bit 0 to select argument 9 or 10 and writes timer-object value 2000. The value 2000 is the timer object's raw field in the test. [Five callbacks](contributions/COORD-ADC-CADENCE/synchronous/control-gui-second-group-validation.json) · [Three callbacks](contributions/COORD-ADC-CADENCE/synchronous/control-gui-second-final-validation.json).
