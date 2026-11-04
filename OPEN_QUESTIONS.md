# Open questions

1. Where is the original V3.6 input registered, and does it use the same raw/eGON layout as V3.8?
2. What do the Beta3 changes at `0x800045e0`, `0x8000461c`, and `0x80004738` do inside the measurement FSM?
3. What hardware unit and units correspond to the sound parameter passed through `SoundControlGate` and the lower routine at `0x800060d0`?
4. Does Beta3 alter acoustic delay, or only the parameter selected after a measurement result?
5. Is `0x80005a78` actually MainADCTask? Validate with bounded emulation/call context.
6. Which SoC UART is used by the RX ISR, and what peripheral/bus supplies the measurement frame?
7. Which Beta3 raw-diff ranges are GUI/profile additions versus measurement protocol modifications?
8. Can a future explicitly approved FEL read operation be designed without violating boot-ROM/SRAM reservations? No such operation is currently authorized.
