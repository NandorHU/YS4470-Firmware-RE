# Make 1.0 from your own YS-4470 firmware

**You do not need Beta3 or the author's personal flash backup.** This offline
patcher accepts the two supported factory application images, either as a raw
`f1c100s.bin` or embedded at0x50000 in your own16 MiB flash backup. It creates
a new file and verifies its hash. It never connects to a meter.

Download the repository ZIP using **Code → Download ZIP**, extract it, and open
the `patcher` folder. Keep `ys4470_patch.py` and `patch-data.json` together.
Python3.10 or newer is required; no Python packages or paid API are needed.

## Windows: drag and drop

Drag your original firmware file onto **`PATCH-WINDOWS.cmd`**. This creates
`<your-name>-ys4470-1.0-continuous.bin` and a `.report.json` alongside it.
The original file is left unchanged. Existing output files are never overwritten.

The continuous variant includes the released1.0 highspeedv2/application changes.
The timed variant is available through the command line.

## Command line

Run from the extracted repository directory:

```text
python patcher/ys4470_patch.py inspect "my-backup.bin"
python patcher/ys4470_patch.py apply "my-backup.bin" --output "my-1.0.bin"
python patcher/ys4470_patch.py apply "my-backup.bin" --variant timed --output "my-1.0-timed.bin"
python patcher/ys4470_patch.py revert "my-1.0.bin" --output "my-restored-original.bin"
```

Use the same `--variant timed` when reverting a timed file. To switch variants,
revert to a new original file first, then apply the other variant. There is no
force option for unknown input hashes.

## Supported inputs

| Factory version | Application bytes | Application SHA-256 |
|---|---:|---|
| V3.6 / Project_February_V3.6_V02.26.6 |5,943,296|`7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9`|
| V3.8 / Project_March_V3.8_V02.26.6 |5,943,296|`7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`|

For a16,777,216-byte full backup, the patcher checks the application hash inside
the backup. **Your whole-backup hash is expected to differ from someone else's.**
Only69 byte ranges/939 bytes change for continuous,65 ranges/928 bytes for timed.
All other bytes are preserved, including the bootloader, logo, settings/storage
outside the application, and every application byte outside the listed edits.
The V3.6 version-specific factory data and application header are retained.

If rejected, run `inspect` and share only its text output in a GitHub issue.
Do not upload a personal full-flash backup or calibration dump. A V02.26.2 or
other unlisted image is not automatically compatible. A filename, displayed
version or whole-flash hash cannot replace the application identity check.

## What was actually checked

-14 regression tests: both versions/variants, raw and personalized full-flash
  fixtures, round trips, corrupt/unknown input rejection, byte/output guards,
  no overwrite and real CLI execution.
- The V3.8 continuous output is byte-identical to the application in the
  [published1.0 Release](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/v1.0).
  Expected application SHA-256:
  `697d160047e9f040b31acd79d5b0febb940bc712f15eb6e2d91d997a5608011d`.
- V3.6 applies the same guarded edits and keeps its different factory bytes.
  Its output has a different pinned hash and **has not been physically tested**.
-12 bounded original ARM926 loader-window cases confirmed the same payload-read
  arguments for the known factory and released bootloaders. This is not a full
  cold-boot or device-compatibility test.
- The Windows launcher was exercised with a filename containing a space.

## Installing the resulting file

This tool prepares a file; it performs no USB, FEL, erase, RAM execution or
firmware-write operation. The existing Release installer requires its particular
Beta3 backup and **must not be used for these personalized outputs**.

Preserve your original complete backup and use your established, verified
programming/recovery process. The full-flash output preserves your own bootloader
and logo; it is not the Release bundle's cosmetic bootloader/logo replacement.
The patched application's header is retained, matching the released application
behavior. Installation using the Mr.Yang factory updater is **not verified**.
Generating an application file does not establish that the updater will accept it.
Device writing is not performed or approved by running this patcher.

The existing1.0 device test concerns the previously tested build/device.
Offline patch tests do not certify every meter, all measurement modes or accuracy.

## Reproducing the patch data

The generator uses only the owner-published factory application files and the
public1.0 Release ZIP pinned to SHA-256
`d336adcb687a1f53695cf1cf98419265f284f97ded2690449f2553fe1e50c038`.
The timed application is reconstructed from the public application-only deltas;
no private Beta3 backup is needed for generation either. Details and test evidence
are under [COORD-PUBLIC-PATCHER](https://github.com/NandorHU/YS4470-Firmware-RE/tree/re/2026-11-04-pyghidra-fel/contributions/COORD-PUBLIC-PATCHER)
on the reverse-engineering development branch. Manufacturer firmware rights
and the project's [NOTICE](../NOTICE.md) remain unchanged.

Regression tests require the two pinned originals from the analysis branch in
`original-firmware/V3.6` and `V3.8`. Run `python -m unittest discover -s patcher
-p test_patcher.py -v` from that checkout. Those inputs are not runtime
dependencies of the patcher and your own supported firmware stays local.

Magyar útmutató: [OLVASS-EL.md](OLVASS-EL.md).
