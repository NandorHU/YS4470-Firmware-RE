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
