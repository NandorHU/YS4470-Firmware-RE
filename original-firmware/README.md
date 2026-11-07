# Original analysis inputs

The project owner explicitly requested publication of these two original firmware
images on 2026-11-07 so contributors can reproduce the analysis. Both files were
SHA-256 checked against the existing research inputs before publication.

| Version | File | Bytes | SHA-256 |
|---|---|---:|---|
| V3.6 | [f1c100s.bin](V3.6/f1c100s.bin) | 5943296 | `7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9` |
| V3.8 | [f1c100s.bin](V3.8/f1c100s.bin) | 5943296 | `7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290` |

These are the application images from the named factory packages in
[manifest.json](manifest.json), not complete 16 MiB personal flash backups.
The raw-file linked base used by the existing analysis is `0x7fffffe0`.
Version 1.0 remains available separately in the
[Release ZIP](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/v1.0).

Use a clone of the [active development branch](https://github.com/NandorHU/YS4470-Firmware-RE/tree/re/2026-11-04-pyghidra-fel); this publication
does not update `main`. Check the hashes after downloading:

```powershell
Get-FileHash -Algorithm SHA256 original-firmware/V3.6/f1c100s.bin
Get-FileHash -Algorithm SHA256 original-firmware/V3.8/f1c100s.bin
```

Pass these paths to the runners' `--input` options. Do not substitute the 1.0
modified image for a V3.6/V3.8 input or treat a matching file size as identity.
Keep originals unchanged; put derived files under a separate work directory.
This publication is for analysis, not an instruction to install an image.
Personal flash backups, calibration/device dumps and recovery material remain
excluded. Third-party rights remain as described in [NOTICE.md](../NOTICE.md).
