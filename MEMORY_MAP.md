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

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

| Storage | Tested role |
|---|---|
| FSM root0x805ac694 +0x2c =0x805ac6c0 | Start counter captured after send or qualifying ACK |
| FSM+0x30 =0x805ac6c4 | Raw counter duration, cached in R5 at0x800044a8 |
| FSM+0x24 / +0x28 | Expected header byte / required reply length; length comparison uses signed32 arithmetic |
| FSM+0x18 / +0x1c | Command index / retry field; successful timed completion increments index modulo32 and clears retry |
| RTOS root0x805abbbc +0xc =0x805abbc8 | Tick snapshot read under critical protection |
| RTOS root+0x30 / +0x18 | Suspend-related condition / deferred increment in the tested tick prefix |
| 0x805ab938 | RX count used by the FSM; distinct from parser discard0x805aae8d |
| 0x01c208c4 | PIO data shadow; successful advance clears bits3 then2 |

Deliberately injected host writes to start/duration at getter entry leave the
current comparison using the earlier R4/R5 snapshots. This verifies caching,
not the existence of an asynchronous writer. Tick wrap is tested at the32-bit
boundary; a complete counter cycle cannot be distinguished from elapsed0.
No location here was read from a live device in this run.


## 2026-11-08: original GaugeCmdTask name binding

Both pinned originals have the string GaugeCmdTask\0 at0x80005a10 and function-pointer literal0x80003dbc at0x80005a20. Executing0x80005948..0x80005954 reaches call0x80005958 with R0=0x80003dbc/R1=0x80005a10. These are application code/data addresses, not new MMIO identities. See contributions/COORD-FUNCTION-PACKETS/validation.json; the creation callee is not executed. Packet global-access candidates cover exported bodies only.


## 2026-11-08 application container preservation

The public patcher recognizes a5,943,296-byte application at full-flash offset0x50000 (exclusive end0x5fb000). It changes only the pinned69 continuous/65 timed sparse ranges inside that application. Known original bootloader0x490..0x508 requests payload flash0x50020→RAM0x80000000 for5,943,264 bytes in12 bounded cases. No other flash region, bootloader, logo or unmodified application bytes are changed. See contributions/COORD-PUBLIC-PATCHER/loader-validation.json; cold boot remains outside scope.


## 2026-11-08 automatic installation plan

The installer preserves the full16 MiB pre-write snapshot and requires a matching second read. It writes only differing64 KiB sectors wholly inside application0x50000..0x5fafff; all other bytes stay equal. Restoration accepts a confirmed backup/plan and refuses differences outside the earlier planned sectors. These contracts passed fake-transport tests; no physical flash state or new MMIO mapping is inferred.


## 2026-11-08: equal-Highspeed profile evidence

Original copy0x80000124 and decompressor0x800000c8 regenerate0x805aaab4..0x805ac098 (exclusive),5604 bytes, SHA256524ba48c4f8e6b7876fc1da735f82f197eb436947e65eac043f2d9f2b96f8be0, from pinned V3.8. E2 active/requested are bytes0/1 at0x80060a90;64 switch cases observed active stores only when FSM0x805ac694+0x34 was0. This is initialized data plus bounded emulated state, not a runtime capture. See contributions/COORD-ADC-CADENCE/README.md.


## 2026-11-09: original UART correlation proof

RX0x805b408c..0x805b4154 exclusive and TX0x805b4154..0x805b421c exclusive are separately guarded200-byte regions in the new original-code transport experiment. Count0x805ab938 remains10 after a two-frame finalization and the next builder, then the next state1 clears it with the RX buffer. Builder/finalizer writes to0x805ab91c/0x805ab920 are distinct bookkeeping cells; their wider roles are not assigned here. Original state1 clear executes IRQ-masked with positive nesting; tested old-frame injection after release can survive until parser publication. See contributions/COORD-ADC-CADENCE/uart/README.md.


## 2026-11-09: admitted-frame stability and caller ownership

The service's original literal0x80005d20 resolves to deferred-record storage0x805ac6d0. Its68-byte extent ends at0x805ac714, immediately before the result object and after the FSM's0x3c-byte region. In1,200 ISR/parser cases, first five RX bytes remain unchanged while up to196 further bytes arrive; valid count caps at200. This is conditional append stability, not immunity to another reset/writer. The synchronous helper's literal0x80006090 resolves to count0x805ab938 in both originals.


## 2026-11-09: local model restored and startup-helper execution

In the tested synchronous helper, matching one-/five-byte ACK input remains in shared RX/count when success returns. After the second attempt's final modeled sleep, a newly delivered matching header can remain at RX with count1 while the helper returns0, because no final recheck occurs. First-attempt delivery after its final sleep is cleared before retry. These are controlled memory/order observations at original0x80005f14 paths, not physical timing or a justified patch. See contributions/COORD-ADC-CADENCE/synchronous/synchronous-validation.json.


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

In 16 original V3.6/V3.8 ARM926 cases, `0x80006778` formed the tested records with a word at offset 0 and bytes at +4 and +5. With a modeled queue, the original service copied all 68 bytes to `0x805ac6d0` and back to its stack for dispatch. At caller `0x8000e7e0`, the record carries `0x27` at +4 while the selection byte at `0x805ac08c` holds `0x09`. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json).

## 2026-11-09: extended deferred status

At `0x80003e60` the extended fallback zeroes `0x805ab920`. At `0x80003f94`/`0x80003fa8` it stores a decoded status value 1–7 for the tested pairs. The control word `0x805ab91c` is set to 1 during the tested path and cleared on exit. The original IRQ-masked clears at `0x80003f24`/`0x80003f44` zero `0x805ab938` and accompany clears of the 200-byte buffer at `0x805b408c`. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

The calibration callback reads `0x805ab920` at `0x8005dac4` and reads `0x805ab91c` at `0x8005dbfc` when status is zero. Timer registration stores the handle at `0x805abeb8`, and the status callback gets its label object through `0x805ac540`. Original stores at `0x80046cb0`/`0x80046cb8` clear the two status words. See the [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json).

## 2026-11-09: original control queue and type 6

The [queue reference index](contributions/COORD-ADC-CADENCE/synchronous/control-queue-index.json) byte-checks the write at `0x800029f4` to the queue handle at `0x805aae90`, and its original reads by the producer, service and drain. The [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json) executes the original 10 × 68-byte ring, including wrap, and the 68-byte copy to the single deferred slot at `0x805ac6d0`.

## 2026-11-09: dynamic type-2 selection and compiled plan

The callback at `0x8000d648` sets `0x805abefc+1` at `0x8000d67c`. The `0x8000d294` callback reads that byte at `0x8000d388` and writes record-bound bytes through UI offsets +7/+8. The [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json) covers both single and paired callback schedules with the original queue drain.

## 2026-11-09: refresh and first publication

The [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json) follows the original discard byte at `0x805aae8d` from 2 at configuration through 1 and 0. The result words at `0x805ac730`/`0x805ac734` retain the prior value until an admitted frame reaches the parser with discard 0. At the ResultDispatch boundary those words still hold the prior value, before the request the refresh just queued can publish.

## 2026-11-09: refresh rendering and sound

The [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json) links result words at `0x805ac730`/`0x805ac734` to the original render record. It checks scaled float32 at record +0x3c, value and unit fields at +0/+0x32, and the filter count and median at `0x805ab92c`/`0x805ab930`.

## 2026-11-10 — Native mode entry and sound expiry

In the replay the raw result/selector, ring at `0x805ac7b8`, and index/count/median at `0x805ab924+4/+8/+0xc` survive both native mode change with terminal configuration frame and the tested countdown suffix. The countdown path writes the active word at `0x805ab924` in the tested expiry cases. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).

## 2026-11-10 — First refreshes after native Fast CONT entry

Native entry sets UI warmup at `0x805abefc+9` to 1. The first timer callback raises it to 2. On the next callback the retained ring at `0x805ac7b8` changes from [5, 6, 7] to [5, 6, 5], and the active flag at `0x805ab924` becomes 1. The empty-filter comparison leaves active 0. The published result and selector at `0x805ac730`/`0x805ac734` still hold the prior measurement at that point. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-first-refresh-validation.json).

## 2026-11-10 — KeyTask and Fast CONT refresh ordering

The KeyTask loop stores the modeled key sample at `0x805abb9c`, decrements the countdown at `0x805ac714+0x50` when positive, and increments the word at `0x805ac714+0x18`. The sound gate uses a shared countdown store at `0x80006eb8` with incoming values 0 for the tested off path and 3 for the tested on path. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/key-task-fast-cont-order-validation.json).

## 2026-11-10 — Scheduler delays and task wakeup

Scheduler base `0x805abbbc` contains the raw tick at +0x0c, deferred tick count at +0x18, wrap count at +0x20, next current deadline at +0x28, suspend count at +0x30, and current/overflow list pointers at +0x34/+0x38. The original wait helper stores the task deadline at task +4 via `0x8004288c`. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-delay-wake-validation.json).

## 2026-11-10 — Installed vectors and scheduler context

The low vector install copies 64 bytes to address 0. IRQ and SVC save an 18-word task frame and publish its address in the first word of the interrupted task object. The tested frame carries critical nesting, saved status, the task's r0–r14 and adjusted exception LR. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-context-validation.json).

## 2026-11-10 — Timer0 and UART2 through the installed IRQ route

The original UART2 ISR receives through registered IRQ3 slot `0x805ab950`, increments RX count `0x805ab938`, and stores the byte in the 200-byte buffer at `0x805b408c`. Tests cover the last slot, a full buffer and absent RX-ready status. Timer0 IRQ13 follows the dedicated tick branch without reading that UART slot. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-irq-validation.json).

## 2026-11-10 — Scheduled GaugeCmdTask service and fallback

The original queue is constructed with ten 68-byte entries. The service keeps a deferred 68-byte record at `0x805ac6d0`, controlled by byte `0x805aae8c`. A later deferred record updates that slot before idle dispatch. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-service-validation.json).

## 2026-11-10 — Scheduled long fallback and status waits

The IRQ-filled buffer at `0x805b408c` and count at `0x805ab938` are cleared under the original critical sections at `0x80003f24` and `0x80003f44`. The first clear saw three bytes and the second two. The status word at `0x805ab920` reflects the fresh prefix. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-long-fallback-validation.json).

## 2026-11-10 — Live calibration status and UI timer

The original callback reads the same `0x805ab920` and `0x805ab91c` words written by the scheduled GaugeCmdTask. The timer handle at `0x805abeb8` points to the fixture timer whose period and last-count words change through original code. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration reset to fresh measurement

The reset stores clear `0x805ab91c` and `0x805ab920`. A 68-byte record with prefix `030000000000` enters the original queue, and the accepted response updates `0x805ac730` and `0x805ac734`. [Shared ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-validation.json).

## 2026-11-10 — Calibration buttons and pending queue

Drain `0x80003d74` requests a 68-byte temporary buffer and repeats original zero-wait queue receive `0x800618dc`. The tested button records have prefixes `010000002800` and `010000002900`. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/calibration-button-queue-validation.json).

## 2026-11-10 — Queue entry candidates and full-queue waits

The replay checks the ten 68-byte records, message count at queue +0x38 and send-wait list at +0x10. Original task initialization at `0x80061e14..0x80061e20` establishes the inverted-priority value and owner of the event-list node. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/queue-interior-full-validation.json).

## 2026-11-10 — Direct control producers and result-block writer

The original constructor stores its returned queue handle at `0x805aae90` via `0x800029f4`. The control queue copies 68 bytes and updates its cursor and count. The `r5` literal at `0x8005d518` instead supplies `0x805ac714` to `0x8005d27c`. The tested `0x8005d35c` stores target this result block. [Factory hashes, original bytes and ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-producer-suffix-replay.json).

## 2026-11-10 — GUI field provenance at 0x80046548

The initializer at `0x80045ea8` preserves its caller's context in `r4`. Original stores place a label pointer at context `+0x38`, a parent pointer at `+0x3c` and a second label at `+0x40`. Both the actual control handle at `0x805aae90` and the allocated queue remain byte-identical. The font descriptor `0x800a56d4` reaches the packed U+007D glyph at `0x8009eec2..0x8009ef6c`, including the raw branch-like word at `0x8009ef10`. [Original replay, instruction bytes and firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/gui-field-provenance.json).

## 2026-11-10 — Registered GUI callbacks and indirect queue producers

The event descriptor stores the handler pointer at +0, the user value at +4, and the filter byte at +8. The original dispatcher temporarily links the event frame at `0x805abc18` and restores the prior value on return. The type-2 handler uses three state bytes at `0x805abefc` and writes the outgoing pair at offsets +7 and +8 on a send. The original control handle at `0x805aae90` remains unchanged. [Original instruction bytes, factory hashes and replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-event-validation.json).

## Diode/Buzzer event state (2026-11-11)

The callback `0x8000cfd0` tests the word at `0x805ac788` for equality to 1 on the tested 3-to-4 transition. It updates the mode byte at `0x805abefc` to 4, or changes it from 4 to 3 on the other branch. Bytes `+6..+10` of that state become `02 22 13 01 00` for type 5 and `02 0e 19 01 00` for type 2. The test seeds `0x805aac40` to 0 for the secondary command guard. [ARM926 replay and firmware identities](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

## Diode/Buzzer setting and sender state (2026-11-11)

The writer at `0x8005a3dc` stores the GUI widget flag into `0x805ac788`. The secondary sender checks `0x805aac40` and words at `0x805aac48` and `0x805aac4c`. Busy byte `0x805aac70` blocks the outgoing call, is set before a send, and is cleared by the observed nonzero return path. [ARM926 replay](contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).
