# Roadmap

## Completed baseline

- [x] Record the published boot-to-main-image mapping and its evidence boundary.
- [x] Separate patch-specific hooks from factory-code claims in the RE documentation.

## Next single technical task

- [ ] Import a legally held, hash-recorded original firmware 3.6 or 3.8 image into Ghidra/REA using ARM little-endian mapping: file header at flash `0x50000`, payload load address `0x80000000`, link base candidate `0x7fffffe0`. Verify the image header and reset/task entry points before naming any functions.

## Subsequent milestones

- [ ] Build a cross-version function/address map for 3.6 and 3.8.
- [ ] Trace measurement transport receive → result parser → mode dispatch.
- [ ] Recover ADC/range-control peripheral accesses and calibration data.
- [ ] Recover GUI/key/timer/interrupt task graph.
- [ ] Specify and implement a clean-room, independently compilable firmware architecture.
- [ ] Validate only with explicit authorization and reversible test procedures.

No new device write is part of this roadmap.
