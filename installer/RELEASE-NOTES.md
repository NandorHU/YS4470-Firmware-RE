# YS-4470 Windows installer 2.0.0-beta.6-v2v4

Open YS4470-Installer.exe on its own, even from Downloads. The embedded V3.8 E2 package is selected
automatically. Connect one meter in FEL mode and choose Install; writes need the user's explicit action.

The Beta Diode button now alternates **v2 ↔ v4**; v2 is active after power-on. Both use the
ownprotocol polling and the diode fixed range (`59 00` instead of `5a`), and configure the diode
function with the additional chip command `68 0a` (modelled on the factory Fast CONT `68 07`).
- v2: fast chip mode only.
- v4: v2 + "tone first": the short tone starts at contact and stays while the reading falls towards
  0 V; it stops when the decay settles at a junction level (brief chirp for diodes/LEDs).
Base/v1/v3 code paths remain in the image (tested) but cannot be selected.

User report on hardware (beta.5, 2026-11-20): v2 and v4 rated excellent.

Application SHA-256 da35f4968038801ddfe5d3528fb45d59df644ee80350a940e8c76a9e8d264c01.
Installing beta.5/beta.4 or the automatic backup restores previous firmware.
Safety chain unchanged: family check, two matching backups, application sectors only, full readback.
Validation: ARM926 replays (v2/v4 cycle, toggle callback and boot default, Base = E2, v1 = beta.4,
68 0a configuration and profile-switch reconfiguration, tone-first on 7 synthetic decays, rearm guards),
simulated install/update/restore including upgrade from beta.5, compiled EXE self-tests.
