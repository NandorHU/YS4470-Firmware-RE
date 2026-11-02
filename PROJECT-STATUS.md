# YS-4470 - project status

## Goal

Reduce the delay between probe contact, diode measurement updates, and the audible indication while retaining the existing measurement hardware and factory commands. Version 1.0 includes the Beta3 responsiveness improvements, the highspeedv2 switch label, and continuous diode sound.

## Progress

- I preserved the original firmware and verified the initial full flash backups.
- Ghidra analysis, ARM disassembly, and function-level emulation established the relevant response-processing, diode-validity, sound-control, and firmware-loading paths.
- I tested Beta2/Beta3 and observed faster response with correct display updates.
- I installed and tested the 1.0 continuous build. The full 16 MiB flash readback matched the intended image byte for byte, and the build works well on the tested device.
- Reproducible binary patches, installer preparation, rollback, tests, and verification records are available. Compiled builds are distributed as Release assets only; private full backups are excluded.

## Research addresses

- 0x80003a0c: diode-validity branch; 0x80003a74: original sound-gate call.
- 0x80006e4c: sound gate; 0x805abf06: measurement repeat-suppression latch.
- 0x805ac764: sound-state/watchdog counter; 0x8000553c: original KeyTask countdown.
- 0x80060928: 1.0 watchdog refresh; 0x80060950: post-start counter initialization.
- 0x80010718: scoped stop handling for OPEN and invalid measurement paths.
- 0x8000f568: Beta3 identical-label-text wrapper.
- 0x80058750: Beta2 diode-response deadline helper.
- 0x80051978: highspeedv2 English label, including its NUL terminator in 12 bytes.

## Limits and next steps

My functional test is not a complete measurement-accuracy or reliability qualification. Objective contact-to-sound/display latency, extended watchdog edge cases, regression of all measurement modes, and analog accuracy still need testing. Function-level emulation does not establish actual ADC/UART/panel timing. The timed-tone fallback remains available.

Further experimental firmware writing and physical tests require explicit approval. The current working 1.0 build is preserved while additional improvements are investigated.
