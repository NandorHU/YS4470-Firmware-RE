# Function database

Only functions or code regions with a direct published evidence path are listed. “Role” is an observed/derived role, not an original symbol name.

| Address | Role | Evidence and limits |
|---|---|---|
| `0x80003a0c` | Diode-result validity branch | Project status and archived ARM sound test enter this address with valid/invalid floating results. |
| `0x80003a74` | Original diode sound-gate call site | Project status; later patch test dispatches PWM through the original path. |
| `0x80006e4c` | Sound gate | Project status and archived test use it as the sound-control route. |
| `0x8000553c` | KeyTask tone/watchdog countdown | Archived test executes 13 cycles and observes tone stop on the 13th. Scheduler period remains unmeasured. |
| `0x80010718` | Scoped OPEN/invalid-result stop hook location | Existing project status identifies this patched path; semantics only verified in function-level emulation. |
| `0x8000f568` | Same-label display wrapper | Existing status identifies it; no full GUI reconstruction has been performed. |
| `0x80058750` | Diode response deadline helper | Existing status identifies it; factory protocol and timeout units are still unknown. |
| `0x80060928` | 1.0 watchdog-refresh hook | Patch-specific code, not a factory symbol. |
| `0x80060950` | 1.0 post-start watchdog initialization | Patch-specific code, not a factory symbol. |

## Naming policy

Addresses remain primary identifiers until a supplied original image permits independent disassembly and cross-version comparison. Do not promote patch-hook labels to factory function names.
