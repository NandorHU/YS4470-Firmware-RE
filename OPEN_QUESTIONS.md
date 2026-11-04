# Open questions

## Highspeed/profile comparison

1. Does Base + highspeedv2 remain fastest in repeated controlled tests, and which metric—first fresh reply, display, or sound—is improved?
2. Does Direct’s accepted-reply sound work add observable Gauge-task latency compared with Base?
3. Does Auto’s idle request path generate extra queue/bus occupancy under diode contact?
4. Does Ready’s bounded 5→7 dispatch affect request ordering or GUI freshness under realistic UART timing?
5. What is the actual duration of a 200/100 Highspeed selector tick, and which scheduler/task owns it?

## Parser and state

- What does pre-parser `r1 == 0x1b` mean?
- What are `0x805aae8c+1`, selector `+8`, and the special `r7` source?
- Is `0x007fffff` overrange, OPEN, or another display sentinel?
- What fills the raw frame pointer and what is frame byte 0?
- Does `0x80004518` retransmit, wait, or dispatch another phase?

## Broader RE

- Which peripheral/register path implements ADC and range switching?
- How do 3.6 and 3.8 differ?
- Where are voltage, resistance, continuity, autorange, calibration, and display conversion implemented?
- How can raw ARM blocks be cross-checked without Ghidra’s ARM/Thumb context conflicts?
