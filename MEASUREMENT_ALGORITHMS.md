# Measurement algorithms

## Factory 3.8 reply parser

Static Ghidra disassembly at `0x80004738` establishes this exact representation:

~~~text
u24 = frame[1] | frame[2] << 8 | frame[3] << 16
value = (u24 & 0x800000) ? (u24 | 0xff000000) : u24
~~~

For a parser control value other than `0x1b`, it derives:

~~~text
code = min(frame[4], 6)
~~~

When a retry byte at `0x805aae8c+1` is nonzero, it decrements it and resumes at `0x80004518`. After retry completion, selector `*(u32 *)(0x805aae8c+8)` controls a special condition:

~~~text
if selector in {0x0d, 0x0e} and unsigned(value) >= 0x1389:
    *(u32 *)(0x805ac714+0x1c) = 0x007fffff
    *(u32 *)(0x805ac714+0x20) = r7   # source semantics still unknown
else:
    *(u32 *)(0x805ac714+0x1c) = value
    *(u32 *)(0x805ac714+0x20) = code
~~~

The `r7` source, 5001's physical unit, and sentinel `0x007fffff`'s presentation meaning are open. It must not yet be called an ADC threshold or OPEN code.

## Existing bounded diode/sound evidence

Prior function-level tests show the patched diode path suppresses redundant PWM start/stop across 1,000 valid results; invalid and tested OPEN paths request stop; a watchdog expires after 13 KeyTask cycles. Those tests do not establish real timing, ADC behavior, or metrology.

Resistance, voltage, continuity, autorange, calibration, filtering, and scaling remain unreconstructed.
