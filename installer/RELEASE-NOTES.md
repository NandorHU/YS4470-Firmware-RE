# YS-4470 Installer 1.1.0-beta.2

Download **YS4470-Installer-1.1.0-beta.2-Windows-x64.zip**, extract it and run
**YS4470-Installer.exe**. The interface is English. Factory V3.8, Python/Tcl/Tk,
sunxi-fel and the official Zadig driver helper are included. No Python setup,
separate firmware download or manual flash dump is required.

- **Save firmware file:** creates the verified1.0 continuous application from the bundled original, without a meter.
- **Install:** user starts the operation in FEL mode; full backup, second-read confirmation, guarded application writes and full readback are automatic.
- **USB driver setup:** included Zadig helper; explicitly select1F3A:EFE8/WinUSB and approve Windows if requested. Driver changes are not silently performed.
- **Restore:** uses the confirmed automatic backup and refuses changes outside the prior write plan.

Exact factory V3.6/V3.8 and known patched identities are supported. V3.8 continuous
matches the public1.0 application. V3.6 retains its different factory bytes and
is offline-tested only. Bootloader/logo and bytes outside the guarded edits are
preserved. Unknown input/device/flash identities are refused.

Validation includes simulated interruption/recovery, double-read mismatch,
corrupt backup, readback failure, unsupported device/image and concurrent-lock
tests, plus compiled EXE resource/Tcl and runtime-component checks. See
**build-validation.json** and **SHA256SUMS.txt**. Corresponding application and
third-party source archives/licenses are in the **Sources.zip** asset.

This is a **beta installer**, not a new physical measurement test. No physical
device was written during its development/testing. Earlier1.0 firmware device
results do not certify this new installer/FEL build or every meter. Keep the
automatic backup folder private and preserve it for recovery. Read README.md
before installation; the legacy Beta3-specific installer is a separate tool.
