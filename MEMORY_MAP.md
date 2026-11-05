# Memory map

| Address/range | Classification | Evidence / meaning |
|---|---|---|
| `0x7fffffe0` | static link base | V3.8 raw ARM import base |
| `0x80000000` | static eGON image load start | Firmware header/payload analysis; not a guarantee of live DRAM in FEL |
| `0x805ac694` | firmware RAM object | Transaction-builder state root (static trace) |
| `0x805ac714` | firmware RAM object | Parsed measurement output object; values written at +0x1c/+0x20 (static trace) |
| `0x805aae8c` | firmware RAM object | Retry selector object (static trace) |
| `0x805b408c` | firmware RAM object | UART RX buffer root (static trace) |
| `0x00010000..0x00010fff` | SRAM-D / OTG SRAM mapping | F1C100S Linux device tree; not approved for automated FEL access |
| `0x01c00000` | system control | F1C100S Linux device tree |
| `0x01c20000` | CCU | F1C100S Linux device tree |
| `0x01c20400` | interrupt controller | F1C100S Linux device tree |
| `0x01c20800` | PIO | F1C100S Linux device tree |
| `0x01c20c00` | timers | F1C100S Linux device tree |
| `0x01c25000/5400/5800` | UART0/1/2 | F1C100S Linux device tree |

Hardware addresses are static mapping information, not authorization to touch a physical device. See `FEL_ANALYSIS_PLAN.md`.


## Beta3 instrumentation / control objects (2026-11-05)

| Address/range | Classification | Evidence |
|---|---|---|
| `0x800600ac + 0x08/+0x2c/+0x38/+0x3c` | Beta3 observer state | Written by helpers `0x800586ec` and `0x8005871c`; precise field semantics unknown |
| `0x805abbbc + 0x0c` | firmware context source | Read by both FSM observer helpers and copied to the Beta3 observer state |
| `0x805abefc + 0/+2/+7` | control-byte tuple | Tested by `0x80058750` to select 30 versus 40 for the FSM `+0x30` field |
| `0x805ac694 + 0x30` | FSM phase budget/interval candidate | Receives values 80, 30/40, 50, or 100 in the local FSM paths; unit unresolved |


## Direct object-access evidence (2026-11-05)

| Address/range | Classification | Verified direct accesses |
|---|---|---|
| `0x805ac694 + 0x30` | FSM phase field, unit unresolved | Writes at `0x80004608`, `0x80004620`, `0x8000466c`; clear at `0x800048d4`; no direct LDR in the bounded literal-load trace |
| `0x805ac694 + 0x34` | FSM/task flag | Read by the task at `0x80005be4` and `0x80005cc0`; initialized by TransactionBuilder |
| `0x805abefc + 0x02` | control byte | Read/written by `HighspeedEventHandler` at `0x8000d294` |
| `0x805abefc + 0x07` | control byte | Read by Beta3 selector; written by several original branches including `0x8000d340` and `0x8000d380` |

Evidence is from `evidence/2026-11-05-literal-object-trace.json`, not a runtime memory capture.


## Measurement-FSM PIO control (2026-11-05)

| Address/range | Classification | Verified access |
|---|---|---|
| `0x01c208b4` | PIO sub-block pointer used by FSM | Passed as `r0` to PIO bit helpers |
| `0x01c208c4` | `0x01c208b4 + 0x10` MMIO word | Bits 2 and 3 are set/cleared by transaction paths |
| `0x8006367c` | command descriptor table | Indexed by FSM command ID before `0x80005e84` send call |

The SoC PIO base is documented at `0x01c20800`; exact port/pin and register semantic for this sub-block remain open.
