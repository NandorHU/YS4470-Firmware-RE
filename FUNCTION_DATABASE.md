# Function database

Only directly evidenced locations are listed. “Role” means an observed role in archived instrumentation or a published test; it is not an original symbol name.

| Address | Role / confidence | Evidence and limits |
|---|---|---|
| `0x80003a0c` | Diode-result validity branch — exercised | Published ARM test enters it with valid/invalid inputs. |
| `0x80003a74` | Diode sound-gate call site — exercised | Published sound test follows the original gate path. |
| `0x80006e4c` | Sound gate — exercised | Published sound test identifies this route. |
| `0x8000553c` | KeyTask countdown handling — exercised | Test observes stop on the 13th cycle; the real period is unknown. |
| `0x800045e0` | Measurement transport TX instrumentation site | Diagnostic patch replaces a call here; protocol semantics remain unverified. |
| `0x80004738` | Measurement transport RX instrumentation site | Diagnostic patch replaces code here; raw buffer format is unknown. |
| `0x800037fc` | Candidate result-consume site | Instrumented call site only. |
| `0x8005d048` | Candidate GUI-update site | Instrumented branch site only. |
| `0x80010648` | Candidate diagnostic-report site | Instrumented call site only. |
| `0x8000740c` | Candidate IRQ-side site | Instrumented branch site only. |
| `0x8000f568` | Same-label display wrapper — patch code | Not a factory symbol. |
| `0x80058750` | Response-deadline helper — patch code | Not a factory symbol. |
| `0x80060928`, `0x80060950` | 1.0 sound watchdog hooks — patch code | Not factory symbols. |

## Naming rule

Use addresses until an original hashed image supports disassembly and cross-version comparison. Do not turn patch labels or instrumentation sites into factory function names.
