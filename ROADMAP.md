# Roadmap

## Completed baseline

- [x] Record boot0 → main-image mapping and evidence boundary.
- [x] Record the available factory-3.8 main-image SHA-256 identity.
- [x] Record six instrumented entry sites for the candidate measurement response path.
- [x] Separate verified factory locations from patch-only code.

## Next single technical task

- [ ] Obtain the hash-matching original 3.8 main image (read-only) and import it into Ghidra/REA: ARM little-endian payload at `0x80000000`, link-base candidate `0x7fffffe0`. Verify header/load behavior, then disassemble and cross-reference RX `0x80004738` through consume `0x800037fc`.

## Subsequent milestones

- [ ] Establish equivalent mapping for 3.6.
- [ ] Recover raw transport reply format and result parser.
- [ ] Map ADC/range-control/calibration references.
- [ ] Recover GUI/key/timer/IRQ task graph.
- [ ] Specify a clean-room, independently compilable architecture.
- [ ] Validate only with explicit authorization and reversible procedures.

No device write is authorized by this roadmap.
