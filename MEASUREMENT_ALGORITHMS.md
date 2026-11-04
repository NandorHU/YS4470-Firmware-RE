# Measurement algorithms

## Diode/sound path: demonstrated behavior

The checked-in function-level ARM test provides these bounded findings for the patched 1.0 path:

1. Execution enters the diode-result branch at `0x80003a0c`.
2. A valid diode candidate produces one PWM-start request through the original sound-control path.
3. Repeated valid candidates do not repeatedly stop/restart PWM in the emulated path.
4. An ordinary invalid result and the tested OPEN sentinel request tone stop.
5. Without refresh, the tested KeyTask path stops after 13 countdown cycles.
6. A competing short beep with counter value <=3 is preserved.

These are control-flow findings, not timing or metrology results. The published test stubs float formatting/conversion, PWM hardware, UART/ADC, and LCD behavior.

## Not reconstructed

Resistance, voltage, continuity, autorange, calibration, sampling, filtering, ADC scaling, and diode thresholds have not been derived from an original firmware image. No claim of equivalent measurement algorithms is justified yet.

## Next analysis

With a hash-recorded original image, identify the measurement-protocol receive routine feeding `0x80003a0c`; enumerate its callers and record the raw reply buffer format before inferring numerical algorithms.
