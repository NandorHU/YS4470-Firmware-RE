# Reverse-engineering status

## Current confirmed target

The preserved local factory 3.8 main image has SHA-256:

`7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`

It is 5,943,296 bytes and remains private. No image was modified or flashed in this analysis.

## Validated image mapping and RX parser

- ARMv5T little-endian raw image base: `0x7fffffe0`.
- boot0 loads flash `0x50020` to `0x80000000`, excluding the 32-byte header.
- RX parser `0x80004738` creates signed little-endian S24 from frame bytes 1–3 and derives a capped code from byte 4.
- It writes to `0x805ac714+0x1c/+0x20`. Selector `0x0d/`0x0e` plus unsigned value >= `0x1389` stores `0x007fffff`.

## New Highspeed/profile result

A byte comparison between the offline reply-audio parent and E1 profile build proves that factory Highspeed code is preserved:

- event handler `0x8000d294..0x8000d3a0`: identical;
- diode period selector `0x8005d1a0..0x8005d260`: identical.

The profile build instead hooks Gauge-task `0x80005d04`, GUI callback `0x8005d048`, and GUI construction `0x80051c0c`. Thus it does not directly rewrite the Highspeed flag handler or its 200/100 period selection.

A private handoff records one user observation that diode Base + highspeedv2 felt fastest. It is useful prioritization evidence, not a controlled causal comparison. No claim is made that Ready is fastest.

## Tool status and next starting point

REA’s Windows Ghidra adapter cannot import raw ARM images. Direct Ghidra 12.1.4 headless import works; full auto-analysis has ARM/Thumb context conflicts, so bounded disassembly is used.

Next: trace profile hook execution through the queue/FSM around `0x80005d04` and quantify each profile’s added request/FSM work without treating model ticks as physical latency.
