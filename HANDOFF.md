# YS-4470 — continuation notes

The current user-facing release is [Windows installer 2.0.0-beta.6-v2v4](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/installer-v2.0.0-beta.6-v2v4). Its standalone EXE embeds the firmware. No personal input firmware or separate factory-image download is required for installation.

The project owner reports a substantial real-device improvement over earlier builds and near-instant sound. This is a qualitative hardware result. Objective latency and complete accuracy/mode regression remain outstanding.

Beta source: branch `re/2026-11-20-diode-v2v4`. v2/v4 combine ownprotocol-style polling, a `59 00` fixed-range request and experimental `68 0a` chip configuration. v4 adds early contact-tone logic. This changes measurement commands and sound policy, not the system processor clock. The chip command's precise internal effect remains unproven.

The root 1.0 builder and offline patcher are historical developer tools, not current installation instructions. Preserve original evidence and hashes; archived evidence is not interchangeable with current release evidence.

Keep full flash backups, calibration dumps, USB logs, credentials and local workspace paths private. Device writes remain user-initiated through the installer. Next work: measure contact-to-sound and contact-to-stable-reading timing separately and verify measurement correctness.
