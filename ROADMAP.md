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
