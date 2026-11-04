# Hardware map

| Component / interface | Status | Evidence |
|---|---|---|
| Allwinner F1C100S | Confirmed | Project status. |
| Winbond 16 MiB SPI flash | Confirmed | Installer/status evidence. |
| SPI boot load | Partially confirmed | boot0 loads flash `0x50020` to RAM `0x80000000`. |
| Measurement-reply software frame | Partially reconstructed | Factory parser at `0x80004738` reads bytes 1–4; physical bus/transport remains unknown. |
| Reply numeric field | Confirmed parser representation | Signed 24-bit little-endian from bytes 1–3. |
| Reply code field | Confirmed parser representation | Byte 4, capped to 6 on the non-`0x1b` parser route. |
| PWM endpoint | Inferred only | Sound tests stub a call at `0x800060d0`; no MMIO register recovered. |
| ADC/range front end | Unknown | No register trace yet. |
| LCD/panel controller | Unknown | Boot-logo test stubs hardware init. |
| Timer/IRQ controller | Unknown | Only an IRQ-side code location is known. |

No frame field is yet mapped to a physical ADC unit, range relay, or external protocol command.
