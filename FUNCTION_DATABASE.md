# Function database (human-readable)

The machine-readable source of record is `FUNCTION_DATABASE.json`. â€śConfirmedâ€ť means static code evidence supports the stated narrow role; it does not imply full behavioral reconstruction.

| ID | V3.8 / Beta3 address | Confidence | Narrow evidence-backed role |
|---|---:|---|---|
| ResultDispatch | `0x800037bc` | confirmed | Measurement-result dispatch region |
| DiodeValidityBranch | `0x80003a0c` | confirmed | Diode/continuity result branch region; sound-gate call is at `0x80003a74` |
| MeasurementFSM | `0x80004490` | confirmed | Request/reply state machine |
| TransactionBuilder | `0x8000489c` | confirmed | Transaction state construction/queueing |
| MainADCTask_candidate | `0x80005a78` | hypothesis | Candidate ADC task entry |
| SoundControlGate | `0x80006e4c` | confirmed | Selector gate (1â€“10) calling lower sound routine |
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

This replaces the former â€śbyte-output candidateâ€ť uncertainty for the measurement sender path. The line configuration and external device remain unknown.


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

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c â†’ 0x800060d0 â†’ pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

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


## 2026-11-08: GaugeCmdTask binding and hash-bound packets

The database now has60 records. New entry0x80003dbc is statically bound to the original GaugeCmdTask name through the executed registration-argument setup at0x80005948..0x80005954. Its seven original instructions call setup0x80005d24, command routine0x80005f14 with9 then19, and repeat service0x80005b6c. Three callees are modeled returns; no UART/RTOS timing is proven. The name of service0x80005b6c is still a hypothesis.

Six original-hash-bound complete-local-CFG packets cover this wrapper, SoundControlGate0x80006e4c and MeasurementRefreshCallback0x8005d048. See contributions/COORD-FUNCTION-PACKETS/packet-index.json and validation.json for360 instructions checked against original bytes,388 edges and explicit caller/global completeness limits. No automatic renames or whole-firmware equivalence claim was made.


## 2026-11-08 public patcher scope

Function records remain60; no new firmware function role was inferred by the distribution work. The application-only patch data reproduces public1.0 code changes from the pinned originals. The12 loader-window cases at0x490..0x508 validate the read argument contract only, not startup or complete boot. See contributions/COORD-PUBLIC-PATCHER/loader-validation.json.


## 2026-11-08 installer release

Function records remain60. Installer1.1.0-beta.2 bundles the known factory image and existing1.0 patch resource; no new firmware role/name is promoted.19 simulated installer/driver-launch tests and14 public patch tests are host-side validation, not new original-function coverage. See contributions/COORD-EASY-INSTALLER/published-release.json.


## 2026-11-08: equal-Highspeed profile evidence

The existing gauge_task_candidate record0x80005b6c is refined to a proven GaugeCmdTask service on the bounded original idle path: call FSM0x80004490, then request sleep(1). Its task-entry label is superseded; GaugeCmdTask entry remains0x80003dbc. E2 active paths execute the patched step/tail around the original body. The inferred service name is not a recovered factory symbol. The database remains60 records. See contributions/COORD-ADC-CADENCE/profile-validation.json and observed-call-edges.json for bounded edges and limits.


## 2026-11-09: original UART correlation proof

Existing measurement_transaction_send, measurement_byte_output_candidate and uart_rx_isr records are refined from static observations to bounded original ARM926 execution on both originals. The sender appends an8-bit additive checksum; selector2 polls UART2+0x7c bit1 and writes UART2+0; the ISR gates on UART2+8 bit2 and appends into a200-byte buffer. The database remains60 entries; inferred labels are not recovered vendor names. New independent pure-C components: reconstruction/uart_transport.c/.h. See contributions/COORD-ADC-CADENCE/uart/validation.json and ghidra-functions.json.


## 2026-11-09: admitted-frame stability and caller ownership

Two scoped analyst entries are added: fallback control handler0x80003dd8 (entry routing dynamically bounded, body statically indexed) and synchronous helper candidate0x80005f14 (identical95-instruction local CFG; no new body execution). The database now has62 records, not62 fully reconstructed functions. Nine direct BL call sites and an additional0x8000404c tail edge are validated in original code. The UART ISR/prefix and service-idle gate evidence is linked to existing records. See contributions/COORD-ADC-CADENCE/admission/.


## 2026-11-09: local model restored and startup-helper execution

The existing synchronous_command_helper_candidate0x80005f14 entry is promoted from static-only evidence to bounded original startup-command execution for IDs9/19, with40 matching cases across3.6/3.8. One matching header byte suffices for helper ACK success; each attempt checks before sleep with a500-iteration cap, and at most one retry is observed. The measurement FSM's separate five-byte contract remains unchanged. The database stays62 records; other command IDs/caller concurrency remain outside this new proof.


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

The existing fallback and synchronous-helper entries now include the four producer-bound paths. At `0x8000404c`, type 0 tail-calls the helper with `0x26`. Tested type-1 records call it at `0x80003eac` with `0x27`, `0x2a` or `0x2b`. The database remains at 62 entries. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json) for 16 original ARM926 cases across V3.6/V3.8.

## 2026-11-09: extended deferred status

The existing `0x80003dd8` and `0x80005f14` entries now include the `0x28`/`0x29` producer-bound branch and its `0x27 → command → 0x26` sequence when a status header is recognized. The two existing analyst entries remain scoped to tested paths. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

New analyst entry `calibration_status_ui_callback` binds `0x8005da88` to the original timer registration at `0x8004c4ec`, the status load at `0x8005dac4`, and the result-label setter at `0x80032038`. The database now has 63 entries. See the [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json).

## 2026-11-09: original control queue and type 6

The existing fallback entry at `0x80003dd8` now includes the synthetic type-6 record path through helper call `0x80003e2c` and the UART2 setup tail call at `0x80003e4c`. The original constructor, enqueue, dequeue and fallback execute in 38 cases. The database retains 63 entries. See the [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json).

## 2026-11-09: dynamic type-2 selection and compiled plan

The existing Highspeed handler at `0x8000d294` now has original producer-to-UART execution on both versions. The existing dispatcher entry is also compared with independently compiled C for types 2–5. See the [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json) and [compiled-plan differential](contributions/COORD-ADC-CADENCE/synchronous/measurement-plan-validation.json).

## 2026-11-09: refresh and first publication

The existing callback `0x8005d048` now runs from its original timer and enqueues type-3/4 into the original queue. The [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json) follows 18 original sequences to parser publication and observes which stored value is present at the ResultDispatch call.

## 2026-11-09: refresh rendering and sound

The [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json) executes original ResultDispatch `0x800037c0`, renderer `0x8000326c`, and a controlled Fast CONT path through `0x80007c88` and sound gate `0x80006e4c` on both originals.

## 2026-11-10 — Native mode entry and sound expiry

The original Diode/Buzzer callback `0x8000cfd0` ran through the queue and dispatcher in 16 cases across V3.6 and V3.8. The sound countdown suffix `0x8000553c` reached the original gate `0x80006e4c` from `0x80005568` in active, expiring cases. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).

## 2026-11-10 — First refreshes after native Fast CONT entry

The original timer calls refresh `0x8005d048` after native mode entry at `0x8000cfd0`. The first refresh moves warmup 1 to 2 and returns. The second reaches ResultDispatch `0x800037c0`, filter call `0x80003970` and renderer `0x8000326c` while the result still holds the prior measurement. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-first-refresh-validation.json).

## 2026-11-10 — KeyTask and Fast CONT refresh ordering

The original registration slice reaches `0x800059dc` with task entry `0x8000551c` and name pointer `0x80005a68` (`KeyTask`). One original loop body executes the watchdog update, sound countdown and sample-counter increment before the back edge to `0x80005528`. Task creation, key input and delay scheduling use fixtures. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/key-task-fast-cont-order-validation.json).

## 2026-11-10 — Scheduler delays and task wakeup

Delay helper `0x80060fbc` takes the original KeyTask argument 50 and GaugeCmdTask service tail argument 1. The ordered list helper stores deadlines and `0x80061fa4` applies ticks, drains due tasks and returns a yield flag in the tested fixtures. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-delay-wake-validation.json).

## 2026-11-10 — Installed vectors and scheduler context

The vector install slice at `0x80000030` clears CP15 control bit 13 and copies the template from `0x800023b0`. Installed IRQ and SVC slots lead to handlers `0x800022c0` and `0x80002234`. Both execute the original task-context path, with selection through `0x800612f8` when requested. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-context-validation.json).

## 2026-11-10 — Timer0 and UART2 through the installed IRQ route

The linked replay starts at original Timer0 setup `0x800617ec` and UART2 registration tail `0x80006d5c`. IRQ bit 13 selects tick processing in `0x800022c0`. With bit 13 clear, the ordinary vector dispatcher `0x80005260` selects the registered UART2 ISR `0x800073bc` and returns to the interrupted task. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-irq-validation.json).

## 2026-11-10 — Scheduled GaugeCmdTask service and fallback

The original GaugeCmdTask post-startup loop at `0x80003dd0` reaches service `0x80005b6c`, real queue receive, fallback `0x80003dd8` and helper `0x80005f14`. The original SVC/tick path schedules each bounded wait. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-service-validation.json).

## 2026-11-10 — Scheduled long fallback and status waits

The original producers at `0x8000e61c`, `0x8000e4f4`, and `0x8000e588` run through the real GaugeCmdTask queue to fallback `0x80003dd8`. The scheduled type-0 case waits 200 before helper `0x26`. Type-1 cases `0x28` and `0x29` execute the status path through the first post-clear poll and cleanup. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-long-fallback-validation.json).

## 2026-11-10 — Live calibration status and UI timer

The timer constructor at `0x8004c4ec` and runner `0x8004092c` execute in the same emulator as the scheduled status writer. The callback `0x8005da88` reads the live result at `0x8005dac4` and reads the flag at `0x8005dbfc` only for status zero. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration reset to fresh measurement

Original stores `0x80046cb0` and `0x80046cb8` clear the calibration flag and status. At the next timer deadline, callback `0x8005da88` takes the original type-3 enqueue at `0x8005dc38`. [Shared ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration buttons and pending queue

Both complete original calibration button callbacks run from `0x8000e4c8` and `0x8000e55c`. They reset the timer period, call the original queue drain at `0x80003d74`, enqueue a type-1 record, and format their mode labels. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-button-queue-validation.json).

## 2026-11-10 — Queue entry candidates and full-queue waits

The original sender at `0x80061acc` supports the tested zero-wait rejection, timed wait, and wake after a receive. Its `0x80061b18` interior edge executes after the sender resumes with the queue still full. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/queue-interior-full-validation.json).

## 2026-11-10 — Direct control producers and result-block writer

The original control-record builder `0x80006778` forwards the caller's type and low bytes of `r1` and `r2` to the original queue sender `0x80061acc`. The 31 indexed direct sites exercise record types 0–5. The `0x8005d34c` result writer clears six words for signed values below `0x40000000` in the tested suffix. [Factory hashes, original bytes and ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-producer-suffix-replay.json).

## 2026-11-10 — GUI field provenance at 0x80046548

The original caller at `0x80057948` enters the initializer `0x80045ea8`. At `0x80046548` the initializer stores a child label returned by `0x80030ad0` and passes it to the text setter at `0x80032038`. The original class descriptor at `0x80068ee0` points to the label constructor `0x800309f0`. The bitmap accessor `0x8002c844` resolves U+007D through the factory font descriptor and the original glyph lookup at `0x8001d5b0`. [Original replay, instruction bytes and firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/gui-field-provenance.json).

## 2026-11-10 — Registered GUI callbacks and indirect queue producers

The original GUI registration helper `0x800338dc` stores a 12-byte callback descriptor. The original event dispatcher at `0x8001ae74` calls the matched handler through `blx r1` at `0x8001b030`. Ten handlers from the original block at `0x8004c3b4` reach the original drain and control-record builder. The second block dispatches `0x8000d294`, which toggles its local flag and can produce type 2. [Original instruction bytes, factory hashes and replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-event-validation.json).

## Registered Diode/Buzzer callback dispatch (2026-11-11)

The original second registration block and dispatcher route event 1 from GUI object `+0x2b8` to `0x8000cfd0`. Both factory images agree in 24 ARM926 cases. Mode 3 with word `0x805ac788 == 1` sends type 5 (`05 00 00 00 22 13`). Mode 3 with word 0 or 2 and mode 4 with any tested word send type 2 (`02 00 00 00 0e 19`). Event 2 leaves the callback and queue untouched. The scheduler is idle and selected UI leaves are modeled. The original producer is `0x80006778`, reached at callsites `0x8000d0a0` and `0x8000d0c8`. [ARM926 replay, original hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

## Diode/Buzzer setting writer and secondary sender (2026-11-11)

Both factory images pass 48 ARM926 cases in total. The original writer `0x8005a3bc` stores bit 0 of the halfword at widget `+0x20` into `0x805ac788`. The registered callback uses that word to select the type-5 or type-2 record. The separate secondary command builds a 64-byte frame and reaches the original sender `0x80060ccc`. The hardware-facing `0x8005fc08` call is modeled. Writer store `0x8005a3dc`; command entry `0x8005f254`; sender call at `0x8005f2ec`. [Original-image replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).

## Secondary USB sender and TX interrupt (2026-11-11)

The original source-26 registration suffix `0x8005fa64` installs `0x800606ec`. In one ARM926 state, original submit `0x80060ccc` and sender `0x8005fc08` write the frame, a second submit is suppressed while busy, and a ready TX interrupt clears the flag at `0x800606d4`. A subsequent submit writes its frame. The IRQ vector and exception return execute original bytes. [Original-byte lifecycle replay](contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-lifecycle-validation.json).

## Mode-1 USB receive and remaining GUI handlers (2026-11-11)

The original USB mode-1 RX handler copies 64-byte type-3 reports from the modeled endpoint-2 FIFO, updates both guard words and stores the 61-byte record at `0x805ac640`. In the eight packet-ready cases across both images the original builder prepares the echo. Four idle cases write it to the channel-1 FIFO and four busy cases suppress that write. The second GUI registration block now has bounded original-dispatch replays for all ten callbacks. The eight newly exercised callbacks add 64 cases and 24 sends across V3.6 and V3.8. Every new send has record type 2. The 0x1c handler `0x8000f3b4` uses widget bit 0 to select argument 9 or 10 and writes timer-object value 2000. [USB replay](contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-rx-validation.json) · [GUI replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-second-group-validation.json) · [Final callbacks](contributions/COORD-ADC-CADENCE/synchronous/control-gui-second-final-validation.json).

## AC checkbox release-to-UART path (2026-11-11)

The AC checkbox class at `0x80068e70` and its base handler `0x80035428` execute the original release-to-value-change path. Checkable release event 8 toggles widget state bit 0 and emits nested event `0x1c`, which reaches the registered callback `0x8000f3b4`. The same original queue record goes through service, FSM and modeled Timer0/UART2 IRQs without host re-enqueue. [Native class event](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-release-validation.json) · [Same-state queue and UART replay](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-uart-validation.json).

## AC refresh and reconfiguration (2026-11-11)

The original timer enqueues a type-3 measurement after the AC checkbox configuration. The first valid reply consumes the remaining discard slot. The next valid reply publishes, and a missing reply delays publication by one request. The modeled view receives the latest stored result on a later native refresh. A second AC release during an active measurement produces a type-2 record. The original service defers that record until the old FSM is idle. An admitted old reply can still publish before the new configuration starts. With two additional releases, the earlier request is drained from the queue or replaced in the deferred slot, and only the last reaches the UART in the tested schedules. [Refresh](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-refresh-validation.json) · [In-flight](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-reconfigure-validation.json) · [Rapid toggles](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-rapid-toggle-validation.json).

## Factory settings event and global volume (2026-11-11)

Original registration `0x8001b2d0` binds the settings save callback `0x800453c8` to GUI context `+0x394`. In the three tested event codes, event 1 reaches the original CRC and storage routine. The other tested events leave the record unchanged. A Fast CONT checkbox update alone changes the RAM word. The factory volume handler `0x80057d34` reads slider `+0x3a0`, caps the input at 100 and stores half at settings `+0x0c`. The original preview passes half that stored value to the modeled PWM call. The global field survives the tested save/load round trip. [Save callback](contributions/COORD-DIODE-VOLUME/factory-settings-ui-validation.json) · [Slider and preview](contributions/COORD-DIODE-VOLUME/factory-volume-slider-validation.json).

## AC result text from the native renderer (2026-11-11)

The original result dispatcher at `0x800037c0` reaches renderer `0x8000326c` after the native checkbox, UART and refresh path. In 16 ARM926 cases, configuration 9 requests signed three-place formatting and configuration 10 requests three-place formatting without an explicit positive sign. Both use V in the tested selectors. A delayed UART reply can leave the previous stored result on screen until a later refresh. [Original replay evidence](contributions/COORD-ADC-CADENCE/synchronous/ac-checkbox-renderer-validation.json).

## Signed AC samples, selector clamp and display cutoffs (2026-11-11)

The original UART parser sign-extends the 24-bit sample at `0x8000474c` and clamps selector bytes above 6 to 6 at `0x80004764`. At `0x800037c0` the original display dispatcher consumes both words. Its configuration-9 branch begins at `0x80003b5c`, the configuration-10 branch at `0x80003b80`. [Original replay evidence](contributions/COORD-ADC-CADENCE/synchronous/ac-result-boundaries-validation.json).

## Factory Filter and the separate highspeed AC label (2026-11-11)

Factory checkbox `+0x328` registers `0x8005a534` for event `0x1c` at `0x8005490c`. A native release reaches the store at `0x8005a554` and toggles settings word `0x805ac784`. The nearby English label is Filter. The word survives valid CRC save/load, and the invalid-record path defaults it to 1 and prepares a CRC-correct rewrite. The original highspeed timer callback `0x8005da88` queues a type-3 request and formats the stored result. Its configuration-10 path at `0x8005dd34` uses 2.5 with both Filter values. The regular dispatcher uses 5.5 with Filter enabled. Five highspeed labels per image differ from the corresponding regular labels in the tested 2.5–5.5 interval. [factory-filter-setting-validation](contributions/COORD-DIODE-VOLUME/factory-filter-setting-validation.json) · [ac-highspeed-result-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-highspeed-result-validation.json).

## Original AC formatter and native highspeed fallback callers (2026-11-11)

The original C locale initializer `0x800001d0` writes `0x805aaaa4` to slot `0x80d5b894` at `0x800001e0`. The initialized decimal separator is a period. The original Thumb formatter `0x80000544` then agrees with both previous label datasets across 936 regular and 104 highspeed samples, including signed results and overload text. Four original type-1 button callbacks retain shadow selections 9, 12 and 15. Real queue and fallback `0x80003dd8` call `0x80005f14` for `0x26`, the selected configuration and `0x19`. In the 24 scheduled cases, the last helper runs after a successful configuration and after the configuration times out on both attempts. [ac-native-formatter-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-native-formatter-validation.json) · [native-highspeed-buttons-validation](contributions/COORD-ADC-CADENCE/synchronous/native-highspeed-buttons-validation.json).

## Native AC widget storage and USB export (2026-11-11)

The regular renderer calls `0x80045184` after its widget updates. This branch formats a USB payload using unit pointers at `0x805ab3d8`, then calls `0x8005f1a8`. The tested AC payload appends V to numeric text, preserves .OL without a unit, and uses category 1. The mirror at `0x805ac67d` updates before USB readiness is checked. With USB mode exactly 1, both readiness words nonzero and the channel idle, the original sender writes a 64-byte report starting `00 04 3f 01` to the channel-1 FIFO. Original text setter `0x80032038` copies the native numeric and unit strings, stores their pointers at widget `+0x24` and clears borrowed-text bit 3 at `+0x48`. It frees the prior buffer when owned and leaves the borrowed buffer untouched. The setter then reaches layout `0x800316fc`. [ac-usb-export-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-usb-export-validation.json) · [ac-widget-text-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-widget-text-validation.json).

## USB report reconstruction and original AC label geometry (2026-11-11)

The original export routine uses categories 1 for configurations 9–11, 2 for 12 and 34, 3 for 15, and 4 for configuration 14 or UI mode 4. The tested exporter appends V, R/K/M or nF/uF/mF tokens according to its unit table and flags. Status substrings .OL and OPEN bypass suffix and whitespace processing. The mirror retains at most 19 text bytes plus NUL. The original widget layout `0x800316fc` calculates a content rectangle through `0x80035b44`, then calls `0x80041078` for dimensions. The tested single-line path uses glyph advance records from the original font at `0x800a56d4`. The 16 schedules use a seeded style mapping. They verify dimensions and label state before redraw. [factory-usb-export-routing-validation](contributions/COORD-ADC-CADENCE/synchronous/factory-usb-export-routing-validation.json) · [ac-widget-layout-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-widget-layout-validation.json).

## Factory AC label bindings, wrapping and glyphs (2026-11-11)

The original initializer stores the numeric label at GUI `+0x2f4` at `0x80050c54` and the unit label at `+0x2f8` at `0x80050db0`. The two labels select fonts `0x804b000c` and `0x800d0bb4`, with size arguments 770×148 and 129×44 respectively. The original layout wraps tested wide numeric strings with those style arguments. For example, configuration 9 splits `+14023.000` into `+14023.` and `000` in the tested path. The 64 glyph cases verify the original advance, metrics and cold/warm 4-bit alpha bitmap lookup for both fonts. [ac-label-bindings-validation](contributions/COORD-ADC-CADENCE/synchronous/ac-label-bindings-validation.json) · [factory-bound-ac-layout-validation](contributions/COORD-ADC-CADENCE/synchronous/factory-bound-ac-layout-validation.json) · [factory-ac-font-glyphs-validation](contributions/COORD-ADC-CADENCE/synchronous/factory-ac-font-glyphs-validation.json).

## Native AC draw event and packed-alpha boundary (2026-11-11)

Label event `0x15` reaches original paint `0x800158c4` and text draw `0x800265bc`. The original context initializer `0x80029cc8` installs glyph callback `0x8002a0c4` at `+0x20`. The callback resolves font metrics and bitmap pointers, checks the ink rectangle against the draw clip, and reaches the packed-alpha compositor boundary `0x80014688`. The 48 cases confirm centered numeric glyph origins and right-aligned units, including a wrapped second numeric line. A full viewport reaches both lines for `+8388606.000`. A viewport ending at y=260 reaches only the first. A disjoint viewport reaches no glyph calls. [Original draw evidence](contributions/COORD-ADC-CADENCE/synchronous/factory-ac-draw-validation.json).
