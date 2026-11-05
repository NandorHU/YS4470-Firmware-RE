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
