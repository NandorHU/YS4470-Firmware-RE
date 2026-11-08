# Equal-Highspeed diode profile experiment — 2026-11-08

This is a bounded ARM926 experiment on the existing E2 application, not a full
meter emulator. Its SHA-256 is
`b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1`.
The common input is a raw-value waveform; task order and UART response timing
are modeled. No physical device operation occurred.

## Result and its practical limit

An existing software wait can be removed: Direct drives sound on an accepted
reply, while Base processes the stored result at the next GUI callback. With
Highspeed=1, the OPEN→contact case accepts raw50 at counter106 in both profiles.
Base calls sound control at125; Direct calls it at106. Both send10 requests
in250 counter units and render the low result at125. This is a19-unit modeled
software difference, **not19 milliseconds or a physical probe-to-beep result**.

The requested explanation for Base feeling faster than the other profiles is
**not proven**. This model does not reproduce a shorter Base sound-start delay.
It does expose a separate possible perceptual factor: Auto/Ready can replace a
brief low value with OPEN sooner, producing a shorter sound-control pulse.
In the short-contact waveform (raw50 only at101≤t<109), observed ON/OFF are
Base125/150, Direct106/131, Auto110/118, Ready107/113. Whether a shorter pulse is
less audible on the physical buzzer remains unknown. No minimum-tone or ADC
timing patch is justified by this observation alone.

## Same Highspeed, separate active/requested state

| E2 profile | Active byte | Sound owner | Extra request when idle | Extra FSM progress | Stable-low requests/accepts at HS=1 |
|---|---:|---|---|---|---:|
| Base |0| GUI stored-result path | no | no |10/10|
| Direct |1| accepted-result hook | no | no |10/10|
| Auto |2| accepted-result hook | yes | no |32/31|
| Ready |3| accepted-result hook | yes | states5/7 in the same service call |42/41|

Each row uses the same Highspeed=1, initial GUI period25, GUI-first/service-next
order, response start=request+1, one byte per counter unit, and250-unit horizon.
The final in-flight response can account for requests exceeding acceptances.
The GUI callback itself changes its timer period: HS=0 produces2 GUI polls in
the same horizon, HS=1 produces10. The full matrix tests both HS values but never
compares two profiles with different HS values as a speed result.

E2's gate at0x8005fd4c branches to `flag`0x80007f60; its active-byte load is at
0x80007f64. It substitutes active!=0 for the old UI Highspeed condition on the
reply-owned sound path. Thus HS=0 does not disable the Direct/Auto/Ready sound
ownership. GUI period selection still reads UI Highspeed independently. This
is a property of this exact E2 image, not a statement about all firmware builds.

Requested is byte1 at0x80060a90; active is byte0. `apply`0x80058678 returns while
FSM+0x34 is busy, performs the old sound cleanup and only then stores requested
into active.64 in-flight switch cases (all16 pairs at four counter positions)
finish at the target and every observed active-byte store occurs with busy=0.
Unchanged start=target cases are included and do not imply a store occurred.

## Binary evidence

- Rechecked all six original-hash Ghidra packets and360 instruction bytes.
  These remain original V3.6/V3.8 packets, not E2 decompilations.
- Original GaugeCmdTask wrapper0x80003dbc→service0x80005b6c is established by
  the previous packet proof. A newly executed empty-queue/inactive-FSM service
  iteration on each original reaches FSM0x80004490 then requests sleep(1)
  through0x80005d14→0x80060fbc. That is a requested delay argument, not a measured
  task period. The actual sleep routine/scheduler is modeled here.
- E2 service callsite0x80005d04 instead calls `step`0x800107cc; tail branch at
  0x80005d08 enters0x8005fb78. The original queue drain, request builder, FSM,
  UART ISR0x800073bc, numeric conversion and sound selection execute around
  the exact patched hooks.
- Accepted-parser stores at0x800047a8/0x800047b4 reach0x80060c70 in the
  reply-audio/E2 inputs. The hook checks eligibility/configuration/timer pause,
  applies its sound selector and reaches the original sound gate0x80006e4c.
  Base keeps GUI ownership; Direct skips that GUI sound write.
- Header mismatch and incomplete deadline are counted separately. At HS=1,
  the wrong-header case has20 header rejects for Base/Direct and33 for
  Auto/Ready; these are not20/33 timeouts. Truncated/missing responses produce
  no accepted results or sound calls; all four profiles have5 incomplete
  deadlines in250 units. Busy GUI polls are separately discarded and counted.
- The harness records RX bytes, requests, state stores, parser holdoff drops,
  accepted results, queue poll drops, sound control and renderer entry.
  Host request labels are not firmware transaction IDs. A delayed frame's
  freshness relative to the real conversion cannot be established from them.

[profile-validation.json](profile-validation.json) contains64 waveform cases,
64 switches,16 existing-candidate cases,268 assertion groups, original idle
service traces and exact input/source hashes. [traces/](traces/) retains every
event boundary for the64 waveform cases in compact JSONL. The978 addresses in
[observed-e2-instructions.json](observed-e2-instructions.json) are code-hook
observations, including skipped modeled-leaf entries; they are not an
instruction or whole-firmware coverage percentage.

## Offline candidate and reproducibility

`reproduce_profiles.py` starts from the public pinned original V3.8, runs the
existing public continuous patcher, then replays158 ordered recorded edit
preimages from [profile-chain.json](profile-chain.json). Every stage has an
exact final SHA-256 and retains the original32-byte application header:

| Stage | SHA-256 |
|---|---|
| threshold-1.1 |884c39524942cf42580b52c0ce3ed8b33dab8d8fc4d3addd6266d1c9831c551e|
| reply-audio |9890a3c671987b0aa75a505e4f389532ca102f9dcf306394daa45a9328bc91e1|
| profiles-E2 |b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1|

This is a newly verified public-input reproduction of **existing offline
candidates**, not a newly invented firmware fix or an execution of the old
source generators. It requires no personal full-flash dump. The reply-audio
parent removes the proven GUI sound wait without changing its threshold-1.1
parent's request/accept counts in the16 comparisons. Its threshold-1.1
dependency also changes sound policy (<0.1 continuous, downward <0.7 one-shot);
do not describe it as a timing-only change to the public1.0 firmware.

The original0x80000124 copy and0x800000c8 decompressor reconstruct initialized
globals from the pinned stock application. Result SHA-256 is
`524ba48c4f8e6b7876fc1da735f82f197eb436947e65eac043f2d9f2b96f8be0`.
No captured runtime memory/calibration dump is needed or published.

From repository root, with tools/analysis-requirements.txt installed:

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python"
python contributions/COORD-ADC-CADENCE/reproduce_profiles.py --out work/adc-cadence
python contributions/COORD-ADC-CADENCE/validate_profiles.py
```

The generated reply-audio-OFFLINE.bin is an application analysis input. This
run does not make it flash-ready, update the public installer, or publish a new
firmware Release. V3.6 active-profile execution is outside this experiment.

## Local helper and remaining work

One new checked-lessons local-model request completed (71 generated tokens,
10.485s including model load). Its exact active-byte quote was checked against
the E2 bytes by the coordinator; the supplied pointer/context was not discovered
by the model. No independent timing/ADC finding was accepted. A socket-permission
failure before the request is preserved separately. See [local-review/](local-review/).

Missing for the reported Base advantage: confirmed installed-build identity,
real UART/ADC conversion behavior under extra0x60 requests, task ordering and
clock units, and buzzer/pulse observations. Static callers, global writers and
indirect calls outside the six packets and observed paths remain incomplete.
Do not shorten deadlines, increase polling, or hold a tone after OPEN on an
unproven physical hypothesis. Resume from [STATUS.md](STATUS.md).
