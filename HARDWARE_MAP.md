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
