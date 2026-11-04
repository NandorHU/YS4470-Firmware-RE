# Measurement algorithms

## Parsed measurement frame (confirmed static behavior)

At `0x80004738`, the parser constructs a 24-bit little-endian value from frame bytes 1–3 and sign-extends it if bit 23 is set. It reads a code from byte 4, limiting normal codes to 6; a control path treats `0x1b` specially. The parser writes output fields under `0x805ac714`. For selectors `0x0d`/ `0x0e`, unsigned values at or above `0x1389` are stored as sentinel `0x007fffff`.

The physical quantity, scale, and whether 5001 is an overload threshold remain unknown.

## Diode / continuity sound path

The established result-branch call site is `0x80003a74`, which calls `SoundControlGate` at `0x80006e4c`. Beta3 replaces the factory selected sound-table halfword at `0x80006e80` with helper `0x80010754`. The helper applies `0x529` only when called from return address `0x80003a78`.

This is evidence of a diode/continuity-branch sound-parameter adjustment. It is not evidence yet of physical frequency, duty cycle, timer period, perceived loudness, or reduced delay. The next analysis must trace the remaining FSM changes and the lower sound routine before any latency claim.
