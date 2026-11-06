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
