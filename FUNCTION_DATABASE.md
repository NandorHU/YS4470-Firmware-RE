# Function and code database

“Role” is a verified local behavior, not an original symbol name.

| Address | Verified role | Evidence |
|---|---|---|
| `0x80004738` | RX reply-field parser | Decodes frame bytes 1–3 as signed little-endian S24; derives/caps a code from byte 4 except in control path `0x1b`. |
| `0x80004518` | RX parser continuation/retry target | Taken after retry decrement and after committing parser output; exact scheduler role unknown. |
| `0x80003fbc` | Result-dispatch function entry | Initializes a 0x44-byte local region and branches on UI/state fields. |
| `0x80003a0c` | Diode-result validity branch | Directly exercised by prior ARM tests. |
| `0x80003a74` | Diode sound-gate call site | Prior ARM evidence. |
| `0x80006e4c` | Sound-control gate | Clamps first argument to 1–10 after an enable check; full semantics open. |
| `0x8000553c` | KeyTask countdown handler | Decrements `[r4+0x50]`; on expiry reaches sound gate. |
| `0x80005d04` | E1 profile Gauge-task hook | Replaced in experimental E1 build; Base runs original FSM once, Ready may issue bounded extra state passes. |
| `0x8000d294` | Factory Highspeed event handler | Byte-identical between reply-audio parent and E1 profile build. |
| `0x8005d1a0` | Factory Highspeed diode period-selector region | Byte-identical between those images; documented 200/100 branch remains outside profile patch. |
| `0x8005d048` | GUI callback entry / E1 hook | E1 profile build replaces entry with a wrapper; Highspeed selector region above remains unchanged. |
| `0x80051c0c` | GUI-constructor entry / E1 hook | Adds profile-control construction only in E1 build. |
| `0x8000f568`, `0x80058750`, `0x80060928`, `0x80060950` | Patch code | Not factory function names. |

Evidence: `evidence/2026-11-04-rx-parser-analysis.json` and `evidence/2026-11-04-profile-highspeed-compare.json`.
