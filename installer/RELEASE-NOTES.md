# YS-4470 reusable Windows installer 2.0.0-beta.1

Extract the **Windows x64 ZIP** and open **YS4470-Installer.exe**.
The included `firmware/firmware.ysfw` targets the V3.8 E2 firmware
family and adds independent diode volume beside **Beta Diode**.
It adjusts from 0 to 100% in 10-point steps, including mute.

For the next update, replace `firmware/firmware.ysfw` or choose a new
`.ysfw` inside the installer. The EXE stays the same. The standalone
`.ysfw` on this release is identical to the one in the Windows ZIP.

The installer requires a recognized application from the matching
family, confirms a full backup with two reads, writes only guarded
application sectors, and verifies the complete flash afterward.
A verified backup can be restored through the app.

This is a pre-release. Validation covers simulated installation,
upgrade, interrupted writes and restore, a compiled Windows self-test,
and the firmware's ARM926 emulation. Physical installation, display,
touch and sound have not been tested with this package. The source
archive includes the application builder and pinned third-party sources.
