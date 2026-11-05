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
