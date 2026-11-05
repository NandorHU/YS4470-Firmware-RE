# Open questions

1. Where is the original V3.6 input registered, and does it use the same raw/eGON layout as V3.8?
2. What do the Beta3 changes at `0x800045e0`, `0x8000461c`, and `0x80004738` do inside the measurement FSM?
3. What hardware unit and units correspond to the sound parameter passed through `SoundControlGate` and the lower routine at `0x800060d0`?
4. Does Beta3 alter acoustic delay, or only the parameter selected after a measurement result?
5. Is `0x80005a78` actually MainADCTask? Validate with bounded emulation/call context.
6. Which SoC UART is used by the RX ISR, and what peripheral/bus supplies the measurement frame?
7. Which Beta3 raw-diff ranges are GUI/profile additions versus measurement protocol modifications?
8. Can a future explicitly approved FEL read operation be designed without violating boot-ROM/SRAM reservations? No such operation is currently authorized.


## Resolved static portion — 2026-11-05

The patches at `0x800045e0` and `0x80004738` are observer wrappers, not changed frame construction or changed signed-24-bit parsing. The `0x8000461c` patch conditionally changes the state-3 `+0x30` field from 30 to 40.

Remaining: identify every read/decrement of `0x805ac694+0x30`, determine the meaning of control bytes at `0x805abefc+0/+2/+7`, and trace the field to a physical timer or protocol cadence before claiming a latency effect.


## 2026-11-05 narrowed questions

- Which indirect callback, scheduler, or alias consumes `0x805ac694+0x30` after the FSM writes it?
- Which writer establishes `0x805abefc+0 = 3` for the Beta3 30→40 condition?
- What semantic mode/event does HighspeedEventHandler's `+2` toggle represent?

The direct PC-literal-object paths have been tested; do not repeat that direct scan before pursuing interprocedural flow.
