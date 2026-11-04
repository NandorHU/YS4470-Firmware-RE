# Open questions

## Parser and state

1. What does the pre-parser `r1 == 0x1b` control path represent, and why does it force its derived code to zero?
2. What concrete object/meaning is at `0x805aae8c`, especially byte +1 and word +8?
3. What produces `r7` for the special sentinel store at `0x805ac734`?
4. Is `0x007fffff` an overrange, OPEN, or another presentation sentinel? The static parser alone does not prove this.
5. What physical unit and mode behavior correspond to the unsigned 5001 threshold?

## Transport and algorithms

- What fills the raw frame pointer consumed at `0x80004738`, and what is frame byte 0?
- Does `0x80004518` retransmit, wait, or dispatch the next command?
- Which peripheral/register path implements ADC acquisition and range switching?
- How do 3.6 and 3.8 differ in reply format and parser behavior?
- Where are voltage, resistance, continuity, autorange, calibration, and display conversion implemented?

## Tooling

- Can targeted ARM blocks be analyzed without ARM/Thumb context conflicts, or should a second raw-ARM disassembler be configured for cross-checking?
- REA’s Windows Ghidra adapter cannot import raw ARM images; direct Ghidra headless import is the current reproducible path.
