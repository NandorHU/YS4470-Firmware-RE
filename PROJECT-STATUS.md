# YS-4470 — project status

Updated November 20, 2026.

## Current beta: practical responsiveness breakthrough

The current release is **2.0.0-beta.6-v2v4**. The project owner reports substantially faster real-device operation than earlier builds, with near-instant audible feedback. This is an owner-observed improvement; no numerical latency or full accuracy qualification is claimed.

The [standalone Windows EXE](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/installer-v2.0.0-beta.6-v2v4) embeds its firmware. Installation does not require obtaining a factory image or building a personalized firmware file. It checks compatibility, confirms full automatic backups, guards application-sector writes and verifies complete readback.

## What changed

- ownprotocol-style polling reduces host-side waiting between requests.
- Diode configuration uses `59 00` in place of `5a`, interpreted from firmware usage as a fixed-range request replacing autorange.
- v2/v4 add measuring-chip configuration `68 0a`, derived from factory Fast CONT `68 07`. Its exact internal meaning is not documented. The F1C100s system clock is not increased.
- v4 adds an early contact tone and evaluates subsequent reading trends. Early sound and a stable displayed measurement are different events.
- Beta Diode selects v2 or v4; power-on defaults to v2.

Source and replay evidence: [diode v2/v4 branch](https://github.com/NandorHU/YS4470-Firmware-RE/tree/re/2026-11-20-diode-v2v4). The release records ARM926 replays, simulated installation/update/restore and compiled Windows self-tests. Emulation does not establish the measuring chip's analog behavior.

## Remaining work

Measure contact-to-sound and contact-to-stable-display latency, verify diode and LED coverage, check analog accuracy and regress other modes. Isolate each configuration change's contribution. The observed speed-up does not establish new measurement ranges, improved accuracy or maximum hardware speed.

## Historical 1.0 evidence

Version 1.0 was installed and tested; its full 16 MiB readback matched the intended image. `evidence/physical-install-1.0.json` records that older installation. Root build scripts, patch manifests and earlier evidence retain their historical scope and do not describe the new beta's installation requirements.

Earlier investigated addresses include diode validity `0x80003a0c`, sound gate `0x80006e4c`, sound/watchdog state `0x805ac764`, and the earlier continuous-tone watchdog refresh `0x80060928`. Use firmware-specific source and hashes when interpreting them.
