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

Raw comparison of the two original releases found no changed instruction bytes. The only payload-data delta is nine unclassified 32-bit values at `0x80063ac8`; consequently this evidence neither proves a measurement-algorithm change nor rules out a behavior change caused by configuration data. The previously recovered UART2/FSM/result rules are byte-identical candidates for V3.6 pending a seeded PyGhidra export.

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
