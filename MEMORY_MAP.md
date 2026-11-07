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


## Measurement result object (2026-11-06)

| Address/range | Classification | Verified use |
|---|---|---|
| '0x805ac714 + 0x1c' | signed result / saturation field | state 5 writes parsed value or sentinel '0x007fffff'; ResultDispatch and two formatting candidates read it |
| '0x805ac714 + 0x20' | bounded selector field | state 5 writes the byte-4-derived selector; ResultDispatch and formatting candidates read it |
| '0x80004820' | state-5 literal | points to result object '0x805ac714' |

Direct consumer tracing is bounded to PC-literal object paths; it is not an alias-complete inventory.


## State-5 saturation-control object (2026-11-06)

| Address/range | Classification | Verified use |
|---|---|---|
| '0x805aae8c + 0x01' | state-5 countdown byte | parser decrements it when nonzero before publishing a result |
| '0x805aae8c + 0x08' | saturation-control word | dispatchers write it; state 5 compares it against '0x0d' and '0x0e' |
| '0x805ac714 + 0x1c' | result/sentinel field | receives '0x007fffff' when the saturation control and threshold conditions hold |
| '0x805ac714 + 0x20' | result selector | receives zero on the saturation path |

No unit, calibration scale, or physical over-range meaning is assigned to threshold '0x1389' or sentinel '0x007fffff'.

## 2026-11-06 V3.6/V3.8 raw-diff anchors

The original V3.6/V3.8 images share link base `0x7fffffe0` and length 5,943,296 bytes. Their only non-header changes fall in a data-looking region after literal `EnumKey*` strings: nine 32-bit cells beginning at `0x80063aa8` (file offset `0x63ac8`). The linked range is deliberately recorded as **unclassified data**, not as code, calibration, a key map, or a measurement table. V3.8 code at `0x80042d98` loads literal pointer `0x80063acc`; the local consumer is still unresolved.

## 2026-11-06 observed flash anchors (live FEL backup)

A non-public, read-only 16 MiB SPI backup establishes these observed anchors: main eGON header at flash 0x50000; header magic eGON.EXE; declared main-image span 0x5ab000 bytes (5,943,296); main payload begins at 0x50020 and spans 5,943,264 bytes. The main span byte-matches the local E2 modified image. Other flash regions have not yet been classified as boot assets, settings, calibration, or unused space.

## 2026-11-06 V3.6/V3.8 code-address confirmation

The bounded PyGhidra inventories confirm identical code fingerprints at the existing link-base addresses for 13 named seeds, including 0x800037bc, 0x80003a0c, 0x80004490, 0x8000489c, 0x80005a78, 0x80006e4c, and 0x800073bc. This reinforces the use of the V3.8 address map for corresponding V3.6 seed analysis, while leaving unexported regions and the nine changed data cells separately classified.

## 2026-11-06: state-5 execution contract

- `0x805b408c+1..+3`: synthetic signed-24 input bytes; `+4`: selector for command 1d.
- `0x805aae8d` (control object +1): a byte sample-discard countdown. Nonzero values decrement before either result field can be updated.
- `0x805aae94` (control +8): control word tested against 13/14.
- `0x805ac730` / `0x805ac734`: result value/selector words; preserved on every tested nonzero-countdown input.

The emulator maps only the code/literal page and these three RAM pages; code is guest read/execute-only and RX guest read-only. It verifies that the only guest writes are countdown byte or the two result words. This memory contract was exercised on both original images, not on the physical device. The flash-span hexadecimal typo above was corrected to 0x5ab000.

## 2026-11-06: discard-counter writers and UART alias distinction

- Control `0x805aae8c+1` (`0x805aae8d`) receives 2 at input-dispatcher stores `0x800043ec` / `0x80004468`.
- Control `+8` (`0x805aae94`) receives input byte +4 in software case 2, or 0x22 in case 5. It is preserved, together with the discard byte, in tested cases 3/4.
- Task control `+0` is a deferred-record flag: visible stores set it at `0x80005bdc` and clear it at `0x80005cec`. Deferred invocation also checks FSM +0x34.
- `0x805b4154` is the separate UART startup buffer loaded into r4 at `0x80005e50`; the store at 0x80005e60 goes to its byte +1, not to the discard counter.

The write scan remains a bounded candidate search. Whole-object resets and indirect aliases have not been excluded.

## 2026-11-07: event records and GUI-linked setting

- 0x805aae8c+4 is read by event builder 0x80006778 as an opaque queue handle; null returns early.
- Event record word +0 receives r0; bytes +4/+5 receive low bytes of r1/r2. A 0x44-byte stack frame is allocated, while bytes +6..+0x43 are untouched by this helper in the experiment.
- 0x805ac788 = settings object 0x805ac770+0x18: exact value 1 switches the Buzzer-side event tuple. Its persistent source/default and user-visible name are open.
- GUI root 0x805ac098: object +0x2b8 registers callback 0x8000cfd0; +0x2c0 receives literal Diode (0x80051940), +0x2c4 receives literal Buzzer (0x80051948).
- GUI mode byte 0x805abefc+0 is updated by the tested 0..4 switch slice. Association with labels is static UI evidence.

These are synthetic RAM and original instruction observations; no running-device RAM was captured.

## 2026-11-07: identified settings record

- Settings object base 0x805ac770; word +0x18 / 0x805ac788 = **Fast CONT** (normalized 0/1 by checkbox handler).
- Settings checksum at object +0x44 / 0x805ac7b4; CRC-covered bytes span +0..+0x43.
- Flash configuration record starts at 0x00f00000 and is 0x48 bytes long; Fast CONT is at record +0x18, checksum at +0x44.
- GUI root fields +0x31c and +0x320 hold the associated checkbox and Fast CONT text label.
- Default block initializes seven words at +0..+0x18; later fields retain their initial RAM pattern in the tested block.

The first record at 0xf00000 is now classified as configuration. This does not classify the remainder of its flash erase sector or make it suitable as instrumentation storage. The full private device dump is preserved.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

| Address | Meaning |
|---|---|
| 0x805ac780 | settings +0x10; exact value1 enables sound gate |
| 0x805ac77c | settings +0x0c; halved value controls PWM duty (tested0..100) |
| 0x805ab924 | sound active flag |
| 0x805ac764 | result object +0x50; on=3, completed off=0 |
| 0x80063968 | ten u16 requested frequencies, 2000..4000 Hz |
| 0x80063acc | unchanged 16-entry PWM prescaler table |
| 0x01c20800 / 0x01c2081c | PIO PA mux/pull |
| 0x01c21000 / +4 | PWM control / period-duty word |

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

Reference inventory contains34 block bases,361 literal register-enum entries in15 groups and428 annotated offset claims. They retain source/line provenance and are distinct from verified YS addresses. The new executed watchdog accesses are TIMER base0x01c20c00 plus0xb0 (keyed control) and0xb8 (mode). Exception-vector, ROM, SRAM, DRAM/framebuffer candidates and reference header inconsistencies are documented in the subsystem map. The upstream BROM artifact is65,535 bytes; it is not asserted to be a complete chip dump.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

| Address | Newly confirmed use |
|---|---|
| 0x805ab940 | one-byte INTC base-initialization flag |
| 0x805ab944 | primary handler table programmed into INTC_BASE_ADDR |
| 0x805ab9e8 | alternate table selected by registration mode0; its wider role is open |
| 0x805ab924+0 | existing sound-active flag |
| 0x805ab924+4/+8/+0xc | Fast CONT ring index / fill count / retained median |
| 0x805ac7b8 | three signed32 history slots |
| 0x8006397c | eleven12-byte lower/upper/selector records |
| 0x01c20400/+4/+0x10/+0x20/+0x60 | INTC vector/base/pending/enable/priority anchors |
| 0x01c20c00/+4/+0x10/+0x14 | timer IRQ enable/status and timer0 control/interval |

Pure C uses a separate24-byte state structure; that is a reconstruction API layout, not the original split-RAM layout. Factory initial history/count/median are not established by seeding the emulator.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

| Address | Verified use in the bounded refresh model |
|---|---|
| 0x805abefc+9 (0x805abf05) | initial callback warmup byte:0→1→2;>=2 permits ResultDispatch |
| 0x805aae8c+1 (0x805aae8d) | independent parser discard byte; callback leaves it unchanged |
| 0x805ac714+0x1c/+0x20 | shared stored raw result/selector; unchanged during primary counterexample |
| 0x805abeb8 | root holding the callback handle returned by creation API |
| handle+0 | word updated with callback period argument25/100/200 |
| 0x80003af8 | float32 divisor bits0x452f499a =2804.60009765625 |
| 0x80003afc | unsigned negative-clamp comparison bits0x80800000 |
| 0x80003b00 | rejection threshold bits0x447a0000 =1000.0 |

The fixture's timer handle and initial raw/history state are synthetic. They are not live SRAM observations or recovered factory initialization values.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

| Storage | Observed layout/use |
|---|---|
| 0x805aae90 | measurement queue handle (CONTROL+4), written by initializer0x800029dc |
| queue+0/+4/+8/+0xc | data start/end/write/read-side pointers |
| queue+0x10/+0x24 | waiting-list fields, empty in tested paths |
| queue+0x38/+0x3c/+0x40 | occupied count/capacity/item size |
| queue+0x44/+0x45/+0x4c | signed lock bytes/type byte |
| queue+0x50 | constructor's contiguous payload start;10*68+80=760-byte request |
| 0x805abbf8 | critical nesting word |
| 0x80d46fb8 / 0x80d46ff8 | two64-byte renderer memo buffers |
| 0x80d47038 / 0x80d47048 | four/eight-word renderer auxiliary histories |

The renderer histories differ from Fast CONT history0x805ac7b8. Runtime queue pointer values in tests are synthetic allocator returns; this is not a live RAM capture. No FEL-safe-region conclusion follows from emulator mappings.
