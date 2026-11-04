# Roadmap

## Completed baseline

- [x] Verify the local factory 3.8 image by SHA-256 and import it read-only into Ghidra.
- [x] Recover its S24 reply parser, retry state, code cap, threshold, and sentinel write.
- [x] Compare E1 profile build against reply-audio parent: Highspeed event and period-selector regions are byte-identical.
- [x] Record the profile hook points and Base/Direct/Auto/Ready static action matrix.

## Next single technical task

- [ ] Trace the original FSM call at `0x80004490` and the E1 hooks at `0x80005d04/`0x80005d08` through a complete request/reply transition, distinguishing profile-added calls from the original Highspeed period-selector path.

## Subsequent milestones

- [ ] Establish the raw frame pointer origin, control register `r1`, and `0x80004518` continuation.
- [ ] Trace `0x805ac730/`0x805ac734` to formatter, GUI, and sound.
- [ ] Map equivalent 3.6 control flow.
- [ ] Recover ADC/range-control/calibration and GUI/key/timer/IRQ graphs.
- [ ] Specify a clean-room, independently compilable architecture.
- [ ] Validate physical behavior only with explicit authorization and reversible procedures.

No device write is authorized.
