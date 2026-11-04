# Reverse-engineering status

## Scope and evidence boundary

This repository does not contain a complete factory flash image or manufacturer source. Findings below are limited to published patch metadata, archived ARM/Unicorn test code, and the checked-in project status. They are not claims of a complete firmware reconstruction.

## Confirmed on 2026-11-04

- The target is an Allwinner F1C100S with a 16 MiB Winbond SPI flash.
- The bootloader reads the main executable from flash offset `0x50020`, maps its payload at `0x80000000`, and excludes the 32-byte image header. The published emulator test checks this exact transfer.
- The main image's link-time base is `0x7fffffe0`; therefore an ARM address `A` maps to flash offset `0x50000 + (A - 0x7fffffe0)`.
- Existing evidence identifies the diode-response branch at `0x80003a0c`, the sound gate at `0x80006e4c`, and KeyTask countdown handling at `0x8000553c`.
- Function-level ARM emulation covered diode validity, PWM start/stop requests, the 13-cycle watchdog behavior, and preservation of a short competing beep. It explicitly did not emulate UART/ADC/LCD hardware timing.

## Current position

The prior work is a targeted, physically validated binary patch. It is not a full RE database and does not yet establish factory firmware 3.6 or 3.8 control flow.

## Next proven starting point

Obtain a legally held, hash-recorded original 3.6 or 3.8 flash image, then reproduce the executable-header/load mapping above in Ghidra before assigning functions outside the presently evidenced diode/sound path.
