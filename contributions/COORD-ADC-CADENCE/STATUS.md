# COORD-ADC-CADENCE — proven checkpoint, 2026-11-08

Coordinator-owned and still in progress. Base physical advantage remains
unexplained; no physical unit or complete firmware/ADC emulation is claimed.

Completed now: public-stock replay of the pinned historical E2 chain (158
preimage guards), original copy/decompress-derived globals, six packet identity
checks/360 instruction bytes,64 equal-Highspeed waveform cases,64 requested vs
active switches,16 existing reply-audio candidate comparisons,268 assertion
groups, and one original idle service iteration per V3.6/V3.8. See README.md,
profile-validation.json and traces/. All original bytes and Release are intact.

Proven software example (HS=1, modeled counter): OPEN→contact raw50 accepted106
in Base and Direct; Base sound125, Direct sound106; both10 requests and low
renderer125. Auto/Ready send more requests; a brief-contact sound-control pulse
is shorter in this model. This does not prove the user's physical Base finding.
Malformed/missing replies never start a tone in the tested cases.

reproduce_profiles.py --out work/adc-cadence creates the existing historical
reply-audio-OFFLINE.bin (9890a3c6...) and E2 (b04fb5bc...) from the public
stock application. It replays recorded edits, not source generators. The
reply-audio parent removes the verified GUI wait, but depends on threshold-1.1
sound-policy changes. No new speculative polling/timeout patch was produced.

One new local LLM extraction completed and its active-byte quote was checked
against E2. It adds no independent timing finding. Failed sandbox socket access
is recorded separately; no completed model job/batch was repeated.

Next bounded task: resolve why extra polls/brief tones differ on actual hardware.
First confirm the installed application identity without a write, and use
existing public/private read-only UART/update protocol evidence to determine
whether0x60 restarts conversion or returns buffered data. If hardware is
unavailable, extend the model with separately labeled response-source variants
and test phase/order sensitivity; do not select one as hardware truth. The
reproduced immediate-responder model alone cannot justify another speed patch.
Keep the incomplete whole-firmware caller/global/indirect-call survey explicit.

Reproduce: set PYTHONPATH to work/analysis-python; run reproduce_profiles.py
then validate_profiles.py. Do not import legacy tests with top-level writes.
No USB/device operations, public firmware Release update or main merge occurred.
