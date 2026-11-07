# Sound gate to PWM0

Original V3.6/V3.8 code now executes from SoundControlGate (0x80006e4c)
through its arithmetic helpers, lower routine (0x800060d0), pinmux helper
(0x8000302c), and PWM configuration (0x80042d40). PIO/PWM addresses are
ordinary emulator RAM shadows. No physical device is accessed.

## Fast CONT qualification

The non-sentinel ResultDispatch slice at 0x8000386c selects special path
0x80003910 only when UI mode byte is 4, Fast CONT word is exactly 1, and
configuration byte +7 is 0x22. All other tested combinations select the
ordinary conversion path. The special path later calls helper 0x80007c88;
that helper is a separate pending three-sample-history investigation.

The original sentinel-off setup at 0x8000384c was also executed into the
complete gate path. It passes (0,0), which reaches a zero-duty PWM update
when sound is enabled and the active flag was nonzero. Formatting, result
threshold calculations and the three-sample helper are not executed here.

## Gate contract

Settings word +0x10 must equal 1, otherwise the gate returns without shadow
MMIO and preserves its active flag. Its signed selector is clamped to 1..10.
The u16 table at 0x80063968 requests frequencies:

2000, 2222, 2444, 2666, 2888, 3110, 3332, 3554, 3776, 4000.

Action r1=1 requests output; other tested action values request off. An off
request with no active flag returns without MMIO. Requested output stores
active=1 and result object +0x50=3; completed off stores both zero.

The lower routine computes period_ns = floor(1e9 / frequency). On output,
settings word +0x0c is halved with signed truncation toward zero, converted
to float, multiplied by 10, multiplied by period_ns, divided by 1000, then
converted to an integer duty_ns. The independent oracle models each float32
rounding step, not merely a final percentage. Off requests use duty_ns=0.

The tested setting range is 0..100. This is a proven PWM-duty role; the
setting's user-visible label is not assigned in this experiment.

## First peripheral accesses and register result

The first peripheral operation is a read of PIO CFG at 0x01c20800 from
instruction 0x80003034. Writes clear/set the PA2 mux field to function 3
and clear its pull field at 0x01c2081c. The F1C100S pinctrl source maps
[PA2 function 3 to PWM0](https://github.com/torvalds/linux/blob/master/drivers/pinctrl/sunxi/pinctrl-suniv-f1c100s.c).

The PWM shadow is 0x01c21000: control at +0 and period/duty at +4. Its
prescaler, polarity, enable and clock-gating bit positions agree with the
[Linux sun4i PWM layout](https://github.com/torvalds/linux/blob/master/drivers/pwm/pwm-sun4i.c).
This reference supports register interpretation; it is not a physical YS-4470 test.

For the tested sound frequencies the code uses bypass prescaler code 15,
nominal clock literal 24 MHz, rounded period ticks, and floor(period_ticks *
duty_ns / period_ns) active ticks. The final control low bits are 0x7f.

For selector 5 and duty-setting 90, the original code requests 2888 Hz,
period 346260 ns and duty 155816 ns. The exact float rounding is preserved.
Actual frequency remains conditional on the physical clock configuration.

Off writes zero active duty while leaving PWM_EN and PWM_CLK_GATING set.
This is not equivalent to clearing the PWM controller's enable bit. The
board's acoustic behavior and response delay are not measured by this model.

## Address correction

Earlier prose mislocated the nine changed V3.6/V3.8 data words by 0x20.
File offsets 0x63ac8..0x63ae8 map to linked word addresses
**0x80063aa8..0x80063ac8**, using link base 0x7fffffe0. The raw diff JSON
already contained these correct addresses. The PWM prescaler table starts
at 0x80063acc, after these words, and is unchanged. Its role must not be
assigned to the neighboring modified data. That data's role remains open.

## Run

```powershell
$env:PYTHONPATH = "$PWD\work\analysis-python"
python tools/trace_sound_pwm_path.py `
  --input 'V3.6=<verified original path>' `
  --input 'V3.8=<verified original path>' `
  --out evidence/sound-pwm-path.json
```

Across both originals: 792 gate/PWM cases, 160 result qualifier cases and
two original sentinel-off call setups pass. The arithmetic/PWM oracle is
independent Python integer and float32 arithmetic. All result fingerprints
match. Plain RAM shadows do not model clock progression or analog output.

Continuation: helper0x80007c88's history/range selection is now independently
tested and reconstructed in `reconstruction/fast_cont.c`; see
`FAST_CONT_FILTER.md`. Its persistent tests execute this full original sound
path as well. The subsequent `RESULT_FRESHNESS.md` experiment proves that the
bounded callback path can invoke it repeatedly from one stored result, and
that invalid caller inputs bypass its history reset. Audit excluded GUI/queue
effects and tick contracts before assigning acoustic or measurement timing.
