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
