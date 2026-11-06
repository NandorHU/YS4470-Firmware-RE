# Open questions

1. Where is the original V3.6 input registered, and does it use the same raw/eGON layout as V3.8?
2. What do the Beta3 changes at `0x800045e0`, `0x8000461c`, and `0x80004738` do inside the measurement FSM?
3. What hardware unit and units correspond to the sound parameter passed through `SoundControlGate` and the lower routine at `0x800060d0`?
4. Does Beta3 alter acoustic delay, or only the parameter selected after a measurement result?
5. Is `0x80005a78` actually MainADCTask? Validate with bounded emulation/call context.
6. Which SoC UART is used by the RX ISR, and what peripheral/bus supplies the measurement frame?
7. Which Beta3 raw-diff ranges are GUI/profile additions versus measurement protocol modifications?
8. Can a future explicitly approved FEL read operation be designed without violating boot-ROM/SRAM reservations? No such operation is currently authorized.


## Resolved static portion — 2026-11-05

The patches at `0x800045e0` and `0x80004738` are observer wrappers, not changed frame construction or changed signed-24-bit parsing. The `0x8000461c` patch conditionally changes the state-3 `+0x30` field from 30 to 40.

Remaining: identify every read/decrement of `0x805ac694+0x30`, determine the meaning of control bytes at `0x805abefc+0/+2/+7`, and trace the field to a physical timer or protocol cadence before claiming a latency effect.


## 2026-11-05 narrowed questions

- Which indirect callback, scheduler, or alias consumes `0x805ac694+0x30` after the FSM writes it?
- Which writer establishes `0x805abefc+0 = 3` for the Beta3 30→40 condition?
- What semantic mode/event does HighspeedEventHandler's `+2` toggle represent?

The direct PC-literal-object paths have been tested; do not repeat that direct scan before pursuing interprocedural flow.


## 2026-11-05 PIO questions

- Which command descriptors at `0x8006367c` correspond to IDs 0x09–0x0f, and what protocol payload does each send?
- Which F1C100S PIO port/pins correspond to MMIO word `0x01c208c4`?
- What external circuit responds to the two-bit patterns?
- Continue indirect tracing of `0x805ac694+0x30`; the `0x800031b8` route has been disproven as a scheduler path.


## 2026-11-05 descriptor questions

- Which response/state paths associate descriptor IDs 09–0f with user-visible measurement modes?
- What peripheral or software transport is implemented by byte-output candidate `0x80006dc8`?
- Why do parser selector handling and descriptor IDs 0d/0e intersect, if they do? No association is assumed yet.


## 2026-11-05 UART2 questions

- Where are UART2 pinmux, divisor, line-control, and interrupt-enable registers configured?
- Which external IC/device is attached to UART2, and what are its documented frame semantics?
- Which RX frame values correspond to descriptor IDs 09–0f?
- Does the FSM `+0x30` field define a timeout for this UART2 transaction, and if so where is it consumed?


## 2026-11-05 UART2 initialization questions

- What exact CCU/UART input clock is active when divisor `0x0249` is programmed, and what resulting baud does it produce?
- Does the first `0x60 0x60` UART2 sequence reset, synchronize, or select the external measurement device?
- Which interrupt controller line/vector reaches the UART2 RX ISR after init?
- What condition marks an RX frame complete before FSM state 5 parses it?


## 2026-11-05 RX lifecycle answers and remaining limits

Resolved: the static condition for state-5 parser entry is now known for command IDs `0x1b` and `0x1d`: RX count >= 5 plus byte-0 header `0x5e`/`0x60`. The UART ISR itself does not supply a semantic end-of-frame signal.

Remaining:
- What protocol operations and external-device modes do IDs `0x1b`, `0x1d`, headers `0x5e`, and `0x60` represent?
- Which command/response path supplies signed values to each user-visible measurement mode?
- What frame-completion logic applies to descriptor IDs 09–0f and non-state-5 UART2 messages?
- What timer unit/clock source determines state-3 timeout behavior and actual UART baud?


## 2026-11-05 command-1b/1d questions

Resolved: '0x1b' and '0x1d' transmit '5e5e' and '6060' respectively, with matching state-3 reply-header gates. Both frames are unchanged in Beta3.

Remaining:
- What external protocol operation is represented by repeated '5e' or '60' bytes?
- Why does UART bring-up also emit '6060'?
- Which input-record/dispatcher case corresponds to each physical measurement mode?
- Which consumers use the state-5 signed result after the parser stores it?


## 2026-11-06 result-flow questions

Resolved: state-5 output fields are '+0x1c' (value/sentinel) and '+0x20' (selector) in object '0x805ac714'; ResultDispatch and two formatting candidates consume them. The ResultDispatch sentinel branch calls SoundControlGate.

Remaining:
- Which exact drawing/UI primitive consumes the prepared text from the two formatting paths?
- Which command/config condition selects the state-5 saturation path?
- Does the ResultDispatch-to-SoundControlGate path generate audible diode/continuity behavior, and under which proven input conditions?


## 2026-11-06 saturation-path questions

Resolved: control '+0x08' values '0x0d/0x0e' plus unsigned parsed value >= '0x1389' cause state 5 to publish sentinel '0x007fffff'. The visible code is identical in V3.8 and Beta3.

Remaining:
- What upstream input-record field supplies the case-2 control value, and which user-visible selection sets it to '0x0d' or '0x0e'?
- Does sentinel '0x007fffff' mean over-range, open circuit, or another protocol condition?
- Under what exact configuration does ResultDispatch's sentinel branch call SoundControlGate, and what output does that gate produce?

## Added 2026-11-06: V3.6 data delta

- What is the semantic role of the nine modified 32-bit cells at `0x80063ac8..0x80063ae8`? The surrounding `EnumKey*` text and a pointer load from `0x80042d98` establish a data-region association only; do not call it calibration, timing, key mapping, or an algorithm parameter without a consumer trace.
- Run and retain the V3.6 seeded PyGhidra inventory, then compare its known function windows against V3.8. Raw equality is a strong baseline, not a complete function-boundary proof.

## Added 2026-11-06: live-device boundary

- What are the non-main regions of the verified 16 MiB SPI backup: boot asset, persistent settings, calibration, log, or unused flash? Classify from image structure before treating any region as safe test storage.
- A full backup proves recovery capability, but what minimal reversible E2 instrumentation would record a useful parser, sound, or ADC event without overwriting calibration or boot data?
- If original V3.6/V3.8 physical behavior is required, which verified original package and complete flash layout are needed before replacing the currently confirmed E2-modified main image?

## Updated 2026-11-06: V3.6/V3.8 comparison status

- The first 13 bounded seed exports are identical V3.6/V3.8. Which unseeded functions reference the nine changed data cells near 0x80063ac8, and do they affect a user-visible behavior?
- Extend function discovery only from evidence-backed call/target seeds; do not turn equal bounded exports into a whole-image semantic proof.
- Passive UART-TTL capture remains a future high-value input when the adapter can be connected safely in normal firmware mode.
