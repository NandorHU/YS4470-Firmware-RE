# Portable factory-input patcher — 2026-11-08

I removed the private Beta3 full-backup prerequisite by deriving application-only
edits directly from the supported factory V3.8 image to the public1.0 application.
Every edit preimage also matches the pinned V3.6 image. Applying only those edits
keeps V3.6's different factory bytes instead of silently replacing them with V3.8.

I downloaded the actual public Release ZIP and matched both SHA256SUMS.txt and
GitHub's asset digest, `d336adcb687a1f53695cf1cf98419265f284f97ded2690449f2553fe1e50c038`.
The continuous target comes directly from firmware/f1c100s-1.0.bin. The timed
target is derived by reversing the public continuous application edits and
applying the public timed application edits. Boot/logo/full-backup bytes are
not used in the new patch resource. The generator needs no private backup.

`patcher/` contains the standard-library CLI, SHA-pinned patch data, Windows
drag/drop launcher, regression tests and bilingual instructions. Full inputs
are recognized by the embedded application at0x50000, not a whole-device hash.
Unknown application hashes, byte guards, output hashes, existing output paths,
in-place writes and incorrect reversal variants are rejected.

Validation:14 regression methods passed, including all four version/variant
round trips for raw and synthetic personalized16 MiB inputs. Synthetic outside
application markers were preserved. V3.8 continuous is byte-identical to the
downloaded public application. V3.6 target hashes are newly pinned offline
variants; no V3.6 physical operation was done. See validation.json.

The first test invocation found a test-fixture slice that grew by two bytes,
and sandbox temporary-directory permissions. I corrected the fixture length
and placed checked temporary paths under work/. The Windows launcher probe
found an installed py launcher without a registered interpreter; it now checks
availability and falls back to python before running a patch, never after a
patch failure. The filename-with-space launch and rejection of a second launch
to an existing output were checked separately.

`verify_loader.py` executes the original0x490..0x508 loader window on ARM926.
For two known bootloaders and six application headers, all12 cases request
flash0x50020 → RAM0x80000000, length5,943,264. printf/SPI-read are explicit
leaf models; startup/DRAM/clock/device behavior is not executed. This supports
leaving the loader unchanged for this observed read contract, not every
unknown bootloader or cold boot. No bootloader image is published here.

Reproduce using the public originals and downloaded Release ZIP:

```powershell
python contributions/COORD-PUBLIC-PATCHER/generate_patch_data.py --release-zip work/public-patcher/release.zip --original-dir original-firmware --out work/public-patcher/regenerated.json
python contributions/COORD-PUBLIC-PATCHER/validate_patcher.py
$env:PYTHONPATH="$PWD\work\analysis-python"
python contributions/COORD-PUBLIC-PATCHER/verify_loader.py --factory-boot '<own official V3.8 boot0_rgb480x854.bin>'
```

The known official boot SHA-256 is
`cdecb2aa58beb830c0efceb77e9488dc91de328df64341c6191df8d042a6d132`.
The new JSON must match patcher/patch-data.json byte for byte. The generated
application/full-container files are local outputs and are not committed.
No personal backup, calibration, complete additional firmware or credentials
are included. No device operation or factory-updater compatibility is claimed.

The existing COORD-ADC-CADENCE task remains owned and unfinished. It was
redirected by the user's public-patcher request after reading the profile builder
and legacy harness sources, before executing their tests. Resume from the six
hash-bound packets and verify the local E2 build chain before drawing any
Base+highspeedv2 versus Direct/Auto/Ready conclusion. No such latency cause or
offline measurement-speed fix was established by this patcher session.
