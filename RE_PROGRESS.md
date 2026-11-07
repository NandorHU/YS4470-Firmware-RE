# Reverse-engineering progress

**Last verified update:** 2026-11-07  
**Development branch:** `re/2026-11-04-pyghidra-fel`

## This session: verified results

- A bounded PyGhidra inventory pipeline now runs with Ghidra 12.1.4, PyGhidra 3.1.0, Jpype1 1.5.2, language `ARM:LE:32:v5t`, and link base `0x7fffffe0`. It exports seeded-function assembly, decompiler output, direct calls, fixed byte-window hashes, and evidence/confidence fields. It intentionally does not represent a full automatic ARM/Thumb analysis.
- The V3.8-to-Beta3 raw equal-layout comparison found **65 changed ranges totaling 931 bytes**. Therefore Beta3 must not be described as a two-patch firmware.
- At V3.8 `0x80006e80`, Beta3 replaces the factory sound-table load with a helper at `0x80010754`. The helper retains the original `ldrh`, and only when its caller return address equals `0x80003a78` it substitutes `r6 = 0x529` (1321 decimal). The target is the previously identified sound-gate call at `0x80003a74`. This proves a call-site-specific sound-parameter override; it does **not** yet prove a physical buzzer frequency or a shorter acoustic delay.
- At V3.8 `0x800037fc`, Beta3 calls helper `0x80060130` instead of loading `[r7,#0x1c]` directly. The helper restores that original load into `r0` and records value/context changes in a new state block rooted at `0x800600ac`. The exact UI/measurement semantics remain a hypothesis.
- A local V3.6 original was not present in the currently accessible workspace. The tooling supports it; no V3.6-to-V3.8 conclusion has been invented.
- The repository contains a deliberately restricted FEL helper. Its offline policy/parser self-test passed. It can issue only `sunxi-fel --list` and `sunxi-fel spiflash-info`; it contains no flash write, RAM execution, arbitrary memory access, boot, or erase operation.
- No USB/FEL operation was executed in this session. Existing 2026-11-02 project artifacts record an F1C100S FEL enumeration and a Winbond 16 MiB SPI-flash identification; that record is historical, not a claim about current device state.

## Exact continuation point

1. Trace the remaining Beta3 changes around `0x800045e0`, `0x8000461c`, and `0x80004738` through the request/reply FSM. Classify each as protocol acceptance, measurement-state change, or unrelated behavior before making latency claims.
2. Obtain or register the original V3.6 image in a local non-public input directory, validate its SHA-256 locally, then run `tools/pyghidra_inventory.py` and `tools/compare_inventories.py`. Do not upload original firmware binaries.
3. Convert the confirmed static call-site sound override into a bounded emulation experiment only after identifying the surrounding parameter contract.
4. Perform a fresh live FEL probe only when the device is intentionally connected; retain its captured output as dated evidence. Never expand the probe to writing, arbitrary memory reads, or RAM code execution without explicit approval.

See `evidence/2026-11-04-pyghidra-beta3-compare.json` for machine-readable session evidence, `FUNCTION_DATABASE.json` for the cross-version function database, and `FEL_ANALYSIS_PLAN.md` for the safety-gated hardware plan.


## 2026-11-05: FSM deltas classified

- `0x800045e0`: V3.8 calls `0x80005e84`; Beta3 calls `0x800586ec`, which records `*(u32 *)(0x805abbbc+0xc)` at `0x800600ac+8`, increments `+0x38`, restores `r0/r1/r12/lr`, and tail-branches to the same original target. **Observer only.**
- `0x80004738`: V3.8 starts parsing with `ldrb r4,[r12,#1]`; Beta3 helper `0x8005871c` records context at `+0x3c`, increments `+0x2c`, restores registers, and executes that exact original load. **Observer only.**
- `0x8000461c`: V3.8 writes fixed 30 to FSM object `0x805ac694+0x30`; Beta3 helper `0x80058750` selects 40 only for control tuple `(3, 0x0e, 1)`, otherwise 30. **Semantic change in an unresolved FSM phase-budget/interval field.**
- Test: bounded PyGhidra trace exported successfully; raw control-flow assertions and five selector cases passed.
- No physical device, USB, FEL, flash, firmware, or RAM-code operation occurred.

### Revised exact continuation point

1. Locate the read/decrement/check path for `0x805ac694+0x30` and establish its unit from code, not assumption.
2. Trace writers of `0x805abefc+0`, `+2`, and `+7`, then attach descriptive names only with proof.
3. Continue V3.6 intake once its original binary is accessible; do not substitute Beta3 for that requested comparison.


## 2026-11-05: direct object-access trace

- Added `tools/trace_arm_literal_object.py`: raw ARM PC-literal-load tracer with a bounded simple-MOV alias window. Its self-test passed.
- `0x805ac694` has four verified PC-literal loads: `0x80004494`, `0x80004850`, `0x800048a0`, and `0x80005b94`.
- Direct trace: FSM writes field `+0x30` at `0x80004608`, `0x80004620`, and `0x8000466c`; TransactionBuilder clears it at `0x800048d4`. No direct `LDR [object+0x30]` was found in the bounded windows. This is not an indirect-flow absence proof.
- The task at `0x80005b70` uses FSM object field `+0x34` as a gate and invokes both `TransactionBuilder` and `MeasurementFSM`.
- `HighspeedEventHandler` `0x8000d294` proves that control byte `0x805abefc+2` is toggled 0/1 and that `+7` receives branch-specific values. It does not prove the semantic names of those fields.
- Tests: source self-test, generated V3.8 object traces, and assertions all passed. No physical I/O occurred.

### Revised exact continuation point

1. Trace `0x800031b8` and any callback/task registration that can consume the FSM object indirectly, with attention to `+0x30`.
2. Trace a concrete source of control byte `0x805abefc+0 = 3`, especially the non-immediate write at `0x8000d74c`.
3. Keep V3.6 intake pending its original binary path; no Beta3 result substitutes for V3.6/V3.8 comparison.


## 2026-11-05: PIO helper and command-path correction

- `0x800031b8` is **PIOBitClear**, not a scheduler: it clears `[r0+0x10]` bit `r1`. `0x800031cc` is the corresponding set helper.
- TransactionBuilder calls PIOBitClear for bits 3 then 2 with `r0=0x01c208b4`, affecting MMIO word `0x01c208c4`.
- FSM state 1 sets command-dependent PIO states immediately before the send routine: IDs `0x0b..0x0f` give bit3=1/bit2=0; IDs `0x09..0x0a` give bit3=0/bit2=1.
- The descriptor table base is `0x8006367c`; code loads the descriptor pointer and its byte 4 before `0x80005e84`.
- Test: bounded PyGhidra trace plus PIO control assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Decode `0x8006367c + 8*id` descriptors for IDs `0x09..0x0f` and map their sent bytes/lengths.
2. Derive PIO register port/pin semantics from verified SoC documentation and firmware initialization; do not infer electrical board function.
3. Independently continue the indirect consumer search for `0x805ac694+0x30`; PIOBitClear is excluded.


## 2026-11-05: command descriptors 09–0f decoded

- Added `tools/extract_measurement_descriptors.py`; its synthetic self-test passed.
- Table `0x8006367c`, IDs 09–0f: each entry holds a two-byte source pointer/count. `0x80005e84` appends the modulo-256 sum and emits three bytes through `0x80006dc8`.
- Verified frames are identical V3.8/Beta3: `58035b`, `58045c`, `580159`, `58075f`, `580961`, `580a62`, `580b63`.
- The previous interpretation that the third adjacent pool byte belonged to each descriptor was corrected: it is the first byte of the next two-byte record; checksum is runtime-generated.
- Test: frame expectations plus send-helper instruction assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Trace byte-output candidate `0x80006dc8` and determine its transport/peripheral contract.
2. Correlate IDs 09–0f with reply parser behavior, preserving the unproven status of their physical measurement names.
3. Keep the FSM `+0x30` indirect-consumer analysis separate from this now-confirmed PIO/frame path.


## 2026-11-05: UART2 transport resolved

- `0x80006dc8` is confirmed as the measurement UART byte transmitter. Selector 2 chooses `0x01c25800` (UART2); it polls `+0x7c` bit 1, then writes the byte to `+0x00`.
- The descriptor sender explicitly passes selector 2. Therefore every decoded command frame in this path is sent through UART2.
- RX ISR `0x800073bc` uses the same base, tests `UART2+0x08` bit 2, reads `+0x00`, and appends to buffer `0x805b408c` with a 200-byte cap.
- Test: UART2 TX/RX static assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Locate UART2 initialization and pinmux/clock configuration; identify divisor, LCR/FCR/IER writes with evidence.
2. Trace RX-buffer completion from `0x805b408c` into FSM parser state 5 and map frame boundaries.
3. Revisit FSM `+0x30` only after a UART2 transaction timeout/check path is found.


## 2026-11-05: UART2 bring-up decoded

- UART init call site `0x80005e3c` passes UART selector 2, literal clock argument 720000000, baud argument 19200, and interrupt flag 1 to `0x80006bb8`.
- Generic init configures PIO pin fields 7 and 8 at function 3; F1C100S Linux pinctrl maps PE7/PE8 function 3 to UART2 TX/RX.
- It computes/programs divisor `0x0249` (DLL=49, DLM=02), writes FIFO/control values, toggles DLAB, and finishes LCR lower field at 3.
- The post-init UART2 startup sequence is `60 60`.
- Test: UART2 initialization assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Trace RX-buffer count `0x805ab938` and buffer `0x805b408c` reset/completion paths into parser state 5.
2. Derive the complete UART2 frame-boundary rule before mapping response bytes to measurement values.
3. Treat 19200 as the firmware's requested argument; calculate actual baud only after validating the active UART clock source.


## 2026-11-05: UART2 RX lifecycle and state-5 gate

- New repeatable PyGhidra tool: `tools/trace_uart2_rx_lifecycle.py`.
- It identified direct bounded reset anchors for RX count `0x805ab938`: `0x80003f24`, `0x80003f44`, `0x80004558`, and `0x80005f30`. ISR `0x800073bc` stores each byte into `0x805b408c + count`, then increments the count.
- For FSM command `0x1b`, state 3 requires at least five received bytes and byte 0 = `0x5e`; for `0x1d`, it requires at least five and byte 0 = `0x60`. Only then does it select state 5.
- State 5 reads bytes 1..3 as a signed little-endian 24-bit value. This is a parser-entry rule for two commands, not a generic UART2 framing rule.
- Test: `py_compile`, tool self-test, and 26 raw-instruction assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Locate descriptor-table entries and callers for command IDs `0x1b` and `0x1d`; export their exact UART2 wire frames.
2. Trace the signed result destination from state 5 into its consumers and UI/measurement-mode selection.
3. Do not reuse the five-byte/header condition for IDs 09–0f unless their own control flow proves it.


## 2026-11-05: state-5 command frames and dispatch

- Exported V3.8 and Beta3 descriptors: '0x1b -> 5e 5e'; '0x1d -> 60 60'. Both are one-byte source plus additive checksum and are identical across the two versions.
- TransactionBuilder receives command lists from input dispatcher '0x80004390' and task dispatcher '0x80005b70'. The latter proves case 3 → '[0x1d]', case 4 → '[0x1b]', and case 5 → '[0x0c,0x22,0x13,0x1d]'; a case-2 list ends in '0x1d' after two input-derived values.
- '0x1d' wire bytes equal the UART2 bring-up bytes '60 60'; equality is recorded as a protocol observation, not a semantic conclusion.
- Test: descriptor exporter self-test, command-sequence tracer self-test, Python compilation, two-version frame assertions, and seven direct TransactionBuilder-call scan passed. No physical I/O occurred.

### Revised exact continuation point

1. Resolve state-5 result-target literals at '0x8000481c..0x80004820' and trace writes at '0x800047b4..0x800047b8'.
2. Identify consumers that map the signed value/selector to UI or measurement state.
3. Preserve dispatcher case tags as unlabelled software values until a downstream physical/UI mapping is proven.


## 2026-11-06: state-5 result flow

- State 5 publishes value/sentinel at '0x805ac714+0x1c' and selector at '+0x20'. The special path can store '0x007fffff'.
- ResultDispatch '0x800037c0' reads both fields. Its sentinel branch conditionally calls SoundControlGate '0x80006e4c'.
- Static text/formatting consumers at '0x80045264' and '0x8005dc3c' also read the result fields; the latter has a nearby '%.3f' literal.
- Test: new PyGhidra result-flow tracer compiled; self-test and 16 instruction/literal assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Trace the special state-5 branch via '0x805aae8c+0x08' and identify its command/config source.
2. Determine when threshold '0x1389' yields sentinel '0x007fffff'.
3. Trace ResultDispatch's conditional SoundControlGate call without claiming a physical buzzer behavior until hardware/control evidence exists.


## 2026-11-06: state-5 saturation path

- State 5 reads '0x805aae8c+0x08'; only control values '0x0d'/'0x0e' proceed to its special path.
- If unsigned parsed value >= '0x1389', it publishes '0x007fffff' at result '+0x1c' and selector zero at '+0x20'.
- Case-2 setup in both dispatchers writes an input-derived control value; the task-level command list ends in '0x1d'. Visible case-5 setup writes '0x22' instead.
- V3.8/Beta3 raw comparisons: input dispatcher, task dispatcher, state-5 saturation code, and literal ranges are identical.
- Test: tracer compilation/self-test and 20 instruction/literal assertions passed. No physical I/O occurred.

### Revised exact continuation point

1. Trace ResultDispatch's sentinel branch and its call to SoundControlGate '0x80006e4c'.
2. Establish the sound-gate argument values and first hardware-facing operation without claiming audible behavior.
3. Separately map the upstream case-2 input field to a UI/measuring mode.

## 2026-11-06: original V3.6 retrieved safely and raw-compared

- Inspected the running Mr.Yang updater without activating **Upgrade**. Its firmware-list manifest named `Project_February_V3.6_V02.26.6` and supplied the expected SHA-256.
- Retrieved original `f1c100s.bin` into a local non-public input directory. Verification passed: **5,943,296 bytes**, SHA-256 `7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9`.
- Ran `tools/diff_raw_images.py` against verified V3.8: **10 ranges / 20 bytes**. Four bytes are at eGON-header offset `0x0c`; 16 bytes alter nine unclassified 32-bit table cells at linked `0x80063ac8..0x80063ae8`.
- Ran `tools/trace_arm_literal_object.py` self-test and bounded trace. V3.8 `0x80042d98` PC-loads literal table address `0x80063acc`; no direct table field access appears in the next 128 ARM words. This is bounded, not a global negative result.
- No physical I/O, FEL operation, device-memory access, firmware flashing, bootloader change, or RAM code execution occurred. The firmware binary itself is deliberately excluded from GitHub.

### Revised exact continuation point

1. Restore/use the existing PyGhidra environment to export a bounded V3.6 seed inventory, then run the inventory comparator against V3.8.
2. Trace the function containing `0x80042d98` until the V3.6/V3.8 table data has a narrow evidence-backed role.
3. Continue the pending ResultDispatch sentinel → SoundControlGate argument/peripheral trace as a separate task; do not conflate it with the V3.6 data delta.

## 2026-11-06: live FEL transport and full flash identity

- Live USB/PnP verified FEL BootROM hardware ID USB\VID_1F3A&PID_EFE8; Windows binds it to WinUSB/libwdi. The updater was closed to eliminate a potential handle conflict.
- The updater-bundled sunxi-fel v1.4.1-104-g11a9d20-dirty enumerated one Allwinner F1C100s device and identified a Winbond EFh:40h 16 MiB SPI flash.
- Read-only spiflash-read 0 0x1000000 produced a full local backup, SHA-256 ab1e0c4539a2e3e053af78b39c1be5d3b4d3c2934dc96b29d4fd5a9395008be3. The backup and its derived payload remain local/non-public.
- eGON extraction: main image at 0x50000, declared size 5,943,296. Full image SHA-256 b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1 is an exact match for beta-diode-profiles-e2/f1c100s-profiles-OFFLINE.bin; payload SHA-256 4708beb05841b42543714d460e0f7928e2fe72aab7479a40cfa757ce7ef511d2.
- No device write occurred: no spiflash-write, boot/SPL/U-Boot operation, RAM write/execution, or normal-firmware memory capture.

### Revised exact continuation point

1. Classify the rest of the backed-up 16 MiB flash image before using any region for future instrumentation or storage.
2. Restore and run bounded V3.6 PyGhidra inventory, then compare it against V3.8; retain the already established raw 20-byte delta.
3. If a physical experiment is needed, design it first against the confirmed E2 image and only use a recovery-tested, narrowly scoped image change after recording the exact restore path.

## 2026-11-06: PyGhidra restored and V3.6/V3.8 seeds compared

- Installed PyGhidra 3.1.0 from the local Ghidra 12.1.4 bundle into an isolated project directory; no external package download was used. Import test passed with JPype 1.5.2.
- Ran the bounded ARMv5T inventory exporter on verified original V3.6 and V3.8 inputs. It produced assembly, decompiler, direct-call, and fixed-window evidence for all 13 seeds.
- Comparator test passed: 13 of 13 exported bodies identical; no changed or missing seed. The first 64-byte and first 512-byte fingerprints are also identical for every pair.
- Corrected compare_inventories.py stale limitation text so future reports do not claim V3.6 is unavailable when it is an input.
- Added ACCELERATION_OPTIONS.md. It records the deferred passive UART-TTL capture method and the install criteria for Unicorn/Capstone, Rizin, Binwalk/ImHex, and Version Tracking.

### Revised exact continuation point

1. Trace SoundControlGate direct callee 0x800060d0 to its first hardware-facing register access, retaining explicit call arguments and gating conditions.
2. Trace the single known pointer into the V3.6/V3.8 nine-cell changed data region at 0x80042d98.
3. When available, use receive-only 3.3 V USB-TTL capture on confirmed UART2 TX during normal firmware boot; retain raw logs as protocol evidence.

## 2026-11-06: Capstone/Unicorn installed and original parser executed

- Completed the isolated environment installation check: Capstone distribution 5.0.9 (runtime reports 5.0.7), Unicorn 2.1.4. ARM926 smoke test passed.
- Added `tools/emulate_state5_parser.py`, pinned requirements, and `tools/ARM_EMULATION.md`. The harness verifies original hashes, maps a limited code/RAM contract, selects UC_CPU_ARM_926, and executes original ARM bytes without stubbing instructions.
- **V3.6: 2,976/2,976 passed; V3.8: 2,976/2,976 passed.** All outputs have identical fingerprints across versions. All 34 instruction addresses were visited; exact write sets were also checked.
- New result: control byte +1 decrements and discards each sample while nonzero on entry. Count 1 → 0 still discards that sample. Command 1b forces selector zero; 1d caps byte 4 at 6.
- Confirmed that the unsigned saturation gate converts negative values to sentinel too, only for control word 13/14 with zero discard counter.
- Replaced the per-case emulation wall timer with a 64-instruction bound; the complete rerun finished successfully in about one second.
- Evidence: `evidence/2026-11-06-state5-arm926-emulation.json`. No physical device I/O occurred.

### Exact next continuation point

1. Trace producers of `0x805aae8d` (control object +1) and the input modes/events that load the discard count.
2. Retain the parser harness as regression coverage; avoid repeating the completed V3.6/V3.8 parser analysis.
3. Then trace SoundControlGate at 0x80006e4c into 0x800060d0 to identify the first hardware-facing operation.
4. UART-TTL capture remains deferred until the user can connect the adapter.

## 2026-11-06: count=2 producers and persistent parser lifecycle

- Verified original input-dispatcher case 2 stores control +8 from record byte 4 and count=2 at 0x80004468; case 5 stores control 0x22 and count=2 at 0x800043ec.
- Case-2 commands are [record[4], normalize(record[5]), 0x1d]; case 5 uses [0x0c,0x22,0x13,0x1d]. Secondary-byte normalization retains 0x13..0x18 and otherwise selects 0x19. Cases 3/4 preserve the control fields.
- Added trace_state5_discard_lifecycle.py and a reproduction note. Extended the existing parser harness with explicit persistent-RAM mode while preserving default behavior.
- Tests passed across V3.6/V3.8: **1,184 producer cases; 96 lifecycle scenarios / 384 parser entries; 16 task-guard cases**. Results and relevant raw-window hashes match between originals.
- Persistent state proves the publication pattern: first response discarded (2→1), second discarded (1→0), third and fourth publish.
- Corrected task interpretation: the normal guard only directly admits cases 3/4. Cases 2/5 reach a deferred-copy branch, with a later static input-dispatcher call at 0x80005cf4. Duplicate task store blocks alone do not establish immediate execution.
- Rejected false literal-scan candidate 0x80005e60: r4 was reloaded with UART startup RAM pointer 0x805b4154.
- Original 5,952 parser regression cases passed with unchanged result fingerprints. No physical device operation occurred.

### Exact next continuation point

1. Trace helper 0x80006778, its r0/r1/r2 record construction, and direct call sites that submit software cases 2/5. Seek a proven UI/event association for input bytes +4/+5.
2. Trace terminal 0x1d polling/repetition and cadence before interpreting count=2 as a time delay.
3. Retain the validated parser/lifecycle harnesses; independent sound-control tracing still begins at 0x80006e4c → 0x800060d0.
4. Keep UART-TTL capture deferred until the user can connect the adapter.

Evidence: `evidence/2026-11-06-state5-discard-lifecycle.json`; method: `tools/STATE5_DISCARD_LIFECYCLE.md`.

## 2026-11-07: Diode/Buzzer GUI event sources verified and saved

- Continued the previous unfinished event-source experiment rather than restarting parser analysis. Re-read the development branch at 8ed1177 and re-ran all new experiments without filesystem writes.
- Identified event builder 0x80006778: opaque handle at control +4, record word +0 = r0, bytes +4/+5 = low8(r1/r2), queue call at 0x80061acc. Null handle returns early; queue r2 is 0 for event 3 and 10 otherwise, with no assigned unit.
- Found 31 aligned direct ARM BL candidates per original image. Full Thumb/indirect coverage is not claimed.
- Proved GUI association: literal Diode/Buzzer assignments to root +0x2c0/+0x2c4, callback 0x8000cfd0 registered on root +0x2b8, and handler code manipulating those labels.
- Diode event tail sends (2,0x0e,0x19). Buzzer sends the same unless settings word 0x805ac788 == 1, then (5,0x22,0x13). The selection API at 0x80044e54 has equivalent tails.
- Tests passed in V3.6/V3.8: **900 builder cases, 64 GUI branch cases, 96 linked parser entries, 12 GUI binding slices, 18 mode-switch cases**. Both result fingerprints equal 79d0dc306702ed86a72cd27754368db7c269f908daa24c06a88bfe32fc6f5bbc; the read-only rerun matched saved evidence.
- No physical device or paid external API was used. The complete GUI and queue implementation remain outside the harness.

### Exact next continuation point

1. Trace writers/default/storage of 0x805ac788 and identify the corresponding GUI setting.
2. Reuse the new event-source harness to verify both setting branches when its provenance is known.
3. Keep physical cadence, queue argument units, and audible latency open until independently proven.
4. SoundControlGate → 0x800060d0 and deferred UART-TTL capture remain pending.

Evidence created 2026-11-06 and re-verified 2026-11-07: `evidence/2026-11-06-measurement-event-sources.json`. Tool: `tools/trace_measurement_event_sources.py`.

## 2026-11-07: Fast CONT UI option, default and CRC persistence proven

- Identified 0x805ac788 as Fast CONT. English/Chinese label tails target GUI label +0x320; checkbox +0x31c registers 0x8005a3bc with event argument 0x1c.
- Executed the original checkbox handler and original getter 0x8003752c: widget halfword +0x20 bit 0 becomes normalized 0/1 at settings +0x18, then execution reaches SoundControlGate(5,1).
- Identified configuration loader 0x80008098 and save routine 0x800082c0. Record: flash offset 0xf00000, 72 bytes, zlib-compatible CRC32 over first 68 bytes, little-endian checksum at +0x44.
- Invalid-record default block sets Fast CONT=1. The seven-word default block and preserved tail are recorded without assigning unproven field names.
- Tests passed across V3.6/V3.8: **524 widget states; 48 save cases; 48 valid loads; 144 damaged records rejected; 12 default cases; eight restore cases; six GUI binding slices; 14 checkbox-to-event cases.** Version result fingerprints match.
- Historical private 2026-11-06 E2 flash backup: valid settings CRC and Fast CONT=1. Raw configuration bytes and the dump remain non-public.
- No physical device, flash-write, or sound operation occurred. Storage, GUI setters and SoundControlGate are API stop boundaries.

### Exact next continuation point

1. Trace Fast CONT read at 0x80003878 in ResultDispatch and prove its effect on the sound-control branch.
2. Continue into SoundControlGate 0x80006e4c → 0x800060d0 to identify the first peripheral-facing sound operation.
3. Retain queue timing units, response cadence and acoustic latency as open until directly established.
4. Investigate settings-save call sites later; loader metadata and remaining configuration fields are separate work.

Evidence: `evidence/2026-11-07-fast-cont-setting.json`. Tool/method: `tools/trace_fast_cont_setting.py` and `tools/FAST_CONT_SETTING.md`.
