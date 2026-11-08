# YS-4470 Installer 1.1.0-beta.2 — English Windows GUI

Download the Windows-x64 ZIP from this Release, extract it, and double-click
**YS4470-Installer.exe**. The package includes its Python/Tcl/Tk runtime, the
SHA-pinned original factory V3.8 application, the FEL utility and the official
USB-driver helper. No Python installation, firmware selection or manual dump
is needed. All application text is English.

## Save firmware without a device

Click **Save firmware file** and choose a new filename. The bundled original
V3.8 is patched and checked against the released1.0 continuous application hash.
The original factory image is also supplied under `factory/V3.8/` in the ZIP.

## Install to a meter

1. Put one YS-4470 into FEL mode and connect a USB data cable with stable power.
2. Click **Install to meter in FEL mode** and confirm the named operation.
3. Wait for **Verified successfully**. Only then disconnect/power-cycle.

The installer detects exactly one F1C100s with the expected16 MiB Winbond flash.
It reads a full automatic backup, checks the installed application identity,
reads the complete flash a second time and requires an identical result.
Only then does it write the changed64 KiB application sectors. A third complete
readback must match every intended byte before100% success is shown.
Bootloader, logo, and all bytes outside guarded application edits are preserved.
There is no automatic reset, unknown-image override or blind retry.

The exact factory V3.6/V3.8 application identities and known patched variants
are supported. A V3.6 device retains its version-specific factory bytes; that
port is offline-tested only. The newly packaged installer/FEL binary has not
been physically tested on a meter. Firmware1.0's earlier device test does not
certify this beta installer, every board or measurement accuracy.

## USB driver: included, with Windows approval

If detection fails, click **USB driver setup**. The included official Zadig
helper opens. Select **only USB VID1F3A / PIDEFE8**, choose **WinUSB**, and click
Install Driver. Windows may ask for administrator approval. Then close Zadig
and retry installation. Do not select a keyboard, mouse or another device.

Driver selection and the Windows approval remain explicit user steps. The
package does not silently change drivers, install certificates, disable
security controls or bypass Windows prompts. No download is required by the
installed GUI; all tools are bundled and verified by SHA-256.

## Automatic backups and recovery

Backups/logs are stored under `%LOCALAPPDATA%/YS4470 Installer/backups/` in a
new folder for each operation. Keep the folder private: it contains your own
complete flash data. It is never uploaded or part of a Release package.

If writing or verification fails, keep FEL mode and use **Restore from an
automatic backup**, selecting that run's `backup-before.bin`. The backup must
match its confirmed manifest and write plan. Changes outside the prior plan
cause restoration to be refused. Recovery also requires full readback equality.
No automatic retry or reboot is issued after failure.

## Build and tests

The source and dependency archives accompany this Release. The GUI uses the
same tested public patch resource as `patcher/`. Build on64-bit Windows with
Python3.12.10 and `requirements-build.lock.txt`:

```text
python installer/prepare.py
python -m unittest discover -s patcher -p test_patcher.py -v
python -m unittest discover -s installer -p test_engine.py -v
python installer/build.py
```

`prepare.py` downloads only the public SHA-pinned inputs in dependencies.lock.json.
It never reads a device. Tests use synthetic personalized flash fixtures and a
fake transport. `--self-test-report` on the built EXE verifies bundled resources
without opening a GUI, USB or device. Sources and third-party notices are in
the separate Sources ZIP. Public GitHub-hosted standard Windows build runners
are used; no paid inference API is involved.
