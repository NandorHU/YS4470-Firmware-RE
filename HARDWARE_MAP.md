# Hardware map

| Component | Status | Evidence |
|---|---|---|
| Allwinner F1C100S | Confirmed | Project status. |
| Winbond 16 MiB SPI flash | Confirmed | Installer evidence/status. |
| SPI boot load path | Partially confirmed | boot0 emulator asserts flash `0x50020` to RAM `0x80000000`. |
| PWM sound endpoint | Inferred only | Sound test stubs call `0x800060d0`; no MMIO register has been recovered. |
| Measurement transport | Candidate code sites only | Diagnostic patch instruments TX `0x800045e0` and RX `0x80004738`; physical protocol is unknown. |
| ADC/range front end | Unknown | No original image or register trace. |
| LCD/panel controller | Unknown | Boot-logo test stubs hardware init. |
| Timer/IRQ hardware | Unknown | Instrumentation marks an IRQ-side branch site, not a controller/register. |

## Rule

Do not label a peripheral register or bus protocol “verified” from a patch endpoint or stub. The next milestone is a register-reference inventory from a supplied original image.
