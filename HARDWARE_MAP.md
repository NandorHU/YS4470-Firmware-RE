# Hardware map

## Identified hardware

| Component | Status | Evidence |
|---|---|---|
| Allwinner F1C100S | Confirmed | Existing project status. |
| Winbond 16 MiB SPI flash | Confirmed | Installer evidence and project status. |
| PWM sound endpoint | Inferred only | Archived ARM test stubs a call at `0x800060d0`; the peripheral register address is not published. |
| ADC / measurement front end | Unknown | No original image or register trace is present in the repository. |
| LCD/panel controller | Unknown | Boot-logo emulator verifies a framebuffer draw loop only; it stubs display-hardware initialization. |
| UART/measurement transport | Unknown | Function-level tests explicitly stub hardware timing and transport. |

## Safety note

No register address should be treated as verified merely because a patched function reached a stubbed endpoint. The next hardware-map milestone is a Ghidra/REA register-reference inventory from a supplied original image.
