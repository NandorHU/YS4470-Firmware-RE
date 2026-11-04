# Open questions

## Blocking inputs

1. Which exact, hash-recorded flash dumps correspond to factory firmware 3.6 and 3.8?
2. Are their main-image header, link base, and load addresses identical to the currently evidenced Beta3-derived image?
3. What is the raw measurement transport/protocol and where are its receive buffers parsed?

## Technical questions

- What peripheral registers implement ADC acquisition, range control, PWM, LCD, and keys?
- What is the real KeyTask cycle period behind the 13-cycle watchdog?
- What values and state flags distinguish diode-valid, OPEN, continuity, and invalid results?
- Where do resistance/voltage/autorange algorithms reside, and how do their constants differ across 3.6/3.8?
- What are the complete GUI task graph and interrupt/timer dispatch chain?

## Continuation rule

Close a question only with an image hash plus a reproducible disassembly, emulator trace, or physical observation. Patch behavior alone is insufficient to identify factory firmware semantics.
