# Reverse-engineering progress

**Last verified update:** 2026-11-05  
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
