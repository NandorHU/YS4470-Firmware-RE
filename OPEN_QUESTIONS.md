# Open questions

## Image acquisition

1. Can the original 3.8 main image with SHA-256 `7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290` be made available locally for read-only analysis?
2. Which hash and image correspond to factory 3.6?
3. Do 3.6/3.8 share the 32-byte header, load address `0x80000000`, and link base `0x7fffffe0`?

## Technical questions

- What raw data enters RX near `0x80004738`, and how does it reach consume near `0x800037fc`?
- What peripheral registers implement ADC/range control/PWM/LCD/keys?
- What is the real scheduler period behind the 13-cycle watchdog?
- What values distinguish diode-valid, OPEN, continuity, and invalid results?
- Where are autorange, calibration, and numeric conversion implemented?
- What are the full GUI, timer, IRQ, and task graphs?

Close a question only with an image hash plus reproducible disassembly, emulator trace, or physical observation.
