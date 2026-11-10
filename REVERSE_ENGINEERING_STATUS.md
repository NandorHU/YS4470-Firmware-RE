# Reverse-engineering status

The project is actively reconstructing the original YS-4470 firmware; it is not complete and no reconstructed firmware is claimed equivalent yet.

## Current continuation (2026-11-08)

The completion/retry/resume gate and six original-hash-bound GaugeCmdTask/sound/GUI function packets are verified. See contributions/COORD-FUNCTION-PACKETS/README.md (360 instruction-byte checks, 388 CFG edges, four bounded original executions, 13 tests). GaugeCmdTask's static name binding reaches 0x80003dbc; its outer loop calls the still-candidate service0x80005b6c. The local index covers six packets; no global-data equivalence or physical timing is inferred.

Next reserved task: COORD-ADC-CADENCE. Reuse the completed FSM proof and packets to validate the task/service→FSM→delay placement before assigning raw polling cadence. Do not repeat local comparisons or infer milliseconds, acoustic speed, or a whole-firmware percentage.

## Confirmed static foundation

- Target CPU: Allwinner F1C100S / ARM926EJ-S. The main raw image is linked at `0x7fffffe0`; its eGON payload entry/load region begins at `0x80000000`.
- Original V3.8 local SHA-256: `7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290`. Both owner-approved originals are published with SHA-256 identities in original-firmware/manifest.json.
- The request/reply measurement FSM begins at `0x80004490`; its parser state includes `0x80004738`.
- `0x800073bc` is a UART receive ISR region with a buffer rooted at `0x805b408c` and a 200-byte bound.
- `0x80006e4c` is a sound-control gate which clamps its selector to 1–10 and invokes a lower sound routine.
- The likely diode/continuity result branch contains the established call site `0x80003a74` to the sound gate.

## Current version work

PyGhidra inventory tooling and a raw diff pipeline are committed in `tools/`. V3.8 and Beta3 have a first reproducible function-level comparison. Beta3 differs from V3.8 in 65 contiguous regions (931 bytes), including a static, caller-specific sound parameter override and a result-observation helper. See `RE_PROGRESS.md` and the session evidence JSON.

V3.6 is now a verified local original (SHA-2567523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9). Earlier unavailable-input notes below are historical; both originals now have bounded comparative execution evidence.

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

A raw equal-layout comparison against the original V3.8 image found **10 contiguous difference ranges totaling 20 bytes**. Four bytes are eGON-header data at file offset `0x0000000c`; the remaining 16 changed bytes occur within nine 32-bit values starting at linked address `0x80063aa8`, immediately after `EnumKey*` text. The semantic role of that table remains unassigned. One static ARM PC-literal load reaches table base `0x80063acc` from `0x80042d98`; the bounded tracer found no direct field access within its 128-word window.

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

## 2026-11-07: GUI event source linked to the discard path

Completed and re-verified the carry-over event-source experiment from 2026-11-06. Original GUI registration at 0x80051894..0x800518a4 binds callback 0x8000cfd0 to GUI object +0x2b8 with event argument 1. The same GUI setup assigns literal labels Diode/Buzzer to objects +0x2c0/+0x2c4, which this callback changes. This establishes a static UI association for the formerly unnamed event path.

The Diode-side event setup passes (2,0x0e,0x19) to event-record builder 0x80006778. The Buzzer-side setup passes the same tuple unless word 0x805ac788 equals exactly 1, in which case it passes (5,0x22,0x13). Both record paths feed the previously proven count=2 dispatcher behavior. The setting's user-visible meaning remains unknown.

Tests across original V3.6/V3.8: 900 event-builder cases, 64 GUI branch cases, 96 linked parser entries, 12 label/registration slices, and 18 mode-switch cases passed. Source/result fingerprints match between versions and the read-only 2026-11-07 rerun matched the saved evidence. Physical timing and analog measurement behavior remain unvalidated.

## 2026-11-07: Fast CONT identified, initialized and persisted

The previously unnamed word at 0x805ac788 is the **Fast CONT** option. English label assignment at 0x8004557c targets GUI label +0x320; checkbox +0x31c registers handler 0x8005a3bc. Executing the original handler and its state getter proves that widget state bit 0 is normalized to 0/1 and stored to this word.

The invalid-record default path sets Fast CONT to 1. The configuration record is 72 bytes at flash offset 0xf00000, with CRC32 over its first 68 bytes and little-endian checksum at +0x44. Original save and validation loops match independent zlib CRC32. The historical private 2026-11-06 E2 backup contains a valid record with Fast CONT=1.

Across V3.6/V3.8, 524 widget-state cases, 48 save cases, 48 valid loads, 144 damaged records rejected, 12 default cases, eight restore cases, six GUI binding slices and 14 checkbox-to-event checks passed. No physical device operation occurred. The result names the Buzzer-path selector, not its physical timing. See [evidence](evidence/2026-11-07-fast-cont-setting.json) and `tools/FAST_CONT_SETTING.md`.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

ResultDispatch special path 0x80003910 requires UI mode=4, Fast CONT=1 exactly, and config byte +7=0x22. Sound gate requires settings +0x10=1, clamps selector to 1..10, uses the unchanged tone table at 0x80063968, and programs PA2 function3/PWM0. Off writes zero active duty while PWM enable/clock-gating remain set. Next bounded task: reconstruct helper 0x80007c88 history/range selection and its calls into this verified gate.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

Four user-requested upstream projects are downloaded as clean detached, pinned checkouts. Five driver sources were cross-compiled for ARM926 (Zig0.13.0) and eight prebuilt SDK objects read separately. Among97 eligible reference functions per original, the conservative matching pass finds no new accepted whole-body/normalized candidates; it does not equate shared names, sizes, prologues or MMIO constants.

Per original:142 MMIO-literal leads,129 following-address-use candidates,10 CP15 leads and11,914 raw aligned BL candidates (1,004 target candidates). These are linear ARM hypotheses, not a recovered whole-firmware call graph. Full graphs are stored as deterministic gzip. Two watchdog helper behaviors at0x800085c4/0x800085e0 are independently executed on ARM926:32 total cases pass. Real PyGhidra exports six proof-backed entries per original, with five new RE_ labels and SoundControlGate's existing name retained. Seven positive/negative pipeline tests pass. Firmware originals and the physical device are unchanged.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

Applied pinned F1C100S register references to five original routines: INTC vector dispatch0x80005260, registration0x80005274, timer configure0x800071a0, enable0x8000725c and timer0 status update0x8005bf54. Both originals pass4446 combined cases. Startup slice configures interval24000/control7 and IRQ13; nominal1kHz depends on24MHz source, not a measured response cadence. The IRQ bridge gives pending bit13 its own tick/scheduler path.

Continued the existing measurement track: Fast CONT helper0x80007c88 is now reconstructed and runs through the original gate/PWM path. An independent, freestanding C component is compiled for ARM926 and executed separately. Original ARM, Python and compiled C agree on3958 persistent state steps (700 scenarios across both originals). The filter retains the previous median/tone during unstable histories; input>1000 resets it. Physical units, power-on initial state, fresh-reply coupling and acoustic timing remain open. Full firmware reconstruction is still incomplete.

Next: Trace fresh-result admission from ResultDispatch call0x80003970 into helper0x80007c88. Determine whether repeated calls can reuse one parsed UART result. Separately bound tick/scheduler0x80061fa4/0x800612f8 and the consumer/decrement of FSM field0x805ac694+0x30 before assigning timing units.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

The original refresh callback0x8005d048 can refill the filter from one unchanged stored result in the bounded model. It enqueues a poll, uses UI+9 for an initial two-call warmup, then calls actual ResultDispatch0x800037c0. Five callback invocations produce filter counts[0,0,1,2,3] without any parser entry; parser discard count stays2. This does not establish live callback timing or full GUI/queue behavior: queue, renderer, printf and creation APIs are explicit stubs.

The caller divides signed raw data by float32 bits0x452f499a, clamps negative finite values to0 and rejects>=1000 before the filter. Accepted helper arguments are0..999. Sentinel/upper-limit paths request off while preserving history/median. The helper's standalone>1000 reset is therefore not the policy of this caller. 752 bounded cases/steps across originals pass with matching fingerprints;10 real Ghidra exports and9 guard/provenance tests pass.

Corrected old analysis seeds:0x800037bc is literal0x805abf10, not a function entry;0x8005d1a0 is a callsite inside callback0x8005d048. Historical comparisons remain saved seed/window evidence. New exports record seed revision and the comparison tool rejects incompatible provenance. Next: Audit real renderer0x8000326c and enqueue path0x80006778 for side effects excluded from the refresh model. Then prove FSM+0x30's cached read at0x800044a8 (r1=sb via ADD#0), its elapsed-tick comparisons and tick getter0x80061f84; do not assign milliseconds before that contract is validated.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

Removed the preceding model's top-level event-builder and renderer stubs. Original queue initializer0x800029dc requests10 slots of68 bytes, stores its handle at0x805aae90, and calls constructor0x80061838. Constructor/list initialization, available send/copy, full zero-wait rejection and critical enter/exit now execute; only the heap allocation return is modeled. Renderer control and helpers0x8000406c/4114/425c/4290/4314/2e44 also execute, with graphics/text/log leaves explicit.

Across originals,2396 checks pass:72 queue,2304 renderer,6 critical,4 initialization and10 linked callback steps. The five-callback stored-result example persists with five real event copies in an original-code-constructed queue. No parser entry occurs, discard remains2, filter fill reaches3 and emulated active becomes1. The tested queue/renderer paths preserve protected freshness/filter state. Fourteen real Ghidra exports and9 guard tests pass. Blocking/waiter paths, full GUI, asynchronous logs and live timing remain open.

Next: Prove FSM+0x30's cached reader0x800044a8 through r5 and elapsed-tick branches0x800046a8/0x800046c4/0x80004720 using real getter0x80061f84 and the verified critical helpers. Test threshold boundaries and32-bit tick wrap before assigning units or interpreting Beta3's30-to40 change. Keep blocked queues, waiters and remaining GUI/log leaves separate.

## 2026-11-07: shared contribution entry point and original-input publication

The owner requested that contributors using their own AI resources can join any
relevant subsystem while the current Codex agent remains coordinator. See
[CONTRIBUTING.md](CONTRIBUTING.md), [current handoff](collaboration/CURRENT_HANDOFF.md),
[task registry](collaboration/TASK_REGISTRY.json) and the task/AI/handoff templates.
Six bounded tasks are available, the FSM timeout/tick task is reserved to the
coordinator, and passive hardware capture is blocked pending real access/evidence.
Only the registry on the integration branch assigns ownership; issue requests,
forks and PRs do not constitute accepted work. No external agent was assigned or
launched by this publication.

The owner also explicitly requested publication of original V3.6/V3.8 application
images. The two 5,943,296-byte inputs are preserved unchanged under
original-firmware/V3.6 and V3.8 with the existing SHA-256 identities in
[manifest.json](original-firmware/manifest.json). Personal 16 MiB recovery backups
remain private. The 1.0 Release image remains distinct. All publication work is
on the development branch; main is not changed.

This is coordination/input-access work, not a new firmware-function proof or
completion-percentage increment. The next technical experiment remains the
cached FSM+0x30 read at0x800044a8, elapsed-tick branches0x800046a8/0x800046c4/0x80004720
and tick getter0x80061f84, including threshold and32-bit-wrap boundaries.

Publication validation from an isolated checkout: nine existing provenance tests
pass, and all 2,396 original-byte checks reproduce the previously committed
fingerprints using the two repository input paths. The 61 checked relative links
resolve. Details: `evidence/2026-11-07-collaboration-publication.json`.

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

Original V3.6/V3.8 pass 13,302 checks with identical result fingerprints. Of these,
12,914 compare original ARM926 instructions, an independent Python transition
specification and independently compiled freestanding C. The remaining probes
cover the real tick getter/critical helpers, tick-advance prefix, original
transmit setup, cache interventions and a clearly marked budget40 fixture.
Four real Ghidra assembly/decompiler exports and nine provenance tests pass.

FSM+0x2c is a start-counter snapshot; +0x30 is a duration loaded into R5 once per
invocation, not a decremented countdown in the tested wait paths. Unsigned
modulo-32-bit elapsed >= duration expires. State3 accepts an already complete,
valid-header reply before reading the deadline. Original command IDs0x1b/0x1d
seed duration30/required5 after the send call; other tested setup commands seed80.
ACK for IDs9..15 starts a new duration50, or100 for13/14, in state4.

The tick getter0x80061f84 reads0x805abbc8 under the original critical helpers.
PIO writes are inert shadows; UART send is an explicit leaf model. The tick
prefix is stopped before full RTOS wrap/ready-list handling. No Beta3 image,
physical tick frequency, real UART or acoustic delay was measured.

A second pure-C component, reconstruction/fsm_timeout.c/.h, is independently
buildable but reconstructs only timed states2/3/4. The function database now has
59 records of differing confidence; this is not a completion percentage.

Next reserved task COORD-ADC-CADENCE: Validate the MainADCTask candidate 0x80005a78 and actual callers of FSM 0x80004490; bound one task-loop iteration and the delay candidate 0x80060fbc before assigning a polling cadence. Keep GUI callback periods, live clock frequency and acoustic latency separate.


## 2026-11-08: local-model collaboration and checked examples

See [local collaboration](collaboration/LOCAL_LLM.md) and the isolated
[reviewed external snapshot](https://github.com/NandorHU/YS4470-Firmware-RE/tree/460405fa04971992d2d8830bac1d6ba914a927fc/contributions/EXT-EVIDENCE-AUDIT). Six local reviews completed;6 existing
facts and7 known limits were confirmed,11 findings rejected, and no new firmware
claim was accepted. The previous31-task draft has22 token-cutoff responses and
unverified binary provenance; its source hashes match but its hypotheses remain
quarantined. Checked lessons are in-context examples, not weight training.
The two-case check scored0/2 before and1/2 after; general reliability and overall
speedup remain unproven. Keep local tasks small and tool-grounded while the main
agent continues COORD-ADC-CADENCE. The13,302-check FSM proof is unchanged.


## 2026-11-08: local completion gates and full function packets

The latest continuation and collaboration/CURRENT_HANDOFF.md supersede historical continuation blocks below.

The completion/retry/resume gate and six original-hash-bound GaugeCmdTask/sound/GUI function packets are verified. See contributions/COORD-FUNCTION-PACKETS/README.md (360 instruction-byte checks, 388 CFG edges, four bounded original executions, 13 tests). GaugeCmdTask's static name binding reaches 0x80003dbc; its outer loop calls the still-candidate service0x80005b6c. The local index covers six packets; no global-data equivalence or physical timing is inferred.

Next reserved task: COORD-ADC-CADENCE. Reuse the completed FSM proof and packets to validate the task/service→FSM→delay placement before assigning raw polling cadence. Do not repeat local comparisons or infer milliseconds, acoustic speed, or a whole-firmware percentage.

Installed and tested promptfoo0.125.1, DSPy3.4.1 and MCP2.3.0 in an isolated prefix; a scoped local-model→REA call succeeded. See contributions/COORD-LOCAL-TOOLS/README.md. The packet comparison verified3/3 complete-context versus1/3 short-window instruction answers in a deliberately small source-coverage test. Two short-context tasks remain needs_split; none is silently complete. No weight training, paid API or physical-device access occurred.


## 2026-11-08: public factory-input patcher

The public factory-input patcher in patcher/ now accepts pinned original V3.6/V3.8 applications and personalized16 MiB containers, without a private Beta3 backup.14 regression tests and12 bounded original ARM926 loader-window cases passed. V3.8 continuous matches the downloaded public1.0 application; V3.6 retains version-specific factory bytes and is offline-tested only. No bootloader/logo replacement or device operation is performed.

See contributions/COORD-PUBLIC-PATCHER/README.md and validation.json. This does not establish a new physical speed gain. The user redirected the current session to distribution after profile-source inspection. COORD-ADC-CADENCE remains in progress; its exact source/E2-hash checkpoint is contributions/COORD-ADC-CADENCE/STATUS.md and profile-inputs.json. No four-profile comparison was executed in this session.


## 2026-11-08: bundled English installer released

The English Windows installer is published as [1.1.0-beta.2](https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/installer-v1.1.0-beta.2) ([Windows ZIP](https://github.com/NandorHU/YS4470-Firmware-RE/releases/download/installer-v1.1.0-beta.2/YS4470-Installer-1.1.0-beta.2-Windows-x64.zip)). It includes factory V3.8, its Python/Tcl/Tk runtime, the pinned FEL utility and the official driver helper. Automatic backup/second-read confirmation/application-only writes/full readback are covered by19 simulated transport/driver-launch tests; the public patcher has14 original-input regression tests. The clean GitHub Windows build passed and all four uploaded asset digests were verified before publication. No device was written; GUI visual control was not established, and this new installer/FEL package is physically untested.

The public ZIP was downloaded again and verified against SHA256SUMS/GitHub asset digest; its included original is7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290. Firmware remains the existing1.0 application; this release versions the installer. Resume COORD-ADC-CADENCE from contributions/COORD-ADC-CADENCE/STATUS.md. No equal-Highspeed four-profile event matrix or new physical speed cause was established by distribution work.


## 2026-11-08: equal-Highspeed profile evidence

The equal-Highspeed E2 comparison is now executed:64 waveform cases,64 active/requested switches,16 existing-candidate comparisons and268 assertion groups. Six packet identities/360 instruction bytes were rechecked. Direct removes a modeled GUI sound wait (accepted106/sound106 versus Base accepted106/sound125), with unchanged Base/Direct polling. This is not physical timing; the reported Base advantage remains unproven. Public-stock replay now reproduces the existing offline reply-audio/E2 inputs. See contributions/COORD-ADC-CADENCE/README.md and profile-validation.json.


## 2026-11-09: original UART correlation proof

The original UART-send leaf has now been replaced by executed original descriptor framing, UART2 byte-output polling and RX ISR in a bounded FSM experiment.12,704 original/Python/separate compiled-ARM-C transport cases passed across factory3.6/3.8, alongside184 arrival schedules and12 explicit ISR interleaves. An old matching-header response can be published after a retry or survive an IRQ-enabled gap after RX clear/before TX. This proves a controlled stale-frame counterexample, not external ADC behavior or a physical Base advantage. See contributions/COORD-ADC-CADENCE/uart/README.md, validation.json and six fresh Ghidra exports. No firmware/device/Release update occurred.


## 2026-11-09: admitted-frame stability and caller ownership

A further1,200 original ARM926 cases show that the UART ISR's append-only path preserves the admitted five-byte prefix before/during state5 parsing under valid-count/no-other-writer conditions.24 original service-gate cases admit the deferred control fallback only when idle. All nine raw BL candidates for synchronous helper0x80005f14 are classified into GaugeCmdTask startup/deferred handler CFGs; an additional tail branch0x8000404c was found. The proof does not establish global mutual exclusion or remove the earlier late same-header ambiguity. See contributions/COORD-ADC-CADENCE/admission/README.md and validation.json.


## 2026-11-09: local model restored and startup-helper execution

The owner's requested local-model restart is complete: the existing signed Ollama0.40.15 and pinned coder14B run on127.0.0.1:11435 with existing weights, loopback/cloud-disabled settings and reported full GPU residency at context4096. Two previously transport-failed extraction tasks completed; manual review accepted3/4 extracted roles and rejected a pointer-literal/UART-status confusion. A new checked-example exercise passed, without weight training or a general-quality claim. Independently,40 original ARM926 cases executed the synchronous startup helper for proven arguments9/19 on both originals. See contributions/COORD-ADC-CADENCE/synchronous/README.md. No firmware patch/device/Release change.


## 2026-11-09: account-migration handoff prepared

The owner requested a complete transfer to another account. See
[migration/2026-11-09/README.md](migration/2026-11-09/README.md), its detailed
AGENT_HANDOFF.md, tool/setup inventory and machine-readable ARTIFACTS.json.
Research baseline remains a2e5e7ebd2f661f37f88507f55a62a14c5df3f9f;
62 function records. No new firmware finding or changed hardware claim is
introduced by this documentation session. The existing memory/hardware/
algorithm evidence and uncertainties remain as recorded above.

A fresh public checkout passed14 patcher tests,40 existing startup-helper
cases and six-packet validation (360 byte checks/388 CFG edges/four outer-loop
runs); READINESS_VALIDATION.json records this portability check. Originals were
rehashed. A full-history bundle/source kit and local environment inventory are
prepared separately without private dumps, credentials or model weights.
The beta.2 GitHub Release currently returns404 although its tag/source remain;
the exact previously published Windows ZIP is retained locally with its pinned
hash. No republishing, main/device write or automation change was performed.

Next research task remains COORD-ADC-CADENCE: further reachable deferred-handler
arguments/record producers and aliases before broader shared-buffer claims;
startup IDs9/19 are already proven. The old daily automation is still active
at08:00 Europe/Budapest and must be deliberately switched during account takeover.
The prepared handoff does not silently release ownership or start a second agent.

## 2026-11-09: original deferred producer paths

Four original caller suffixes now run through the record producer at `0x80006778`, the idle service at `0x80005b6c`, the fallback at `0x80003dd8` and the synchronous helper at `0x80005f14`. Sixteen ARM926 cases across V3.6/V3.8 agree for IDs `0x26`, `0x27`, `0x2a` and `0x2b`, with a first-check header and with no reply. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json).

## 2026-11-09: extended deferred status

Original callers `0x8000e50c` and `0x8000e5a0` reached the idle fallback's extended branch at `0x80003eb8` on V3.6 and V3.8. After the command ACK, two original critical sections cleared the RX count and buffer. The separate status loop mapped `a0 01..03` to 1–3 and `a1 01..04` to 4–7. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

Both originals passed 40 status cases and eight linked four-deadline UI sequences. The original calibration button registration, timer constructor and due gate, Thumb formatter, and label copy were exercised. The mapped strings cover power-on success, two calibration successes, three EEPROM errors and calibration over-range. See the [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json) and the separate [producer index](contributions/COORD-ADC-CADENCE/synchronous/control-producer-index.json).

## 2026-11-09: original control queue and type 6

Across both originals, the [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json) passed 38 cases covering the original queue lifecycle, type-6 UART2 setup after ACK success/failure, ring wrap, deferred overwrites and ordering relative to immediate measurement records. The [queue reference index](contributions/COORD-ADC-CADENCE/synchronous/control-queue-index.json) bounds direct queue-send and handle references.

## 2026-11-09: dynamic type-2 selection and compiled plan

Both originals agree in 36 Highspeed callback cases, 20 adjacent/paired callback cases and 512 exhaustive byte-to-second-send cases. Separately compiled ARM C agrees with the original dispatcher and builder in 4,108 plan cases. See the [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json) and [compiled-plan differential](contributions/COORD-ADC-CADENCE/synchronous/measurement-plan-validation.json).

## 2026-11-09: refresh and first publication

The [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json) adds 18 matching V3.6/V3.8 sequences across successful, missing and wrong-header replies, a busy overlap, and reconfiguration in both directions. In the overlap the original queue accepts a refresh request, the busy service skips it, and the refresh still reaches ResultDispatch with the prior stored result.

## 2026-11-09: refresh rendering and sound

The [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json) adds 18 lifecycle sequences with original scaling and renderer control, plus two integrated Fast CONT/PWM sequences. It verifies stale value reuse across the prior busy overlap and reconfiguration. Widget updates and numeric formatting are explicit fixtures.

## 2026-11-10 — Native mode entry and sound expiry

Across V3.6 and V3.8, 16 original UI transition and 12 original countdown suffix cases agree. Fast CONT selects type 5 for the tested mode 1 to 4 transition with the setting enabled. The tested mode 4 to 3 transition selects type 2. Both preserve the seeded stored result and filter history through configuration. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).
