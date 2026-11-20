# ownprotocol — offline Beta Diode profile for V3.8 E2

User-directed bounded implementation, 2026-11-20. Profile selection is now
`Base → Direct → Auto → Ready → ownprotocol → Base`. The exact requested display
name is `ownprotocol` (profile ID 4). The profile button expands from 112 to 180 px
only while this name is selected. Its factory glyph advances plus letter spacing
fit; the existing Beta Diode and volume controls retain their geometry.

This is a new **host-side measurement controller using the existing protocol**,
not a new ADC/peer wire protocol or replacement meter firmware.

## Behavior and binary evidence

- Retain factory command ID `0x1d`, wire request `0x60`, original UART ISR, frame
  parser, result thresholds and timeout policy. No unproven command is sent.
- Reuse Ready's bounded completion progression for states 5 and 7, then start
  one new transaction immediately through `0x8000489c` and one `0x80004490`
  step. This removes the extra service turn before the next transmit.
- Admission checks require active=requested=4, UI mode 3/submode 14, full-width
  control function 14, no pending control work/holdoff and no busy transaction.
  The original service caller also applies its existing profile/sound predicate.
- Accepted results drive the inherited E2 reply sound; GUI refresh is independent.
  Missing/wrong/truncated frames do not fabricate accepted results or new tones.
  Existing factory GUI request messages still exist; ownprotocol does not add
  synthetic service-side queue messages. One transaction remains outstanding.
- Profile changes remain deferred while busy. Leaving ownprotocol stops its
  rearming. Selection and volume remain RAM settings, as in the E2 baseline.

Hooks (ARM addresses, mapping base `0x7fffffe0`):

| Address | Change |
| --- | --- |
| `0x8005f8b0` | Five-state cycle in the actual profile callback |
| `0x800609c0` | Bounded label lookup and conditional button width |
| `0x8001110c` | Own admission/direct start; profiles 0–3 retain original path |
| `0x80007f8c` | Ready completion progression also permits profile 4 |
| `0x8006b688..0x8006dc14` | Volume overlay plus own hooks and lossless font data |

The frozen `COORD-DIODE-VOLUME` sources are composed without editing them.
Their original 7,979-byte RLE bitmap left insufficient room, so a bounded LZ
back-reference decoder and a 6,603-byte encoding reclaim space in the same
9,612-byte font region. All 95 glyph lookups and decoded bitmap bytes match the
original. No extra image region is assumed unused. The font still allocates
9,612 bytes lazily, as in the volume candidate. Invalid distances, premature end,
input bounds and output bounds fail closed.

## Inputs and output

- Factory V3.8 application: 5,943,296 bytes, SHA-256
  `7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`.
- Reproduced profiles-E2 SHA-256:
  `b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1`.
- Ownprotocol application SHA-256:
  `b081860a2383e5c1251ea80abf25cb4f39bdf74a340a376975acf2b0ff6f9c8e`.
- Output: `out/ownprotocol/ys4470-e2-ownprotocol-OFFLINE.bin`.
- Build receipt records every guarded edit, overlay size, and hashes. Image size
  and the first 32 header bytes are preserved. V3.6 is not supported by this build.

## Reproduction

Python 3.12.10 and the pinned requirements were used. From repository root:

```powershell
python -m pip install --target work/python-deps -r contributions/COORD-ADC-CADENCE/ownprotocol/requirements.txt
$env:PYTHONPATH = "$PWD/work/python-deps"
python contributions/COORD-ADC-CADENCE/ownprotocol/build_ownprotocol.py --out out/ownprotocol
python contributions/COORD-ADC-CADENCE/ownprotocol/test_ownprotocol.py
```

`reproduce_profiles.py` reconstructs its hash-pinned E2 prerequisite from the
owner-approved original. The builder rejects a different base image or changed
hook preimage. No device access, firmware installation or network API is needed.

## Executed validation and limits

`validation.json` records the candidate identity and bounded ARM926 execution:

- Two complete five-profile cycles through real LVGL event dispatch (original
  GUI allocation/property leaves are modeled; captured profile registration is
  replayed to build the real event descriptor).
- Eight unchanged existing-profile comparisons, original volume event/PWM paths,
  95 font lookups, truncated/invalid font data rejection.
- Eight ownprofile scenarios: stable low, make/break/short contact, delayed reply,
  silence, wrong header and truncation. No overlapping outstanding requests.
- Silence followed by valid replies recovers without resetting the machine.
- Busy/idle deferral for all five requested profiles and eight blocked admission
  conditions, including a full-width function-ID alias.
- Four Highspeed/GUI period/phase combinations preserve ownprofile request,
  accepted-result and reply-sound timing. Corrupt base rejection and deterministic
  rebuilding also pass.

On the supplied open-contact waveform over 250 synthetic counter units:
Ready makes 42 requests/41 accepted results; ownprotocol makes 50/49. Both render
10 times. Ready's first low-result sound is at counter 107, ownprotocol's at 105.
These are **model-specific counter units, not milliseconds or measured hardware
speed**. Faster request cadence does not prove fresher ADC conversions or longer
short-pulse audibility. Late same-header replies have no new sequence identity:
factory protocol correlation and physical ADC behavior remain open questions.

No device was written, no installer/Release was published, and background RE
workers/automation remain paused. This is a separately committed offline test
candidate on `re/2026-11-20-ownprotocol`, based on
`b3bb1dc9e350fafcd75f8fb305c3f0425ad8c5aa`. The paused native GUI reconstruction
and pending external static review were not resumed or integrated.


## Ready-to-run Windows installer (2026-11-20)

User requested this candidate in the installer. Local build version:
`2.0.0-beta.2-ownprotocol`. The extracted ready folder is
`<workspace>/YS4470-ownprotocol-telepito`.
Open its `YS4470-Installer.exe`; the adjacent `firmware/firmware.ysfw`
is selected automatically. No Python or manual package selection is required.
The user still connects the meter in FEL mode and explicitly presses Install.
The ownprotocol measurement profile is then selectable on the meter.

`installer-validation.json` records 27 installer tests, compiled runtime checks,
exact packaged firmware hash, simulated factory-to-ownprotocol installation,
update from a fresh backup store, both restores, and default package discovery
from an unrelated working directory. Ready-folder extraction was byte-compared
to the ZIP, then its EXE was self-tested without a package argument. All pass.
No device operations or remote publication occurred. The Windows/source ZIPs,
standalone firmware package and SHA256SUMS are in `work/easy-installer/release`.


## Standalone EXE fix (2.0.0-beta.3-ownprotocol)

The beta.2 EXE was copied by itself into Downloads, where its required adjacent
firmware package was absent. Beta.3 embeds the same hash-pinned ownprotocol
package in the EXE and uses it by default when no adjacent package exists.
An existing external package still takes precedence and an invalid external
package is refused rather than ignored. Explicit package selection remains.
The build self-test now runs without an external firmware argument. The compiled
release audit also copies only the EXE to an isolated Downloads-like directory,
from a different working directory, and checks the exact embedded package hash.
Three focused source regression tests cover fallback, override and refusal.
The firmware itself is unchanged; no new device access is part of this fix.
