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
