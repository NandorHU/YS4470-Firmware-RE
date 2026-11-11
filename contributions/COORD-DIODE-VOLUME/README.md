# E2 diode volume

This offline application variant targets the hash-pinned E2 build reproduced
from factory V3.8. In diode mode the existing top strip shows
`Volume [−] 60% [+]` immediately left of Beta Diode. The existing two E2
buttons keep their positions and callbacks. The volume controls follow the
strip's existing alternate-header visibility rule.

Volume ranges from 0 to 100 in steps of 10. Zero is mute. The setting is
separate from the global volume and defaults to 60 after startup. A change
applies to the next diode tone and immediately updates a continuous diode
tone that still owns PWM. The original global sound enable, the short key
tone and the diode watchdog retain their roles.

## Build and check

From the repository root, use the project's analysis environment and
`keystone-engine==0.9.2`.

```powershell
python -B contributions/COORD-DIODE-VOLUME/build_diode_volume.py --repo . --out work/diode-volume
python -B contributions/COORD-DIODE-VOLUME/test_diode_volume.py --repo . --candidate work/diode-volume/ys4470-e2-diode-volume-OFFLINE.bin --out work/diode-volume/validation.json
```

[Build receipt](build-receipt.json) · [Emulation report](validation.json)

## Implementation and limits

The GUI construction and visibility hooks are at `0x80051c0c` and
`0x8005d048`. Buttons use the same event-1 dispatch as the factory controls.
The sound hook at `0x80006ec0` applies the separate value to the two E2 diode
caller return addresses. A live update uses the original critical section
and PWM routine while the continuous diode tone owns the output.

The image remains the original size and preserves the application header.
The overlay shares the original bitmap range at `0x8006b688` with a
lossless packed copy of that font. The existing font callback at
`0x8006eafc` is wrapped. On first use, the wrapper reserves 9,612 bytes
through the original GUI allocator, decodes within checked bounds, and
hands off to the original lookup. The emulated result is byte-identical
to the original bitmap.

The checks cover actual original event registration and indirect dispatch,
PWM register writes with shadow MMIO, volume limits and ownership, glyph
widths and 95 bitmap lookups, and eight E2 profile scenarios. GUI
layout calls and allocation are modeled. There is no physical display,
touch, sound or cold-boot validation for this application variant.

## Factory persistence research (2026-11-11)

Original registration `0x8001b2d0` binds the settings save callback `0x800453c8` to GUI context `+0x394`. In the three tested event codes, event 1 reaches the original CRC and storage routine. The other tested events leave the record unchanged. A Fast CONT checkbox update alone changes the RAM word. At `0x80006374` the original save reads a 4 KiB sector. A blank record prefix goes directly to one 72-byte program. A nonblank prefix takes erase, scratch merge and sixteen 256-byte program calls. Both paths preserve the adjacent synthetic bytes when transfers succeed. When the in-memory SPI model returns a short page header, the original skips that page, makes no second sector read and still reaches the completion log. This is an offline fault case.

The factory volume handler `0x80057d34` reads slider `+0x3a0`, caps the input at 100 and stores half at settings `+0x0c`. The original preview passes half that stored value to the modeled PWM call. The global field survives the tested save/load round trip. The valid-record loader overwrites selected metadata spans after validation. The independent diode-volume overlay still uses its runtime state. These tests identify the factory behavior needed to evaluate future storage options.

```powershell
$task = 'contributions/COORD-DIODE-VOLUME'
python -B "$task/trace_factory_settings_roundtrip.py" --out factory-settings-ui-validation.json
python -B "$task/trace_factory_settings_sector.py" --out factory-settings-sector-validation.json
python -B "$task/trace_factory_settings_write_failure.py" --out factory-settings-write-failure-validation.json
python -B "$task/trace_factory_volume_slider.py" --out factory-volume-slider-validation.json
```

[Settings event](factory-settings-ui-validation.json) · [Sector merge](factory-settings-sector-validation.json) · [Short transfer](factory-settings-write-failure-validation.json) · [Global volume](factory-volume-slider-validation.json).
