# Measurement algorithms

## Factory 3.8 reply parser

At `0x80004738`:

~~~text
u24 = frame[1] | frame[2] << 8 | frame[3] << 16
value = (u24 & 0x800000) ? (u24 | 0xff000000) : u24
code = min(frame[4], 6)             # only outside control path 0x1b
~~~

A retry byte at `0x805aae8c+1` resumes `0x80004518`. Selector `*(u32 *)(0x805aae8c+8)` chooses a special output for values >= `0x1389`:

~~~text
selector in {0x0d, 0x0e} -> store 0x007fffff at 0x805ac714+0x1c
otherwise                 -> store value at 0x805ac714+0x1c
~~~

The 5001 unit and sentinel UI meaning remain unknown.

## Highspeed and profile comparison

The E1 profile build preserves the factory Highspeed event-handler and diode period-selector bytes. Existing evidence describes the selector’s diode branches as 200 ticks OFF and 100 ticks ON, but the tick duration is unknown.

Static profile semantics:

| Profile | Direct audio | Autopoll | Immediate extra FSM work |
|---|---:|---:|---:|
| Base | no | no | no |
| Direct | yes | no | no |
| Auto | yes | yes | no |
| Ready | yes | yes | bounded 5→7 after original pass |

Therefore Base has the least added experimental acquisition work. This does not prove it is physically fastest or establish why a user perceives it that way.

Voltage, resistance, continuity, autorange, calibration, filtering, and scaling remain unreconstructed.
