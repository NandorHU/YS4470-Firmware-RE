# Roadmap

## Completed baseline

- [x] Verify a preserved local factory 3.8 main image by SHA-256.
- [x] Import the raw image in Ghidra as `ARM:LE:32:v5t` at `0x7fffffe0`; original bytes untouched.
- [x] Recover the S24 reply value, byte-4 code cap, retry state, selector, threshold, and sentinel write in the factory RX parser.
- [x] Record tool limitations: REA raw-ARM adapter unavailable on Windows; Ghidra full auto-analysis has mixed ARM/Thumb conflicts.

## Next single technical task

- [ ] Recover the immediate caller of `0x80004738` and the continuation at `0x80004518`: establish the raw frame pointer origin, the control register `r1`, and whether the decrement at `0x805aae8d` schedules a retry or another phase.

## Subsequent milestones

- [ ] Trace result-state fields `0x805ac730` and `0x805ac734` to UI formatting and mode dispatch.
- [ ] Map equivalent 3.6 parser/control flow.
- [ ] Recover ADC/range-control/calibration references.
- [ ] Recover GUI/key/timer/IRQ task graph.
- [ ] Specify and build a clean-room, independently compilable architecture.
- [ ] Validate only with explicit authorization and reversible procedures.

No device write is authorized.
