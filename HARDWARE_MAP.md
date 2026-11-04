# Hardware map

| Component / interface | Status | Evidence |
|---|---|---|
| Allwinner F1C100S | Confirmed | Project status. |
| Winbond 16 MiB SPI flash | Confirmed | Installer/status evidence. |
| SPI boot load | Partially confirmed | boot0 loads flash `0x50020` to RAM `0x80000000`. |
| Measurement-reply software frame | Partially reconstructed | Factory parser at `0x80004738` reads bytes 1–4; physical bus remains unknown. |
| Reply numeric field | Confirmed parser representation | Signed 24-bit little-endian from bytes 1–3. |
| Reply code field | Confirmed parser representation | Byte 4, capped to 6 on the non-`0x1b` path. |
| Highspeed control | Software path partially confirmed | Its event handler and selector are byte-preserved by E1 profiles; physical effect and time unit remain unknown. |
| PWM endpoint | Inferred only | Sound tests stub `0x800060d0`; no MMIO register recovered. |
| ADC/range front end | Unknown | No register trace. |
| LCD/panel controller | Unknown | Boot-logo test stubs init. |

No frame field or Highspeed period has yet been mapped to a physical ADC unit, bus rate, relay, or external protocol command.
