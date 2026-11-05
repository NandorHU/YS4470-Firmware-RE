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


## Command descriptor storage (2026-11-05)

| Address/range | Classification | Evidence |
|---|---|---|
| `0x8006367c` | 8-byte command descriptor table | Entry layout: source pointer (u32), source count (u8), three zero tail bytes |
| `0x80063654..0x80063661` | source-byte pool for IDs 09–0f | Seven adjacent two-byte sequences, each beginning with `0x58` |
| temporary buffer via literal at `0x80005f10` | send-buffer root | Send helper copies source bytes, writes checksum at source-count offset, then emits source-count+1 bytes |

The final checksum byte is constructed at runtime; it is not the following table-pool byte.


## UART2 transport path (2026-11-05)

| Address/range | Classification | Verified use |
|---|---|---|
| `0x01c25800` | F1C100S UART2 base | Measurement TX selects it; RX ISR reads it |
| `0x01c2587c` | UART2 status/readiness word | TX waits until bit 1 is set |
| `0x01c25800 + 0x00` | UART2 data register | TX writes each byte; RX reads low byte |
| `0x01c25808` | UART2 status/interrupt-related word | RX ISR tests bit 2 before reading data |
| `0x805b408c` | UART2 RX byte buffer | ISR appends bytes, bounded by count `0x805ab938 < 200` |

The UART2 base is consistent with the F1C100S Linux device tree; register behavior above is primarily firmware disassembly evidence.


## UART2 initialization state (2026-11-05)

| Address/range | Classification | Verified use |
|---|---|---|
| `0x01c20890` / `+0x04` | PIO configuration words | Firmware programs pin indices 7 and 8 to function 3 for UART2 bring-up |
| `0x01c25800 + 0x00/+0x04` | UART2 divisor/data register offsets | Under DLAB, init writes DLL `0x49` and DLM `0x02` |
| `0x01c25800 + 0x08` | UART2 control/FIFO offset | Init writes `0x37` |
| `0x01c25800 + 0x0c` | UART2 line-control offset | DLAB is toggled; final low field is `0x03` |
| `0x01c25800 + 0x10` | UART2 modem-control offset | Init writes zero |

The F1C100S pinctrl driver documents PE7/PE8 function 3 as UART2 TX/RX: [Linux source](https://github.com/torvalds/linux/blob/master/drivers/pinctrl/sunxi/pinctrl-suniv-f1c100s.c).


## UART2 RX parser storage (2026-11-05)

| Address/range | Classification | Verified use |
|---|---|---|
| `0x805ab938` | UART2 RX byte count | ISR uses it as the next buffer offset and increments it; direct reset anchors include `0x80003f24`, `0x80003f44`, `0x80004558`, and `0x80005f30` |
| `0x805b408c + 0` | parser header byte | FSM state 3 requires `0x5e` for command `0x1b` or `0x60` for `0x1d` |
| `0x805b408c + 1..3` | signed measurement-value field | FSM state 5 combines little-endian bytes and sign-extends bit 23 |
| `0x805b408c + 4` | parser selector input | State 5 bounds values >= 7 to 6; physical meaning remains unresolved |

For the two state-3 command paths, parser admission requires RX count >= 5. This storage layout must not be generalized to every UART2 exchange without tracing their separate FSM paths.


## State-5 command descriptors (2026-11-05)

| Address/range | Classification | Verified use |
|---|---|---|
| '0x80063754' | descriptor entry for command '0x1b' | points to '0x80063678', source length 1, source '5e', UART2 wire '5e5e' |
| '0x80063764' | descriptor entry for command '0x1d' | points to '0x80063679', source length 1, source '60', UART2 wire '6060' |
| '0x80063678..0x80063679' | one-byte source pool | source values for the two state-5 command descriptors |
| '0x805ac694 + 0x04..+0x10' | TransactionBuilder command-word slots | builder copies up to four command IDs here before FSM state 1 reads them |

V3.8 and Beta3 descriptor entries and wire frames for both IDs are identical.
