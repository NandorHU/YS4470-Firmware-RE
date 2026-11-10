# YS-4470 reusable Windows installer

Extract the Windows x64 ZIP, then open `YS4470-Installer.exe`. The ZIP
includes the current V3.8 E2 diode-volume beta as
`firmware/firmware.ysfw`. For another update, replace that single file or
choose a new `.ysfw` in the app. The EXE contains the runtime and tools.
It loads firmware from the selected external package each time.

## Install and restore

1. Extract the complete ZIP. Run the EXE, and check the selected package.
2. Connect one YS-4470 in FEL mode using a USB data cable. If the FEL
   device is missing, open the included driver helper and select WinUSB
   for the device with USB ID `1F3A:EFE8`. Driver setup requires approval.
3. Choose **Install selected firmware in FEL mode** and confirm the
   package name and firmware family. Wait for verified full readback.
4. After verification, power-cycle the meter. Keep the automatic backup
   folder private. Use **Restore from an automatic backup** with its
   `backup-before.bin` and the accompanying plan and manifest if needed.

The installer accepts exactly one F1C100s with the supported 16 MiB
Winbond flash and a recognized application from the matching firmware
family. This release's included package targets V3.8. It supports
factory V3.8, the known V3.8 1.0/experimental images and future images
previously verified by this installer on the same Windows backup store.
An unrecognized existing application is backed up and refused. The two
backup reads must match. Changes are confined to complete application
sectors, and the entire flash is read back after the write. Firmware
packages are application images. Personal backups stay on the local PC.

A package SHA-256 checks consistency with its manifest. Obtain packages
from the project Release or another source you trust. This installer is
a beta tested with a simulated flash and a compiled Windows self-test.
It has not been exercised against a physical meter.

## Package a new firmware version

Create a `.ysfw` from the reviewed, full-length application binary for
the corresponding factory firmware family. Use a fresh output name.
The EXE does not have to be rebuilt.

```powershell
python installer/pack_firmware.py new-firmware.bin --family V3.8 --label "New E2 build" --out new-firmware.ysfw
```

The firmware must preserve its factory-family header and the existing
application geometry. A change in the final partial sector is rejected
because the installer writes only complete sectors contained in the
application.

## Reproduce the Windows release

Use 64-bit Python 3.12.10 with the pinned build dependencies. Run
`python installer/prepare.py` to verify the public build inputs. Build
the E2 diode-volume application as documented in
`contributions/COORD-DIODE-VOLUME`, then package it.

```powershell
python installer/build.py --firmware-package path/to/firmware.ysfw
python installer/verify_release.py
```

The Windows and source ZIPs, separate firmware package, SHA-256 list
and test receipt are written to `work/easy-installer/release`.
