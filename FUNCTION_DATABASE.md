# Function and code database

“Role” is a verified local behavior, not an original symbol name.

| Address | Verified role | Evidence |
|---|---|---|
| `0x80004738` | RX reply-field parser | Decodes frame bytes 1–3 as signed little-endian S24; derives/caps a code from byte 4 except in control path `0x1b`. |
| `0x80004518` | RX parser continuation/retry target | Taken after retry decrement and after committing parser output; exact scheduler role unknown. |
| `0x80003fbc` | Result-dispatch function entry | Initializes a 0x44-byte local region and branches on UI/state fields; it clears output flags and invokes sound gate on one documented invalid path. |
| `0x80003a0c` | Diode-result validity branch | Directly exercised by prior ARM tests. |
| `0x80003a74` | Diode sound-gate call site | Prior ARM evidence. |
| `0x80006e4c` | Sound-control gate | In Ghidra, clamps first argument to 1–10 after a state-enable check; detailed semantics remain open. |
| `0x8000553c` | KeyTask countdown handler | Decrements `[r4+0x50]`; when condition word is 1 and count reaches zero, calls sound gate with `r0=5,r1=0`. |
| `0x800045e0` | Request-transmit tail site | Calls `0x80005e84`, then `0x80061f84`; associated request/state fields vary for control values `0x1b` and `0x1d`. |
| `0x8005d048` | GUI-update function entry | Candidate GUI route; a large function beginning with sound-gate handling. |
| `0x80010648` | Report-path call site | Candidate diagnostic report route only. |
| `0x8000740c` | IRQ-side branch site | Candidate IRQ route only. |
| `0x8000f568`, `0x80058750`, `0x80060928`, `0x80060950` | Patch code | Not factory function names. |

The complete bounded parser result is recorded in `evidence/2026-11-04-rx-parser-analysis.json`.
