# Reverse-engineering status

The project is actively reconstructing the original YS-4470 firmware; it is not complete and no reconstructed firmware is claimed equivalent yet.

## Confirmed static foundation

- Target CPU: Allwinner F1C100S / ARM926EJ-S. The main raw image is linked at `0x7fffffe0`; its eGON payload entry/load region begins at `0x80000000`.
- Original V3.8 local SHA-256: `7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`. Originals remain external/non-public inputs.
- The request/reply measurement FSM begins at `0x80004490`; its parser state includes `0x80004738`.
- `0x800073bc` is a UART receive ISR region with a buffer rooted at `0x805b408c` and a 200-byte bound.
- `0x80006e4c` is a sound-control gate which clamps its selector to 1–10 and invokes a lower sound routine.
- The likely diode/continuity result branch contains the established call site `0x80003a74` to the sound gate.

## Current version work

PyGhidra inventory tooling and a raw diff pipeline are committed in `tools/`. V3.8 and Beta3 have a first reproducible function-level comparison. Beta3 differs from V3.8 in 65 contiguous regions (931 bytes), including a static, caller-specific sound parameter override and a result-observation helper. See `RE_PROGRESS.md` and the session evidence JSON.

V3.6 is expected but was not accessible in this workspace at the time of analysis. No V3.6 comparison has been fabricated.

## Boundaries

- Candidate labels (notably `MainADCTask` at `0x80005a78`) remain hypotheses until independently validated.
- Static results do not prove display behavior, audible timing, live peripheral state, or measurement calibration.
- FEL evidence documents boot-ROM USB availability, not runtime debugging. No physical-device operation occurred in the 2026-11-04 analysis session.


## 2026-11-05: Beta3 FSM patch classification

The three previously open Beta3 changes in the request/reply FSM were traced with raw ARM words and bounded PyGhidra windows. The patches at `0x800045e0` and `0x80004738` are observer wrappers: each preserves the original operands before continuing with the original operation, while recording `*(u32 *)(0x805abbbc + 0xc)` and incrementing a field in the Beta3 state block at `0x800600ac`.

The patch at `0x8000461c` is behaviorally different: it replaces fixed `0x1e` with a helper that returns `0x28` only when bytes `[0x805abefc+0]`, `[+7]`, and `[+2]` are `3, 0x0e, 1`; otherwise it returns `0x1e`. The result is stored at `0x805ac694+0x30` immediately before FSM state 3. Static code shows this field is selected from values 30/40/50/80/100 in nearby FSM paths, but its unit and physical timing role remain unproven.


## 2026-11-05: object-access trace

A raw ARM PC-literal-object trace now covers the measurement FSM object at `0x805ac694` and the Beta3 selector's control object at `0x805abefc`. The FSM field `+0x30` is written with 80, 30/40, 50, or 100 and cleared by `TransactionBuilder`. No direct load of `[0x805ac694+0x30]` occurred in the bounded 96-word windows after its four verified PC-literal loads. This deliberately leaves interprocedural and alias-based consumers open.

The task beginning at `0x80005b70` drives `TransactionBuilder` and `MeasurementFSM`; in the traced path it reads FSM object `+0x34`, not `+0x30`. The original `HighspeedEventHandler` at `0x8000d294` toggles control byte `0x805abefc+2` and writes `+7` on specific branches. See `evidence/2026-11-05-literal-object-trace.json`.


## 2026-11-05: measurement-FSM PIO control

The suspected scheduler helper at `0x800031b8` is now classified as a PIO bit-clear helper; `0x800031cc` is its bit-set counterpart. Both modify `[r0+0x10]` using bit number `r1`.

`TransactionBuilder` supplies `r0=0x01c208b4` and clears bits 3 and 2. FSM state 1 supplies the same PIO sub-block and selects one of two bit patterns before sending a descriptor-table command: IDs `0x0b..0x0f` select bit3=1/bit2=0, while IDs `0x09..0x0a` select bit3=0/bit2=1. This proves a command-dependent two-bit PIO control path, but not pin names, electrical function, or measurement-mode mapping.


## 2026-11-05: descriptor framing for PIO-selected commands

The seven descriptors at `0x8006367c + 8*id` for IDs `0x09..0x0f` are now decoded in V3.8 and Beta3. Every entry supplies two source bytes. Send helper `0x80005e84` copies those bytes, appends their 8-bit sum, and calls `0x80006dc8` once per resulting three-byte frame.

Frames are identical in V3.8 and Beta3: `58035b`, `58045c`, `580159`, `58075f`, `580961`, `580a62`, and `580b63` for IDs 09 through 0f respectively. Therefore the Beta3 changes do not alter these command frames.


## 2026-11-05: UART2 measurement transport confirmed

The command-frame transport is now statically connected end-to-end. `MeasurementTransactionSend` calls `0x80006dc8` with selector 2. That routine selects literal base `0x01c25800` (UART2), waits for readiness bit 1 at `UART2+0x7c`, then writes the byte to `UART2+0x00`.

The RX ISR at `0x800073bc` uses the same `0x01c25800` base: it tests a status word at `+0x08`, reads the low byte at `+0x00`, and appends it to `0x805b408c` up to 200 bytes. UART2 pinmux, baud/line parameters, and the external peer are not yet recovered.


## 2026-11-05: UART2 pinmux and line configuration

UART2 bring-up is now statically traced. Call site `0x80005e3c` invokes generic UART init `0x80006bb8` with selector 2, a literal clock argument `720000000`, explicit baud argument `19200`, and interrupt-path flag 1. The init code configures PIO pin fields 7 and 8 at function value 3; the F1C100S pinctrl source maps PE7/PE8 function 3 to UART2 TX/RX.

The code shifts the clock argument to 180000000, divides by 19200, shifts the quotient by four, and programs divisor `0x0249` (DLL 49, DLM 02) under DLAB. It writes LCR low bits as 3 after clearing its low five bits. Post-initialization it emits `60 60` on UART2. Actual live baud remains conditional on the active input clock.


## 2026-11-05: UART2 RX lifecycle and state-5 admission

A bounded PC-literal trace now connects the UART2 RX count at `0x805ab938`, the RX buffer at `0x805b408c`, and the MeasurementFSM parser. The ISR at `0x800073bc` uses the current count as a buffer offset, writes one received byte, then increments and stores the count. Direct reset anchors found in the bounded trace are `0x80003f24`, `0x80003f44`, FSM state 1 at `0x80004558`, and synchronous command helper `0x80005f30`; this is not a complete alias-analysis claim.

The precise parser-admission rule is now proven for command IDs `0x1b` and `0x1d` only. FSM state 1 stores required count 5 and selects state 3. State 3 admits state 5 only when received count is at least 5 and buffer byte 0 is `0x5e` for command `0x1b`, or `0x60` for command `0x1d`. State 5 at `0x80004738` then combines bytes 1..3 little-endian and sign-extends bit 23.

This is a static state-5 parser-entry condition, not a general UART2 end-of-frame specification and not a protocol-semantic identification of either command.


## 2026-11-05: state-5 command frames and dispatchers

Descriptor export proves the two commands that enter the signed-24-bit state-5 path. Command '0x1b' has one source byte '5e' and wire frame '5e5e'; command '0x1d' has source '60' and wire frame '6060'. The checksum equals the one-byte source in both cases. V3.8 and Beta3 frames are byte-identical.

The TransactionBuilder at '0x8000489c' stores command words for FSM state 1, which indexes descriptor table '0x8006367c' and sends through UART2. Input dispatcher '0x80004390' has a direct '[0x1b]' build path; task dispatcher '0x80005b70' constructs '[0x1d]' for software case 3, '[0x1b]' for case 4, an input-derived two-byte prefix plus '0x1d' for case 2, and '[0x0c,0x22,0x13,0x1d]' for case 5.

The same bytes '6060' are also sent by UART2 bring-up. Byte equality alone does not establish that the startup sequence and command '0x1d' have the same external-device meaning. Dispatcher cases are software values, not proven user-visible measurement modes.


## 2026-11-06: state-5 result-object flow

State 5 writes its signed result to result object '0x805ac714+0x1c' and its bounded selector to '+0x20'. Its special threshold path writes sentinel '0x007fffff'. A bounded direct-access trace proves that ResultDispatch at '0x800037c0' reads both fields; its sentinel branch conditionally calls SoundControlGate '0x80006e4c'.

Two separate formatting/rendering candidates also directly consume these fields: '0x80045264' and '0x8005dc3c'. The latter has nearby '%.3f' formatting data. This establishes software dataflow from UART state-5 parsing toward presentation and one conditional sound-control gate; it does not identify the final drawing primitive, physical measurement mode, or buzzer timing.


## 2026-11-06: state-5 saturation control reconstructed

The state-5 saturation branch reads control object '0x805aae8c+0x08', not the current state-5 command ID. It accepts only values '0x0d' or '0x0e'. When the unsigned parsed value is at least '0x1389', it replaces result object '0x805ac714+0x1c' with sentinel '0x007fffff' and stores selector zero at '+0x20'. Otherwise it preserves the parsed signed value and the byte-4-derived selector.

Both the input dispatcher ('0x80004390') and task dispatcher ('0x80005b70') case-2 paths write an input-derived value to the control field. The task case-2 sequence has terminal command '0x1d'. In contrast, visible case-5 setup writes constant '0x22' to the control field, which cannot satisfy this branch's '0x0d/0x0e' comparison.

The relevant dispatcher, saturation, and literal ranges are byte-identical in V3.8 and Beta3. This proves a shared static saturation rule; it does not assign the input values, command cases, or sentinel to a physical measurement type.

## 2026-11-06: original V3.6 acquisition and bytewise baseline

The running Mr.Yang updater listed package `Project_February_V3.6_V02.26.6`. Its original `f1c100s.bin` was downloaded without invoking **Upgrade**, saved outside the public repository, and verified against the updater manifest: **5,943,296 bytes**, SHA-256 `7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9`.

A raw equal-layout comparison against the original V3.8 image found **10 contiguous difference ranges totaling 20 bytes**. Four bytes are eGON-header data at file offset `0x0000000c`; the remaining 16 changed bytes occur within nine 32-bit values starting at linked address `0x80063ac8`, immediately after `EnumKey*` text. The semantic role of that table remains unassigned. One static ARM PC-literal load reaches table base `0x80063acc` from `0x80042d98`; the bounded tracer found no direct field access within its 128-word window.

No changed instruction bytes were observed in this raw diff. This is strong evidence that the known V3.8 code paths are byte-identical in V3.6, but it is not a substitute for the scheduled V3.6 PyGhidra seeded-inventory export or a claim about hardware behavior.

## 2026-11-06: live FEL identity and recoverable flash baseline

A live, non-destructive FEL session enumerated one Allwinner F1C100s device at USB\VID_1F3A&PID_EFE8. The active WinUSB binding was verified and the SPI flash identified as Winbond model 40h, 16,777,216 bytes. A complete read-only 16 MiB image was backed up locally (SHA-256 ab1e0c4539a2e3e053af78b39c1be5d3b4d3c2934dc96b29d4fd5a9395008be3); the binary is intentionally not published because it may contain device-specific data.

The flash eGON main image begins at 0x50000, declares 5,943,296 bytes, and its complete SHA-256 is b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1. It byte-matches the local modified artifact beta-diode-profiles-e2/f1c100s-profiles-OFFLINE.bin; the payload SHA-256 is 4708beb05841b42543714d460e0f7928e2fe72aab7479a40cfa757ce7ef511d2. This supersedes earlier historical assumptions about the active image.

No flash or bootloader write, RAM code execution, or running-firmware memory observation was performed. FEL is treated as BootROM transport, not a runtime debugger.

## 2026-11-06: V3.6/V3.8 PyGhidra seed comparison

PyGhidra 3.1.0 was installed from the local Ghidra 12.1.4 bundled wheel, using JPype 1.5.2. A bounded ARMv5T seed inventory ran successfully on the verified original V3.6 and V3.8 inputs at link base 0x7fffffe0. All 13 evidence-labelled exports have identical exported assembly fingerprints, identical first-64-byte windows, and identical first-512-byte windows across the two versions. The paired set includes MeasurementFSM, TransactionBuilder, ResultDispatch, SoundControlGate, UART_RX_ISR, DiodeValidityBranch, and MainADCTask_candidate.

This function-level result is consistent with the earlier whole-image raw result of 20 non-instruction-byte differences. It covers only the bounded seeds, not every inferred function boundary or live behavior. Full machine-readable inventories and the comparator output are committed as dated evidence.

## 2026-11-06: original state-5 parser executed on ARM926

The installed Capstone/Unicorn environment now executes original V3.6 and V3.8 ARM instructions at `0x80004738..0x800047bc`, using the explicit Unicorn ARM926 CPU model. **2,976 synthetic cases per version (5,952 total) passed** against the independent high-level reconstruction, with identical result fingerprints between versions. All 34 instruction addresses were visited. The harness checks the expected output fields, exact write sets, source SHA-256, and the factory `r7=0` prologue.

New bounded result: control byte `0x805aae8c+1` is a sample-discard countdown. Any nonzero entry value is decremented and neither result field is updated, even when it becomes zero. Command `0x1b` forces selector zero; `0x1d` clamps RX byte 4 to 0..6. The existing unsigned saturation comparison means negative signed-24 values also become sentinel `0x007fffff` when control word `+8` is 13/14 and the discard counter is zero.

Evidence: [ARM926 parser experiment](evidence/2026-11-06-state5-arm926-emulation.json); reproduction: `tools/ARM_EMULATION.md`. Frame admission, the common FSM epilogue, peripheral behavior, and physical timing remain outside this experiment.

## 2026-11-06: discard count producers and persistent lifecycle

Original input dispatcher `0x80004390` sets control byte `0x805aae8d` to **2** in software cases 2 and 5 (stores at `0x80004468` and `0x800043ec`). Case 2 sets control word +8 from input byte +4 and passes [input[4], normalized input[5], 0x1d]; case 5 sets +8 to 0x22 and passes [0x0c,0x22,0x13,0x1d]. Cases 3/4 leave these control fields unchanged.

The producer and parser were executed with persistent RAM in both originals: 1,184 producer cases, 96 four-entry lifecycle scenarios (384 parser entries), and 16 task-guard cases passed. The first two admitted state-5 entries retain previous result fields, and the third can publish. This is a response count, not an established time interval.

Task guard `0x80005bb8` immediately admits only cases 3/4. Cases 2/5 take a deferred-copy branch and the later static path can call the input dispatcher at `0x80005cf4`. Thus duplicate case-2/5 store blocks in the task are not proof of normal immediate execution. A false candidate at `0x80005e60` was rejected because r4 is reloaded with UART startup buffer `0x805b4154` first.

Evidence: [producer/lifecycle experiment](evidence/2026-11-06-state5-discard-lifecycle.json). Original 5,952-case parser regression fingerprints remained unchanged; no hardware I/O occurred.
