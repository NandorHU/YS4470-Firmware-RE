# Reverse-engineering status

## Current confirmed target

A preserved local factory 3.8 main image was SHA-256 checked as:

`7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`

It is 5,943,296 bytes and remains private. No image was modified or flashed.

## Validated image mapping

- ARMv5T little-endian raw image base: `0x7fffffe0`.
- boot0 loads flash `0x50020` to `0x80000000`, excluding the 32-byte header.
- For ARM address `A`, flash offset is `0x50000 + (A - 0x7fffffe0)`.

## New factory-3.8 result: RX parser

Bounded Ghidra disassembly at `0x80004738` proves that the reply parser builds a signed little-endian 24-bit value from frame bytes 1–3. For its non-`0x1b` control path, it takes frame byte 4 and caps it at 6.

A retry-related state object is at `0x805aae8c`: byte +1 is decremented and word +8 selects a special path. The output state object is `0x805ac714`, with result at +`0x1c` and code at +`0x20`. When selector is `0x0d` or `0x0e` and the unsigned result is at least `0x1389` (5001), the result stored is `0x007fffff`.

The physical units of 5001 and the UI meaning of the sentinel are not yet established.

## Tool status

REA confirmed that its Windows Ghidra adapter cannot open raw ARM binaries. Direct Ghidra 12.1.4 headless import succeeded. Full auto-analysis produced ARM/Thumb context conflicts, so only bounded static disassembly at known ARM instruction addresses is used as evidence.

## Next starting point

Recover the caller and consumer meanings of the control value in `r1`, selector at `0x805aae94`, and the result/code fields at `0x805ac730`/`0x805ac734`.
