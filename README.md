# YS-4470 firmware 1.0 — highspeedv2

Firmware improvements for the Mr. Yang YS-4470**Version 1.0 continuous has been installed on the device. A complete 16 MiB flash readback matched the intended image byte for byte, and the owner confirmed that version 1.0 works well.** This is an operational confirmation, not a complete accuracy or reliability certification.

**[Download version 1.0 from Releases](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/v1.0).** Compiled firmware is distributed as Release assets only; it is not tracked in the source tree.

## Project goal

Reverse engineer and improve the existing firmware, primarily to reduce the delay between probe contact, the displayed diode measurement, and the audible indication. The project also provides reproducible offline patches, input-hash and original-byte validation, a verified Windows FEL installation process, and rollback support.

The original measurement hardware and factory measurement commands are retained. New measurement ranges and improved measurement accuracy have not been demonstrated. This is a binary patch project: the manufacturer's complete firmware source code is not available.

## Current status — November 2, 2026

The target uses an F1C100s system controller and a Winbond 16 MiB SPI flash. Analysis used Ghidra, ARM disassembly, and function-level Unicorn emulation. The response-processing, display-update, sound-control, and boot-image paths have been investigated sufficiently for the targeted changes.

The owner reported faster response and correct display updates with Beta2/Beta3. Installation of version 1.0 continuous changed six 64 KiB sectors. A fresh full backup of the working Beta3 image was saved first, and the complete post-write flash readback matched the intended image. The owner subsequently confirmed that version 1.0 works well.

Remaining work includes objective contact-to-display and contact-to-sound latency measurements, extended testing of continuous sound and watchdog edge cases, regression testing of every measurement mode, measurement-accuracy checks, and further hardware investigation. The maximum achievable hardware speed and the benefit of additional optimization have not been established.

## Features

- Retains Beta3's faster diode polling, corrected complete-response deadline, and suppression of redundant updates when measurement-label text is unchanged.
- Renames the English switch label to `highspeedv2`. The text and terminating NUL fit the original 12-byte allocation. Labels in other languages are unchanged.
- `continuous`: a continuous 1321 Hz diode tone while the original valid-measurement condition holds. Open or invalid input requests a stop. The patch adds no sleep or extra measurement command to the measurement cycle.
- `timed`: a fallback build retaining Beta3's nominal 420-tick one-shot tone, with the same updated label and boot image.

The sound uses PWM synthesis approximating the pitch of the supplied reference audio. It does not play the MP3 waveform. Continuous sound implements the latest requested behavior and replaces the earlier one-shot duration requirement.

## Use and limitations

Select diode mode and enable `highspeedv2`. Check the switch after restarting; this project does not add automatic persistent setting storage. The owner has confirmed improved Beta3 responsiveness and working version 1.0 operation. Quantitative latency comparison, complete mode regression, and accuracy validation remain outstanding.

Valid measurements refresh a finite sound watchdog while its counter is above three. The original KeyTask stops the tone after 13 cycles without a qualifying refresh: nominally about 650 ms, depending on actual scheduling. A mode change therefore does not leave an indefinitely sustained tone, but immediate stopping has not been established. Counters of three or less preserve a superseding short key beep. In unusual scheduling conditions, sound may remain until the watchdog expires after an invalid result. These edge cases require further physical testing.

## Reproducible Windows build

Python 3.12 and its standard library are sufficient for the portable patch build. It requires your own verified **full 16 MiB Beta3 flash backup**, with this SHA-256:

`2ce9c1693a9726a2fe042620debd7705e77cfec58d98e8729bb6ec1ade4a9d0f`

```powershell
python build.py --backup C:/my-backups/current-beta3.bin --fel C:/tools/sunxi-fel.exe
```

This produces standalone local installation bundles in `out/continuous` and `out/timed`. The `--fel` argument can be omitted for an offline build; native installation requires the pinned executable. The build verifies input hashes, original patch bytes, and final output hashes.

`patches/*.json` contains applicable binary deltas, not the manufacturer's source code. Full personal flash backups and external executable tools are excluded from the public source package. See `NOTICE.md` for provenance and scope.

## Installation and rollback

The Release ZIP contains the compiled main firmware, bootloader, and boot image in `firmware/`, plus the reproducible installer project in `project/`. Read `OLVASS-EL.txt` before installation. Preparing the tested installer requires the exact matching Beta3 backup and `sunxi-fel.exe`; an unknown device state is not automatically supported. Installation through the factory updater has not been verified.

This build **also modifies the bootloader** to position the boot image. Interrupted writing may require FEL recovery. Each physical installation requires explicit approval for that build.

1. Connect one F1C100s device with the expected Winbond 16 MiB flash in FEL mode, with stable power and USB.
2. After approving the specific installation, run `Install-V1-APPROVAL-REQUIRED.cmd` in the chosen generated bundle.
3. The installer creates a fresh complete backup, checks known state and hashes, writes only changed 64 KiB blocks, then reads back all 16 MiB and verifies byte-for-byte equality.
4. Progress uses actual completed blocks and Hungarian stage names. It reaches 100% only after successful verification. There is no automatic reset.
5. `Restore-Beta3-APPROVAL-REQUIRED.cmd` restores the previous working Beta3 image, including the factory boot image. Rollback also requires explicit approval.

The installer accepts only the known Beta3 state or its own target variant. To move between the two 1.0 variants, first restore Beta3 using the current variant's rollback tool. If an error occurs, keep the device in FEL mode and preserve all logs and backups.

## Tests and evidence

Portable build and virtual installer tests, without USB access:

```powershell
python tests/test_build.py --backup C:/my-backups/current-beta3.bin
python tests/simulate_installer.py out/continuous
python tests/simulate_installer.py out/timed
```

The simulator replaces device enumeration and all native FEL calls in a temporary copy; the original installer is unchanged. It tests installation, rollback, and rejection of corrupted readback.

`evidence/` contains function-level ARM emulation results for drawing and sound, virtual-flash installer tests, and the independently verified physical installation record in `physical-install-1.0.json`. Hardware endpoints are stubbed in emulation; those tests do not establish full cold-boot behavior, analog accuracy, or real hardware latency.

Research scripts under `src/` are archived from the original workspace. The portable build entry point is the root `build.py`. Archived emulation tests require Unicorn and the original local firmware inputs.

See `PROJECT-STATUS.md` for research addresses and next steps. Older manifests retain their status at the time they were created; the physical installation record documents the later successful installation. Keep full flash backups, USB logs, and local `out/`, `inputs/`, and `tools/` directories private.
