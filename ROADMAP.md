# Roadmap

## Current next bounded task

Trace and classify the Beta3 request/reply FSM deltas at `0x800045e0`, `0x8000461c`, and `0x80004738`. Output: a raw instruction-level evidence table that says whether each delta affects frame acceptance, state progression, value parsing, or is unrelated. Do not infer latency from the sound override alone.

## Near term

1. Add the original V3.6 image as a local verified input (preserve original and SHA-256 locally), then run the existing PyGhidra inventory and comparison scripts.
2. Attribute the remaining 63 V3.8/Beta3 changed ranges and preserve uncertainty where boundaries are unclear.
3. Map the sound parameter from `0x80006e4c` into its lower routine and peripheral ownership.
4. Build a minimal Unicorn harness for a bounded parser or sound helper only after its memory/register contract is known.
5. Correlate GUI/result observer state only after static references are enumerated.

## Later milestones

- Establish task/interrupt map and startup flow.
- Validate ADC task, range logic, resistance/voltage/current/capacitance algorithms.
- Reconstruct GUI, settings, storage, calibration, and update flow.
- Build a separately compilable functional reconstruction with test fixtures; never replace or flash original firmware automatically.


## Updated next bounded task (2026-11-05)

Find the consumer(s) of `0x805ac694+0x30` and prove whether the field is decremented by a scheduler tick, checked as a protocol timeout, or exported to another subsystem. Then map the three selector bytes at `0x805abefc+0/+2/+7` to their writers. This is the shortest path to establishing whether the Beta3 30→40 change affects measurement cadence rather than only metadata.


## Updated next bounded task (2026-11-05, after literal trace)

Trace the event/scheduler path originating at `0x800031b8` and its callbacks to find an indirect consumer of FSM object `+0x30`. In parallel, follow the dynamic write at `0x8000d74c` and related writers until a proven `0x805abefc+0 = 3` source is found. Preserve the distinction between a static state-field value and physical time.


## Updated next bounded task (2026-11-05, after PIO trace)

Decode the descriptor records at `0x8006367c + 8*command_id` for IDs `0x09..0x0f`. Establish command bytes/lengths, link the two observed PIO patterns to protocol commands, and only then attempt a measurement-mode mapping. Keep the unresolved FSM `+0x30` indirect-consumer search separate.


## Updated next bounded task (2026-11-05, after descriptor decoding)

Trace `0x80006dc8` to identify the byte transport and its completion/timing contract. Then follow response parsing for descriptor IDs `0x09..0x0f`, especially 0d/0e, to map a command/PIO/frame path to observed measurement behavior without guessing UI labels.


## Updated next bounded task (2026-11-05, after UART2 trace)

Trace UART2 initialization: locate the writes to `0x01c25800` register offsets (divisor/LCR/FCR/IER and pinmux setup), then trace the RX-buffer completion path from `0x805b408c` into parser state 5. This should establish wire configuration and command/response transaction boundaries without hardware interaction.


## Updated next bounded task (2026-11-05, after UART2 initialization)

Trace the RX-buffer frame-completion path: identify every writer/reset of `0x805ab938` and every caller that invokes parser state 5 at `0x80004738`. Output a verified frame-boundary rule before assigning command/response semantics to UART2 frames.


## Updated next bounded task (2026-11-05, after RX lifecycle trace)

Trace the descriptor-table entries and callers for FSM command IDs `0x1b` and `0x1d`. Establish their transmitted frames, their state-3 headers (`0x5e`/`0x60`), and the consumers of the signed-24-bit result without assigning a physical measurement name prematurely. Keep descriptors 09–0f separate until their own response path is proven.


## Updated next bounded task (2026-11-05, after command-1b/1d extraction)

Trace the state-5 result stores and their consumers: resolve the literals at '0x8000481c..0x80004820', follow the signed value and selector written at '0x800047b4..0x800047b8', and connect them to a UI/result structure. Do not infer diode, continuity, or any physical range name from dispatcher case values without a proven downstream mapping.


## Updated next bounded task (2026-11-06, after result-flow trace)

Trace the special state-5 saturation branch backward: resolve the object at '0x805aae8c+0x08', prove which command/config values select IDs 0x0d/0x0e, and determine when threshold '0x1389' causes sentinel '0x007fffff'. Then separately trace ResultDispatch's SoundControlGate call conditions without equating them to a physical buzzer event.


## Updated next bounded task (2026-11-06, after saturation-path reconstruction)

Trace the ResultDispatch sentinel branch at '0x800037fc..0x80003854' into SoundControlGate '0x80006e4c' and its immediate callees. Prove call arguments, gate conditions, and the first hardware-facing sound-control operation. Keep the distinction between a sentinel-triggered software call and audible buzzer behavior.

## Updated next bounded task (2026-11-06, after V3.6 intake)

Run the existing bounded PyGhidra seed inventory on the verified original V3.6 input and compare it with V3.8. Separately trace the literal-pool consumer beginning at `0x80042d98` to classify the nine changed V3.6/V3.8 data cells. Keep the already scheduled ResultDispatch → SoundControlGate trace independent; do not infer buzzer timing or a physical measurement mode from the version-data delta.

## Updated next bounded task (2026-11-06, after live FEL identification)

Use the verified local flash backup to classify the regions outside the main eGON image, beginning with header and signature scans plus known package assets. In parallel, restore the bounded PyGhidra V3.6 inventory environment and compare V3.6/V3.8 known function windows. Do not flash any image merely to accelerate analysis: the current device is confirmed E2-modified, and its backup must remain the recovery baseline.

## Updated next bounded task (2026-11-06, after PyGhidra V3.6/V3.8 baseline)

Trace SoundControlGate at 0x80006e4c into direct callee 0x800060d0 and continue until the first hardware-facing sound-control operation is proven. The relevant bounded V3.6/V3.8 exports are identical, so perform this once against V3.8 and carry the evidence to V3.6 only within that bounded scope. Keep passive UART-TTL capture as a separate future validation task.

## Updated next bounded task (2026-11-06, after real-byte ARM926 execution)

Trace the writers of sample-discard byte `0x805aae8d`, starting from the verified control-object literal loads. Determine what sets/reset its initial count and which input modes can reach it. Reuse the new 5,952-case parser harness for regression rather than redoing parser disassembly. The separate SoundControlGate → 0x800060d0 hardware-control trace remains pending.

## Updated next bounded task (2026-11-06, after countdown lifecycle)

Trace the record-building helper at 0x80006778 and its direct callers. Establish which input events produce software cases 2/5, and which source values fill record bytes +4/+5. Preserve physical measurement names as hypotheses until a UI/string or explicit hardware mapping supports them. Reuse the completed lifecycle/parser harnesses; do not repeat their disassembly. SoundControlGate → 0x800060d0 remains a separate pending hardware-control task.

## Updated next bounded task (2026-11-07, after GUI event-source linkage)

Trace settings word 0x805ac788 through writers/defaults/storage and seek its GUI label. This is the shortest next step to explain why the Buzzer UI can select either [0x0e,0x19,0x1d] or [0x0c,0x22,0x13,0x1d]. Reuse the validated event-builder/dispatcher/parser harnesses. Queue timing and SoundControlGate hardware ownership remain separate pending tasks.

## Updated next bounded task (2026-11-07, after Fast CONT identification)

Trace the Fast CONT-dependent result consumer starting at 0x80003870/0x80003878, then connect its sound-gate conditions and arguments to 0x80006e4c → 0x800060d0. Recover the first peripheral-facing sound operation without assigning a millisecond delay or acoustic outcome. The named setting/default/record format is now established; reuse the Fast CONT and event-source harnesses rather than repeating that work.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

Next: reconstruct/test helper0x80007c88 with persistent histories, invalid/threshold values and range-table choices; feed its calls into the now-validated gate. Do not rerun completed parser, Fast CONT setting or gate analysis. Reference-based SoC signature tooling is an authorized parallel workstream within the continuing project.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.
