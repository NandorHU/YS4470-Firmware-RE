# Measurement algorithms

## Demonstrated diode/sound control flow

The checked-in ARM test establishes only these bounded patched-path behaviors:

1. It enters the diode-result branch at `0x80003a0c`.
2. A valid candidate yields one PWM-start request through the original sound route.
3. 1,000 repeated valid candidates cause no repeated PWM stop/restart in the emulation.
4. Invalid and tested OPEN paths request stop.
5. The KeyTask path stops after 13 countdown cycles without refresh.
6. A competing short beep with counter <=3 remains protected.

The test stubs formatting/conversion, PWM hardware, UART/ADC, and LCD behavior. It cannot establish wall-clock latency, thresholds, analog accuracy, or protocol correctness.

## Newly bounded investigation path

Archived diagnostic instrumentation marks TX `0x800045e0`, RX `0x80004738`, consume `0x800037fc`, GUI `0x8005d048`, report `0x80010648`, and IRQ `0x8000740c`. With the matching 3.8 image, these are the ordered starting points for recovering the raw reply → parsed result → display path.

## Not reconstructed

Voltage, resistance, continuity, diode thresholds, autorange, calibration, sampling, and filtering remain unknown.
