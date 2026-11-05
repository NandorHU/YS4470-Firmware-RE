# Hardware map

## SoC-level verified sources

The F1C100S documentation identifies an ARM926EJ-S core and USB download capability in boot ROM. The Linux device tree maps CCU, interrupt controller, PIO, timers, and UART0–2; exact mappings used in this project are in `MEMORY_MAP.md`.

## Current firmware correlations

- The firmware has a receive ISR at `0x800073bc`, but the active UART peripheral instance is not yet proven.
- The sound gate at `0x80006e4c` ultimately invokes a lower-level routine at `0x800060d0`; a timer/PWM/codec ownership link is not yet proven.
- Beta3 changes a sound-call parameter for the diode/continuity branch. It does not, by itself, prove which hardware peripheral produces the audible output.

## FEL status

A historical project test identifies an F1C100S in FEL mode and a 16 MiB Winbond SPI flash. The only committed FEL automation is restricted to enumeration and SPI-flash identification. No write, erase, RAM code, or peripheral-register operation is authorized.


## 2026-11-05 boundary

The new FSM trace is wholly static. It narrows a control-field change but does not connect `0x805ac694+0x30` to any timer, PWM, UART, or buzzer peripheral. No hardware-map entry is promoted from this result.


## 2026-11-05 static-state boundary

The recovered objects are firmware RAM structures. The access trace identifies no MMIO register, timer instance, PWM, or buzzer peripheral. Therefore the 30→40 selector remains a software-state change with no asserted hardware timing unit.


## PIO control evidence — 2026-11-05

The measurement FSM controls bits 2 and 3 of the MMIO word at `0x01c208c4` (derived from PIO argument `0x01c208b4` plus helper offset `0x10`). It clears both during transaction construction, then chooses either bit3=1/bit2=0 or bit3=0/bit2=1 for specific command-ID groups.

This is a static PIO-control result only. It does not identify a GPIO port/pin, analog switch, range relay, buzzer line, or the electrical polarity at the board.


## Protocol-output boundary — 2026-11-05

The descriptor send helper calls `0x80006dc8` once per framed byte, but its peripheral ownership has not been recovered. The output must remain described as a firmware byte-output path, not as UART, GPIO bit-bang, SPI, or a specific external IC interface until `0x80006dc8` is traced.


## Measurement UART — 2026-11-05

The firmware sends descriptor frames through **UART2** at `0x01c25800`; the corresponding RX ISR receives from the same base. This is now a confirmed firmware transport link, not merely a candidate UART.

Unresolved hardware facts: which F1C100S pins are muxed for UART2, electrical level/interface, baud/format, and the identity of the external measurement controller. The shared UART2 result does not imply direct access to ADC registers.


## UART2 pins and configuration — 2026-11-05

Firmware writes function value 3 into the PIO fields for **PE7** and **PE8**. The F1C100S pinctrl definition maps those functions to **UART2 TX** and **UART2 RX** respectively. [Linux F1C100S pinctrl source](https://github.com/torvalds/linux/blob/master/drivers/pinctrl/sunxi/pinctrl-suniv-f1c100s.c)

The initialization requests baud argument 19200 and programs divisor `0x0249`; it then transmits startup sequence `60 60`. Exact applied baud is not asserted without independently proving the live UART clock source.


## UART2 RX completion boundary — 2026-11-05

No UART2 hardware register in the ISR declares a complete application frame. The ISR appends individual bytes in RAM and increments `0x805ab938`; the MeasurementFSM later applies a software rule for command IDs `0x1b/0x1d`: at least five bytes plus header `0x5e` or `0x60` respectively.

Therefore no new peripheral, ADC, timer, buzzer, or physical measurement mapping is asserted. This result is a firmware RAM/protocol gate, not evidence of a hardware end-of-frame signal.
