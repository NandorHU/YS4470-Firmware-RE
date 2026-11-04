# Reverse-engineering status

## Scope and evidence boundary

This repository does not contain a complete factory flash image or manufacturer source. Findings are limited to published patch metadata, archived ARM/Unicorn test code, and checked-in project status. They are not claims of a complete firmware reconstruction.

## Confirmed baseline

- Target: Allwinner F1C100S and 16 MiB Winbond SPI flash.
- boot0 reads the main payload at flash offset `0x50020`, maps it to `0x80000000`, and excludes its 32-byte header. The published emulator asserts this exact transfer for a 5,943,264-byte payload.
- Main image link base: `0x7fffffe0`. For ARM address `A`: `flash_offset = 0x50000 + (A - 0x7fffffe0)`.
- The archived 3.8 research build pins a factory main-image SHA-256: `7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`. The image itself is intentionally absent.
- Instrumentation insertion sites identify a candidate flow: transport TX `0x800045e0`, RX `0x80004738`, result-consume `0x800037fc`, GUI update `0x8005d048`, report `0x80010648`, IRQ path `0x8000740c`. These are call/branch sites, not independently named factory functions.

## Current position

The prior work is a targeted, physically validated binary patch. The factory 3.8 image identity is known by hash but unavailable here; 3.6 has not yet been identified. Complete ADC, range, GUI, and task reconstruction remains open.

## Next proven starting point

Acquire a legally held image whose SHA-256 matches the recorded 3.8 value (or another separately recorded 3.6/3.8 hash). Load its payload at `0x80000000` in Ghidra/REA, validate the header/load mapping, then inspect callers around the six instrumented sites.
