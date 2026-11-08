# Function database (human-readable)

The machine-readable source of record is `FUNCTION_DATABASE.json`. “Confirmed” means static code evidence supports the stated narrow role; it does not imply full behavioral reconstruction.

| ID | V3.8 / Beta3 address | Confidence | Narrow evidence-backed role |
|---|---:|---|---|
| ResultDispatch | `0x800037bc` | confirmed | Measurement-result dispatch region |
| DiodeValidityBranch | `0x80003a0c` | confirmed | Diode/continuity result branch region; sound-gate call is at `0x80003a74` |
| MeasurementFSM | `0x80004490` | confirmed | Request/reply state machine |
| TransactionBuilder | `0x8000489c` | confirmed | Transaction state construction/queueing |
| MainADCTask_candidate | `0x80005a78` | hypothesis | Candidate ADC task entry |
| SoundControlGate | `0x80006e4c` | confirmed | Selector gate (1–10) calling lower sound routine |
| UART_RX_ISR | `0x800073bc` | confirmed | UART RX interrupt handler |
| Beta3SoundOverride | `0x80010754` | confirmed | Call-site-specific `r6=0x529` substitution when return address is `0x80003a78` |
| Beta3ResultObserver | `0x80060130` | confirmed static behavior | Preserves dispatch value while recording result/context changes |

## Function pairing rules

Function names are identities, not address identities. The inventory exporter compares the same proposed ID per version and records raw window hashes, assembly, decompiler output, and direct calls. A different exported-body hash can arise from changed code or a changed recovered boundary; raw range inspection is required before semantic conclusions.


## 2026-11-05 Beta3 helper classification

| ID | Beta3 address | Confidence | Evidence-backed behavior |
|---|---:|---|---|
| Beta3FSMCommandObserver | `0x800586ec` | confirmed static behavior | Records context/counter under `0x800600ac`, restores `r0/r1/r12/lr`, tail-branches to the original `0x80005e84` call |
| Beta3FSMParserObserver | `0x8005871c` | confirmed static behavior | Records context/counter, restores registers, then executes the replaced `ldrb r4,[r12,#1]` |
| Beta3Phase3BudgetSelector | `0x80058750` | confirmed static behavior | Returns 40 only for the documented three-byte condition; otherwise 30; caller writes the value to FSM object `+0x30` before state 3 |

The two observer helpers are not evidence of a protocol or parse-result change. The selector changes an FSM field, but no physical time unit or buzzer-latency conclusion is made.


## 2026-11-05 object-trace additions

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| MeasurementFSMDriverTask | `0x80005b70` | confirmed static behavior | Decodes an input/event, queues transactions through `0x8000489c`, and calls `MeasurementFSM` at `0x80005d04` |
| HighspeedEventHandler | `0x8000d294` | confirmed static behavior | Toggles `0x805abefc+2`; writes `+7` in its active branches |
| FSMPhaseField_0x30 | `0x805ac694+0x30` | hypothesis | Written/reset control field; direct consumer not yet recovered |

The literal-object tracer is bounded and direct-only. Its absence of a direct `LDR` is not a whole-program negative proof.


## 2026-11-05 PIO helper classification

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| PIOBitClear | `0x800031b8` | confirmed | Clears bit `r1` of MMIO word `[r0+0x10]` |
| PIOBitSet | `0x800031cc` | confirmed | Sets bit `r1` of MMIO word `[r0+0x10]` |
| MeasurementFSM state-1 GPIO selector | `0x80004504` | confirmed static behavior | Selects a bit2/bit3 PIO pattern for two command-ID groups before transaction send |

The former scheduler hypothesis for `0x800031b8` is rejected. These helpers do not directly consume FSM field `+0x30`.


## 2026-11-05 descriptor send path

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| MeasurementTransactionSend | `0x80005e84` | confirmed static behavior | Copies descriptor source bytes, computes an 8-bit sum, appends it, then invokes `0x80006dc8` once for each wire byte |
| MeasurementByteOutput_candidate | `0x80006dc8` | hypothesis | Called by the send helper with each prepared byte; transport/peripheral role remains open |

The descriptor count byte is the number of source bytes. It is not a count that includes the checksum.


## 2026-11-05 UART2 transport

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| MeasurementUARTSendByte | `0x80006dc8` | confirmed | Selector-based UART TX primitive; measurement sender selects UART2 and waits at `+0x7c` before writing `+0x00` |
| UART_RX_ISR | `0x800073bc` | confirmed | UART2 receive ISR; conditionally reads `+0x00`, stores byte in `0x805b408c`, caps count at 200 |

This replaces the former “byte-output candidate” uncertainty for the measurement sender path. The line configuration and external device remain unknown.


## 2026-11-05 UART2 initialization

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| UARTConfigure | `0x80006bb8` | confirmed static behavior | Configures selected UART base, PIO mux, FIFO/control fields, divisor latch, LCR, and optional interrupt path |
| UART2BringupCallsite | `0x80005e3c` | confirmed static behavior | Passes selector 2, requested 19200 baud, and interrupt flag 1; sends two `0x60` bytes after init |

The line code writes LCR low field `0x03`; standard 16550 semantics identify this as eight data bits with parity disabled/one stop bit, but the firmware result is documented first as the exact register write.


## 2026-11-05 UART2 RX lifecycle and parser gate

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| MeasurementFSMState3FrameGate | `0x800046dc` | confirmed static behavior | For command IDs `0x1b/0x1d`, waits for RX count >= 5, validates byte-0 header (`0x5e/0x60` respectively), then selects state 5 |
| MeasurementFSMState5Signed24Parse | `0x80004738` | confirmed static behavior | Combines RX bytes 1..3 little-endian, sign-extends bit 23, and handles byte 4 as a bounded selector input |
| SynchronousCommandResponseWait | `0x80005f20` | confirmed static behavior | Clears RX count, sends a descriptor, and polls for its first source byte; retransmits after its bounded wait expires |

The UART RX ISR is only an append producer. The state-3 rule is not promoted to a universal UART frame boundary, and the semantic purpose of command IDs `0x1b` and `0x1d` remains unresolved.


## 2026-11-05 command-1b/1d sequence construction

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| MeasurementCommandInputDispatcher | '0x80004390' | confirmed static behavior | Builds TransactionBuilder command lists from an input record; includes direct '[0x1b]' and lists ending in '0x1d' |
| MeasurementCommandTaskDispatcher | '0x80005b70' | confirmed static behavior | Repeats the sequence selection after task input decode; case 3 builds '[0x1d]', case 4 builds '[0x1b]', case 5 builds '[0x0c,0x22,0x13,0x1d]' |
| TransactionBuilder | '0x8000489c' | confirmed static behavior | Stores up to four command words for FSM state 1, which resolves descriptors and sends their UART2 frames |

Descriptor frames: '0x1b -> 5e5e'; '0x1d -> 6060'. These facts identify software command routing only. Neither dispatcher case nor byte value is assigned a physical measurement name.


## 2026-11-06 result-object consumers

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| ResultDispatch | '0x800037c0' | confirmed static behavior | Reads result value '+0x1c' and selector '+0x20'; its sentinel branch conditionally calls SoundControlGate |
| ResultTextPreparation_candidate | '0x80045264' | confirmed static data access | Reads selector and conditionally value while preparing a bounded text-formatting path |
| HighspeedResultFormatting_candidate | '0x8005dc3c' | confirmed static data access | Reads selector/value; nearby literal '%.3f' anchors numeric formatting context |

The field consumers are confirmed; names ending in '_candidate' do not assert a complete GUI function or a physical measurement assignment.


## 2026-11-06 state-5 saturation gate

| ID | Address | Confidence | Static role |
|---|---:|---|---|
| State5SaturationGate | '0x80004784' | confirmed static behavior | Reads control '+0x08'; for values '0x0d/0x0e' and unsigned value >= '0x1389', stores sentinel '0x007fffff' and selector 0 |
| MeasurementCommandInputDispatcher case-2 | '0x80004464' | confirmed static behavior | Writes input-derived r1 to saturation control '+0x08' |
| MeasurementCommandTaskDispatcher case-2 | '0x80005c58' | confirmed static behavior | Writes input-derived r1 to control '+0x08' while building a command list with terminal '0x1d' |

The recovered rule and bounded setup paths are raw-identical in V3.8 and Beta3. They remain software/protocol facts, not physical range or diode/continuity labels.

## 2026-11-06 V3.6 version baseline

Original V3.6 is now a verified local, non-public input: `Project_February_V3.6_V02.26.6/f1c100s.bin`, SHA-256 `7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9`, 5,943,296 bytes.

A whole-image raw comparison against V3.8 found only 20 changed bytes: an eGON-header word at offset `0x0c` and 16 bytes among the nine 32-bit cells beginning at `0x80063aa8`. Therefore the established V3.8 function addresses remain the initial V3.6 pairing coordinates, but each function is still marked V3.8/Beta3 until the reproducible V3.6 PyGhidra inventory is exported. No V3.6 function label or physical behavior is inferred solely from byte equality.

## 2026-11-06 active-device image identity

The live device complete eGON main image at flash offset 0x50000 is byte-identical to local modified build beta-diode-profiles-e2/f1c100s-profiles-OFFLINE.bin (full-image SHA-256 b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1). This establishes the address base for later, explicitly E2-scoped hardware experiments. It does **not** promote E2-only behavior into an original V3.6/V3.8 function claim.

## 2026-11-06 V3.6/V3.8 bounded function pairing

The PyGhidra exporter paired 13 evidence-labelled seeds between original V3.6 and V3.8. Every pair exported at the same address with identical assembly fingerprint and identical first 64/512 bytes. This includes all currently named core measurement, result, sound, and UART seeds. The result establishes a reusable V3.6 baseline for these functions; it does not assert that all unnamed firmware functions or all data tables are identical.

## 2026-11-06: bounded execution of state-5 parser

| Region | Original V3.6/V3.8 address | Verified behavior |
|---|---|---|
| Signed-24 parse and selector | `0x80004738..0x80004768` | RX bytes 1..3 are sign-extended; command 1b sets selector 0, command 1d caps byte 4 at 6 |
| Sample-discard gate | `0x80004770..0x80004780` | Nonzero control byte +1 decrements and skips both result stores |
| Unsigned saturation | `0x80004784..0x800047ac` | Control word 13/14 plus unsigned value >=5001 publishes sentinel and zero selector |

These are regions of MeasurementFSM, not newly discovered standalone functions. The complete 34-instruction slice passed 2,976 cases per original version on Unicorn ARM926; see [execution evidence](evidence/2026-11-06-state5-arm926-emulation.json). The counter initialization and physical measurement mapping remain unresolved.

## 2026-11-06: input dispatcher initializes the discard window

| Region within dispatcher | Original V3.6/V3.8 site | Proven effect |
|---|---|---|
| software case 2 | `0x80004464..0x80004468` | control +8 = input byte 4; discard byte +1 = 2 |
| software case 5 | `0x800043e4..0x800043ec` | control +8 = 0x22; discard byte +1 = 2 |
| task selection guard | `0x80005bb8..0x80005bd4` | cases 3/4 enter the immediate branch; other cases reach the deferred-copy call |

Case-2 secondary input is normalized to 0x19 unless it lies in 0x13..0x18. Both count-initializing command lists end in 0x1d. The persistent producer-to-parser experiment preserves the old result for two admitted responses and publishes on the third; it stops before TransactionBuilder and does not execute queue scheduling. See [evidence](evidence/2026-11-06-state5-discard-lifecycle.json) and `tools/STATE5_DISCARD_LIFECYCLE.md`.

The raw task stores at 0x80005c60/0x80005c80 remain static code observations; the verified task guard does not directly reach them for input cases 2/5. Physical mode names remain open.

## 2026-11-07: UI callback and event-record construction

| Function/region | V3.6/V3.8 address | Proven narrow role |
|---|---|---|
| MeasurementEventRecordBuilder | 0x80006778 | Returns early for null control +4 handle; otherwise stores r0 as record word +0 and low bytes of r1/r2 at +4/+5 before calling 0x80061acc |
| DiodeBuzzerUIEventHandler | 0x8000cfd0 | GUI callback bound to object +0x2b8; manipulates Diode/Buzzer label objects +0x2c0/+0x2c4 and constructs the related measurement events |
| MeasurementModeSelect_candidate | 0x80044e54 | Selection API with preconditions; tested switch slice writes indices 0..4 to mode byte, and its Diode/Buzzer event tails mirror the UI callback |
| Settings-dependent event branch | 0x8000d084 / 0x800450b4 | Word 0x805ac788 == 1 selects event (5,0x22,0x13) on the Buzzer side; otherwise event (2,0x0e,0x19) |

The event builder passes queue-boundary r2=0 for exact event word 3 and r2=10 for other tested words, with r3=0. No time unit is assigned to that argument. Its stack frame is 0x44 bytes; only the first six record bytes are initialized by the helper. GUI framework and queue implementations were not executed.

Evidence: [event-source experiment](evidence/2026-11-06-measurement-event-sources.json). The 31 aligned direct ARM BL sites are candidates, not an exhaustive Thumb/indirect call graph.

## 2026-11-07: Fast CONT and configuration record functions

| Proposed function | Original V3.6/V3.8 address | Evidence-backed role |
|---|---|---|
| FastCONTCheckboxHandler | 0x8005a3bc | Reads checkbox +0x31c state through 0x8003752c, writes 0/1 to settings +0x18, reaches SoundControlGate(5,1) |
| SettingsRecordLoad | 0x80008098 | Stages 72 bytes from offset 0xf00000; CRC validation leads to copy or default initialization |
| SettingsRecordSave | 0x800082c0 | Computes CRC32 over 68 settings bytes, stores checksum at +0x44, reaches write boundary with size 72 |

The checkbox-state getter at 0x8003752c reads widget halfword +0x20 and masks bit 0. It and the complete checkbox handler up to SoundControlGate were executed, alongside bounded CRC/default blocks. The storage read/write, copy/log and sound implementations were stop boundaries. Fast CONT defaults to 1 on the tested invalid-record path.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

| Entry | Proven bounded role |
|---|---|
| 0x80006e4c | sound gate, signed selector clamp, settings +0x10 enable check, state flag at 0x805ab924 |
| 0x800060d0 | period/duty conversion and PWM0 output setup |
| 0x8000302c | pinmux/pull helper, PA2 function3 for this caller |
| 0x80042d40 | PWM configuration; control 0x01c21000, period/duty +4 |
| 0x8000386c..0x80003888 | result qualifier slice; not a separate function boundary |

Helper 0x80007c88 is a pending history/range-selection candidate; its full algorithm has not been executed in this harness.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

| V3.6/V3.8 entry | Bounded proven behavior | Evidence |
|---|---|---|
| 0x800085c4 | WDG_CTRL at0x01c20cb0 read-modify-write: old OR0x14af; returns via LR | eight inert-shadow seeds per original; reference timer header/feed key agrees |
| 0x800085e0 | WDG_MODE at0x01c20cb8 read-modify-write: old OR1; returns via LR | eight inert-shadow seeds per original |

These analysis labels are RE_WatchdogKeyedControlUpdate and RE_WatchdogModeEnable. They do not claim hardware timeout/reset behavior or byte identity with the reference feed routine (which writes a constant). Other MMIO/CP15/BL leads remain candidates in the reference report. No reference function match has been promoted on a similarity score alone. PyGhidra preserves existing names/comments and exports all six proof-backed functions.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

| Entry in V3.6/V3.8 | Proven role | Bounded tests, both originals |
|---|---|---|
| 0x80005260 | INTC vector-pointer dereference and BX handler dispatch | 328 ARM/Thumb target cases |
| 0x80005274 | handler registration/exchange, priority and enable programming | 3304 cases |
| 0x800071a0 | timer configuration; low8 channel/IRQ flag, interval low32(24*argument) | 720 cases |
| 0x8000725c | set timer-control enable bit0 | 48 cases |
| 0x8005bf54 | timer IRQ-status read/OR1/write helper | eight cases |
| 0x80007c88 | three-slot history/stability/retained-median sound selector | 3958 original/Python/compiled-C steps |

Additional control-flow slices:36 IRQ-bridge cases and two linked startup cases. All fingerprints agree between originals. These are bounded behaviors, not blanket live-hardware/function-equivalence claims. Actual PyGhidra exports all five hardware entries and the filter/gate pair. Proof-only inventory mode avoids repeating the13-seed baseline.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

| Location | Corrected/proven role |
|---|---|
| 0x800037c0 | actual ResultDispatch entry; original memclr/numeric/filter/gate path executes |
| 0x8005d048 | measurement refresh callback entry; normal notification state0 tested |
| 0x8005d1a0 | callback's BL ResultDispatch, not a separate period-selector entry |
| 0x80040b84 | two-instruction word store to callback handle+0; period units unassigned |
| 0x800037bc | literal0x805abf10; PC-load uses0x80003688/3710/3774 |

New naming evidence exports the corrected dispatch, callback and period store with existing filter/gate entries. Legacy labels are not factory symbols or evidence of genuine function boundaries. The revised13-seed inventory is not compared with the old seed set as if a seed correction were a firmware change.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

| Original entry, V3.6/V3.8 | New bounded role/evidence |
|---|---|
| 0x800029dc | measurement queue init caller: arguments(10,68,0), stores handle at CONTROL+4 |
| 0x80061838 | queue constructor: allocation size0x50+capacity*itemsize, metadata and list init; allocator modeled |
| 0x8000326c | renderer/state core,1152 states per original; protected fields unchanged |
| 0x80006778 | existing event builder now executes into real send/copy; tested scopes expanded |
| 0x80061acc | available send-to-back and full wait0 reject; no waiting tasks |
| 0x80060efc | guest IRQ mask/nesting increment |
| 0x80060f20 | nesting decrement and guest IRQ enable at zero |

Helpers0x80060e48 (list init) and0x800009c4 (memcpy) execute as callees. The seven entry labels are analysis names with bounded proof, not recovered factory symbols. Complex renderer helper algorithms and blocked queue semantics are not promoted to full reconstructions.

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

| Original address, V3.6/V3.8 | Established scope |
|---|---|
| 0x80004490 | Existing measurement FSM; states2/3/4 now execute from the real entry and match independent Python/compiled C |
| 0x800044a4 / 0x800044a8 | Loads cached start/+0x30 duration; duration remains in R5 through the deadline branch |
| 0x800045e4..0x80004628 | Getter timestamp after modeled send returns; command0x1b/0x1d selects required5/duration30, other tested commands duration80 |
| 0x800046a8 / 0x800046c4 / 0x80004720 | Unsigned modulo elapsed comparisons; expiry routes differ by state |
| 0x80061f84..0x80061fa0 exclusive | New full tick-snapshot helper: critical enter, load ROOT+0xc, critical exit, return snapshot |
| 0x80061fa4..0x80061fe8 exclusive | Tick prefix only: unsuspended increment, or tested suspended/deferred early return; not a full routine proof |

New database ID rtos_tick_snapshot links the FSM to the existing critical
helpers. The FSM's existing Beta3 annotation remains historical: this new
execution proof covers only the SHA-256-pinned originals. Ghidra's inferred
whole-function body is not a claim that all FSM states were reconstructed.
