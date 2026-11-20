# Diode mode — end-to-end pipeline (V3.8, E2/ownprotocol/beta.4), 2026-11-20

Scope: what the firmware does from a Diode selection to sound and display. "Executed" means
original/E2 ARM instructions ran on Unicorn ARM926 with the stated fixtures. "Static" means
disassembly only. Nothing here establishes physical time units, ADC behaviour or acoustic output.
Image under test: beta.4 4-site candidate `934a2557…ae9417` (ownprotocol `b081860a…` + 4 bytes).

## 1. Entry (executed; see candidate_adapter.py / adapter-report-4site.json)
| Path | Code | Record | UI+6..8 | Commands → wire |
|---|---|---|---|---|
| Mode button callback | 0x8000cfd0 (tail 0x8000d0bc) | (2,0x0e,0x13) | 02 0e 13 | 0x0e,0x13,0x1d → `58 0a 62` `59 00 59` `60 60` |
| Mode selector, index 3 | 0x80044e54 (0x80045044) | (2,0x0e,0x13) | 02 0e **19** | same |
| Buzzer, Fast CONT=0 | 0x8000d0bc / 0x800450c4 | (2,0x0e,0x13) | as above | same |
| Buzzer, Fast CONT=1 (unchanged) | 0x8000d0a4 / 0x8004513c | (5,0x22,0x13) | 02 22 13 | 0x0c,0x22,0x13,0x1d → `58 07 5f` `68 07 6f` `59 00 59` `60 60` |

Factory/beta.3 diode sends `5a 5a` instead of `59 00 59`. Selector r8 at 0x80044ec0 is shared by five
branches (V, cfg 0x0c, cfg 0x0f, diode, buzzer) and is intentionally unpatched.
Dispatch sets CTRL+8 = 0x0e and the discard counter CTRL+1 = 2. In the ownprotocol image the setup
payloads go out at model ticks 0 and 102 and the first poll at 104 (identical for 0x19 and 0x13).

User observation on hardware (beta.4, 2026-11-20): diode readings correct (1N4148 ≈0.6 V, OL, short ≈0)
and the display reacts noticeably faster than beta.3. This supports, but does not prove, that `5a` is
autorange and that autoranging caused most of the old display lag.

## 2. Reply → stored result (executed earlier; MEASUREMENT_ALGORITHMS.md)
Poll `60` → 5-byte reply `60 v0 v1 v2 s`. Parser 0x80004738: signed 24-bit LE value, selector
min(s,6). While CTRL+1 > 0 a reply is consumed and discarded (two after every mode entry). With
CTRL+8 ∈ {13,14} every value whose unsigned representation is ≥ 5001 becomes 0x7fffff, selector 0
(diode overload). Result: RESULT 0x805ac714 +0x1c raw, +0x20 selector.

## 3. Display (executed: diode-sweep-profile*.json)
Scale exponent table 0x80063817 + 7·config + selector; config 0x0e is 03 for all seven selectors, so the
displayed value is raw × 10⁻³ V regardless of the range byte (raw 400 → 0.400, 5000 → 5.000, 5001 → OL).
The renderer runs from the GUI timer callback 0x8005d048 (period from UI Highspeed: 25 model units at
HS=1), not from reply acceptance. Render cache 0x8000328c compares UI+0/+7/+8 with +0x11/+0x0f/+0x10.

## 4. Sound decision (executed: diode-sweep-profile4.json, profile0.json, sound-retouch.json)
E2 "threshold-1.1" + "reply-audio" policy. The decision does not use volts: 0x80010754 classifies the
**raw count** into r5 = 0.0 (raw < 100), 0.5 (100 ≤ raw < 700), 1.0 (raw ≥ 700); 0x800602b4 then
compares |r5| with 0.1 and 0.7 (literals 0x7b99999a, 0x7e666666 = 0.1f, 0.7f shifted left by one).

| Raw (mV) | Branch | Action |
|---|---|---|
| < 100 (short) | 0x800602f0 → 0x80060928 | if countdown RESULT+0x50 ≤ 3: start tone (gate 5,1), state 2, countdown 13; else refresh countdown 13 |
| 100…699 (junction) | 0x800602d4 | downward one-shot: state 0→1, tone started, countdown 2 → off at expiry |
| ≥ 700 / OL | 0x800602f8 → 0x80010718 | tone off if countdown > 3 (gate 5,0) |

Countdown is decremented by KeyTask 0x8000553c; expiry with active tone calls gate (5,0).
Gate 0x80006e4c returns immediately unless settings +0x10 == 1, clamps the selector to 1..10 and
reaches 0x800060d0, which programs pinmux 0x8000302c and PWM 0x80042d40 directly (no deferral).

Ownership: the E2 hook 0x8005fd38 runs in the reply path only for UI mode 3 / UI+7 == 0x0e and an
active profile ≠ 0 (0x80007f60). Base (profile 0) evaluates in the GUI callback.

Measured order in the model (OPEN until t=50, then constant raw):
- ownprotocol: first fresh reply t=55 → tone t=55; first display t=75.
- Base: first reply t=56; tone and display together at t=75.
- Re-touch after release (ownprotocol): off at 165, on again at the first short reply 180.
  The countdown ≤ 3 condition did not block re-start in this schedule.

So in this firmware model the tone is never later than the display. The user's hardware report
(ownprotocol, short: tone noticeably later than display) is not reproduced. Not modelled: real task
priorities/periods (KeyTask, GUI, GaugeCmd), real chip reply timing under dense ownprotocol polling,
and buzzer/driver behaviour. Next diagnostic (on hardware): Direct and Base profiles on short.

## 5. Open
- Meaning of `59 0n` vs `5a` confirmed only behaviourally (display faster, values correct).
- Range byte `s` in diode replies (fixed range 0 vs autorange) is not observed.
- `68 xx` (sent only by Fast CONT) is unnamed; whether `68 0a` would help diode is untested.
- Tick units of all timers; physical probe-to-tone and probe-to-display latency.
