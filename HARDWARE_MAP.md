# Hardware map

## SoC-level verified sources

The F1C100S documentation identifies an ARM926EJ-S core and USB download capability in boot ROM. The Linux device tree maps CCU, interrupt controller, PIO, timers, and UART0–2; exact mappings used in this project are in `MEMORY_MAP.md`.

## Current firmware correlations

- The firmware has a receive ISR at `0x800073bc`, but the active UART peripheral instance is not yet proven.
- The sound gate at `0x80006e4c` ultimately invokes a lower-level routine at `0x800060d0`; a timer/PWM/codec ownership link is not yet proven.
- Beta3 changes a sound-call parameter for the diode/continuity branch. It does not, by itself, prove which hardware peripheral produces the audible output.

## FEL status

A historical project test identifies an F1C100S in FEL mode and a 16 MiB Winbond SPI flash. The only committed FEL automation is restricted to enumeration and SPI-flash identification. No write, erase, RAM code, or peripheral-register operation is authorized.


## 2026-11-05 boundary

The new FSM trace is wholly static. It narrows a control-field change but does not connect `0x805ac694+0x30` to any timer, PWM, UART, or buzzer peripheral. No hardware-map entry is promoted from this result.


## 2026-11-05 static-state boundary

The recovered objects are firmware RAM structures. The access trace identifies no MMIO register, timer instance, PWM, or buzzer peripheral. Therefore the 30→40 selector remains a software-state change with no asserted hardware timing unit.


## PIO control evidence — 2026-11-05

The measurement FSM controls bits 2 and 3 of the MMIO word at `0x01c208c4` (derived from PIO argument `0x01c208b4` plus helper offset `0x10`). It clears both during transaction construction, then chooses either bit3=1/bit2=0 or bit3=0/bit2=1 for specific command-ID groups.

This is a static PIO-control result only. It does not identify a GPIO port/pin, analog switch, range relay, buzzer line, or the electrical polarity at the board.


## Protocol-output boundary — 2026-11-05

The descriptor send helper calls `0x80006dc8` once per framed byte, but its peripheral ownership has not been recovered. The output must remain described as a firmware byte-output path, not as UART, GPIO bit-bang, SPI, or a specific external IC interface until `0x80006dc8` is traced.


## Measurement UART — 2026-11-05

The firmware sends descriptor frames through **UART2** at `0x01c25800`; the corresponding RX ISR receives from the same base. This is now a confirmed firmware transport link, not merely a candidate UART.

Unresolved hardware facts: which F1C100S pins are muxed for UART2, electrical level/interface, baud/format, and the identity of the external measurement controller. The shared UART2 result does not imply direct access to ADC registers.


## UART2 pins and configuration — 2026-11-05

Firmware writes function value 3 into the PIO fields for **PE7** and **PE8**. The F1C100S pinctrl definition maps those functions to **UART2 TX** and **UART2 RX** respectively. [Linux F1C100S pinctrl source](https://github.com/torvalds/linux/blob/master/drivers/pinctrl/sunxi/pinctrl-suniv-f1c100s.c)

The initialization requests baud argument 19200 and programs divisor `0x0249`; it then transmits startup sequence `60 60`. Exact applied baud is not asserted without independently proving the live UART clock source.


## UART2 RX completion boundary — 2026-11-05

No UART2 hardware register in the ISR declares a complete application frame. The ISR appends individual bytes in RAM and increments `0x805ab938`; the MeasurementFSM later applies a software rule for command IDs `0x1b/0x1d`: at least five bytes plus header `0x5e` or `0x60` respectively.

Therefore no new peripheral, ADC, timer, buzzer, or physical measurement mapping is asserted. This result is a firmware RAM/protocol gate, not evidence of a hardware end-of-frame signal.


## Identical UART2 byte sequence caveat — 2026-11-05

Descriptor command '0x1d' sends '60 60', the same two bytes emitted immediately after UART2 initialization. This confirms a shared byte sequence at the UART2 boundary only. It does **not** prove that initialization and command '0x1d' have the same meaning, affect the same external state, or identify any analog hardware function.


## Result-to-sound software boundary — 2026-11-06

ResultDispatch checks the software sentinel '0x007fffff' from result object '+0x1c' and conditionally calls SoundControlGate. This establishes a firmware control-flow relationship between result handling and a sound-control routine. It does not identify a buzzer peripheral transition, sound duration, threshold semantics, or a physical measurement condition.


## Saturation is software state — 2026-11-06

The '0x0d/0x0e' selector and '0x1389' threshold are evaluated entirely in RAM/state-5 code before a sentinel is written to the result object. The bounded trace introduces no ADC register, comparator, GPIO, PWM, timer, or buzzer peripheral access. Accordingly, the branch must remain a software saturation/display/control rule until a separate hardware/protocol mapping is proven.

## 2026-11-06 updater-mediated firmware intake

The Mr.Yang updater's read-only firmware-list request exposed the V3.6 package and SHA-256 manifest. The image was retrieved directly from that manifest and verified before analysis. **Upgrade was not invoked**, the updater reported no USB/FEL-ready device, and no physical hardware operation, firmware write, RAM execution, flash access, or device-memory read was performed.

## 2026-11-06 live FEL/flash verification

- BootROM enumerated USB\VID_1F3A&PID_EFE8 as Allwinner F1C100S through the installed WinUSB/libwdi binding.
- The compatible updater-bundled sunxi-fel enumerated the device and reported a Winbond EFh:40h SPI flash of 16 MiB.
- A full spiflash-read backup completed and was SHA-256 verified locally; it is non-public. No spiflash-write, boot, SPL, U-Boot, arbitrary RAM write, or execution command was issued.
- This confirms a recoverable baseline for future explicitly scoped device experiments, but FEL remains unavailable for observing memory while the normal firmware executes.

## 2026-11-06 analysis-environment acceleration

The local Ghidra 12.1.4 bundled PyGhidra wheel is now installed and exercised with original V3.6/V3.8 inputs. This is offline software analysis only and creates no additional hardware or FEL capability. The optional passive UART-TTL capture plan is recorded in ACCELERATION_OPTIONS.md; no TTL connection has been made.

## 2026-11-06: ARM926 software execution environment

Unicorn 2.1.4 is installed with explicit ARM926 CPU selection; Capstone distribution 5.0.9 reports runtime version 5.0.7, and both identities are recorded in the evidence. The state-5 experiment maps no MMIO and no ADC/UART/device model. All 5,952 passed cases are software execution evidence only. No device operation was performed in this session.

## 2026-11-06: response-count semantics, software evidence

The control byte initialized to 2 is decremented on admitted state-5 responses rather than by a demonstrated hardware timer. The two suppressed samples cannot be converted into milliseconds until cadence is proven. The apparent extra +1 writer in UART bring-up is a separate RAM buffer at 0x805b4154; no new GPIO, MMIO ownership, physical measurement mode, or UART wire observation is inferred. This session used host-side ARM926 execution only.

## 2026-11-07: GUI naming versus hardware observation

The event sources are now associated with the firmware's literal Diode/Buzzer labels through label assignment, callback registration, and handler code. This does not identify new pins, ADC frontend behavior, or actual buzzer timing. Event-builder queue argument r2=10 remains an untyped software argument, not 10 milliseconds. The verification ran on host-side ARM926 emulation only.

## 2026-11-07: Fast CONT snapshot and storage boundary

The 2026-11-06 E2-modified 16 MiB backup contains a valid CRC-protected settings record at flash offset 0xf00000 with Fast CONT=1. This was read from the existing local dump, not from a new live FEL session. The original settings write routine was emulated only up to its storage call; no flash, GPIO, USB, or sound-control hardware operation was issued.

The UI label Fast CONT identifies the branch selector. Its electrical effect and audible response time remain separate hardware/algorithm questions.


## 2026-11-07: sound gate reaches PWM0 (bounded ARM926 execution)

Evidence: `evidence/2026-11-07-sound-pwm-path.json`; reproducible method: `tools/SOUND_PWM_PATH.md`; runner: `tools/trace_sound_pwm_path.py`.

Original V3.6/V3.8 pass 792 gate/PWM cases, 160 Fast CONT result-qualifier cases and two sentinel-off call setups, with identical fingerprints. Real original instructions execute through 0x80006e4c → 0x800060d0 → pinmux 0x8000302c / PWM configure 0x80042d40; arithmetic helpers are executed, not stubbed. PIO/PWM are RAM shadows, with no physical clock, acoustic result or measured delay.

First peripheral read: instruction 0x80003034 reads PIO 0x01c20800. PA2 mux bits8..11 become3 and PA2 pull bits4..5 at +0x1c become0. [F1C100S pinctrl](https://github.com/torvalds/linux/blob/master/drivers/pinctrl/sunxi/pinctrl-suniv-f1c100s.c) maps PA2/function3 to PWM0. PWM fields agree with [sun4i PWM layout](https://github.com/torvalds/linux/blob/master/drivers/pwm/pwm-sun4i.c): enable bit4, polarity bit5, clock gate bit6, prescaler low4. All tested sound frequencies use prescaler15 and a nominal 24 MHz code literal. Actual source clock, wiring and acoustic delay remain unmeasured.

Address correction (2026-11-07): file word offsets 0x63ac8..0x63ae8 map to linked 0x80063aa8..0x80063ac8 at base 0x7fffffe0. Earlier prose was displaced by 0x20; raw-diff JSON was correct. Pointer load 0x80042d98 reaches the unchanged PWM prescaler table at 0x80063acc, not the changed nine-cell block. The changed block remains unclassified.


## 2026-11-07: pinned F1C100S reference pipeline integrated

Reference acquisition/licensing: `references/f1c100s/README.md` and `sources.lock.json`. Subsystem register anchors and identification methods: `references/f1c100s/F1C100S_REFERENCE_MAP.md` / `register-map.json`. Runner/method: `tools/analyze_f1c100s_references.py` / `tools/F1C100S_REFERENCE_ANALYSIS.md`.

All fifteen requested subsystem areas now have reference register anchors and concrete identification methods in F1C100S_REFERENCE_MAP.md. The map includes CPU/vector/boot, INTC, timers/watchdog, GPIO, PWM, UART, SPI/TWI, DMA, LCD/framebuffer, CCU/reset and cache/MMU/DRAM. Internal KEYADC/RTP are kept distinct from the established external measurement UART2 protocol. FNIRSI FPGA/ADC wiring is not transferred to YS-4470.

Watchdog helpers are tested against inert RAM shadows only. No real watchdog, FEL, flash, bootloader or RAM-code operation occurred. Unlicensed/proprietary-SDK comparison artifacts are not copied into the reconstructed firmware.


## 2026-11-07: reference-guided INTC/timer proof and Fast CONT C reconstruction

Evidence: `evidence/2026-11-07-intc-timer-path.json`, `evidence/2026-11-07-intc-timer-ghidra.json`, `evidence/2026-11-07-fast-cont-filter.json`, and `evidence/2026-11-07-fast-cont-filter-ghidra.json`. Methods: `tools/INTC_TIMER_PATH.md`, `tools/FAST_CONT_FILTER.md`.

YS uses INTC_VECTOR as a pointer to a handler slot, unlike the reference pending-bit scan/IRQ-number examples. Register routine initializes base to0x805ab944 once; mode0 uses a separate table, modes1..7 the primary table. Priority is cleared/replaced but the caller value is not masked to two bits; invalid high priorities can spill into neighboring fields. No out-of-range IRQ/channel index was executed.

The linked original startup path configures timer0 with24000 cycles, IRQ13 priority3 and registered status handler0x8005bf54, then sets control7. IRQ bridge0x8000230c tests pending bit13 and directly calls tick0x80061fa4, optionally scheduler0x800612f8, bypassing ordinary dispatch on that branch. Tick/scheduler bodies are stubs in the bridge experiment. Inert register shadows do not model clock progress, interrupt clearing or actual exception restoration.


## 2026-11-07: stored-result freshness and corrected refresh entries

Evidence: `evidence/2026-11-07-result-freshness.json` / `evidence/2026-11-07-result-freshness-ghidra.json`. Reproduction/scope: `tools/RESULT_FRESHNESS.md`, `tools/trace_result_freshness.py`.

No new device access occurred. This run links a GUI callback to stored measurement data and the already verified sound/PWM path using inert shadows. Callback period arguments25/100/200 are not assigned milliseconds. The nominal1kHz RTOS timer setup alone does not prove callback scheduling, UART sample cadence or acoustic latency. A queued command is not a completed measurement reply in this model.


## 2026-11-07: original queue/renderer state execution

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and `evidence/2026-11-07-refresh-side-effects-ghidra.json`; runner/method: `tools/trace_refresh_side_effects.py` / `tools/REFRESH_SIDE_EFFECTS.md`.

Original critical helpers manipulate guest CPSR IRQ-mask bit7 and nesting word0x805abbf8. Valid nesting0/1/2 paths pass on explicit ARM926. This does not inject hardware IRQs or prove concurrent scheduling. Queue/renderer code writes normal RAM, not newly observed MMIO. No device, flash, live UART or acoustic operation occurred; callback periods and wait10 remain unassigned physical time units.

## 2026-11-08: cached FSM deadlines and real tick snapshot

Evidence: `contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` and `contributions/COORD-FSM-TIMEOUT/fsm-timeout-ghidra.json`. Method/runner: `contributions/COORD-FSM-TIMEOUT/README.md` / `trace_fsm_timeout.py`.

Actual original tick-snapshot0x80061f84 reads the RTOS counter at0x805abbc8 while
guest IRQ is masked and critical nesting is incremented. Valid nesting0/1/2/7
is restored. The tick prefix increments modulo32 when not suspended; the
suspended branch increments a deferred counter and leaves the getter's word
unchanged. Ready-list, wrap-list and full interrupt scheduling remain outside
this proof.

Original GPIO clear/set helpers execute on inert RAM at0x01c208c4. The timed
advance path clears bits3/2, but the experiment assigns no new analog-range or
physical-pin function. UART send0x80005e84 is the explicit state1 leaf model;
a successful modeled call does not establish wire transmission timing.

The prior nominal timer0 setup is not upgraded to a measured frequency.
Duration30, budget40 fixtures, settle50/100 and other duration80 remain raw
counter quantities. No FEL operation, flashing, live UART or acoustic test
occurred.


## 2026-11-08: packet workflow scope

No physical hardware, USB/FEL, flash or live register operation occurred. REA supplied a read-only original-file identity/entropy observation; Ghidra/Unicorn supplied original-code context and bounded execution. None establishes the external measuring IC, clock rate or sound delay. See contributions/COORD-FUNCTION-PACKETS/README.md and contributions/COORD-LOCAL-TOOLS/rea-model-smoke.json.


## 2026-11-08 public patcher

The new patcher operates on local files only. Fourteen offline regression tests and twelve bounded loader-window executions used no physical device. Bootloader/logo/device-specific data outside the listed application edits are preserved. The known-loader read contract does not establish an unknown bootloader's compatibility or any live-device state.


## 2026-11-08 host-tool package

The new beta installer pins public sunxi-fel v1.4.2-162-g530adfa (exeSHA256cc1e338a238ab99dc0ca12bdb3558d2781f9e81ed411a9b92d1c4021a67a2acf), separate from the earlier tested da14... host binary. It requires exactly one F1C100s/Winbond EF40/16 MiB device. Official Zadig2.9 is bundled for explicit WinUSB setup; administrator approval remains with the user. No native USB, driver replacement, RAM execution or flash write was performed during the new installer tests. New package physical compatibility remains unverified.


## 2026-11-08: equal-Highspeed profile evidence

The E2 profile experiment executes the original UART ISR with synthetic RX bytes and inert MMIO. UART TX, PWM/renderer endpoints and RTOS ordering remain models. It cannot establish the external ADC identity, whether repeated0x60 restarts conversion, actual conversion cadence, physical clock units or buzzer audibility.64 waveform cases produced no false sound on malformed/missing input. See contributions/COORD-ADC-CADENCE/profile-validation.json.


## 2026-11-09: original UART correlation proof

The original UART2 transmitter now executes through its real ready loop at0x80006e00..0x80006e08 and register write0x80006e10. Descriptor source60 emits60 60 including checksum. Real ISR0x800073bc executes with synthetic status/data; UART2 MMIO remains inert guest memory. A160-instruction not-ready probe remains in TX before the FSM post-send timestamp, establishing no physical stall duration. No external ADC identity, conversion restart/buffering, actual baud or acoustic timing follows from these software cases. Hardware/device operations:0.


## 2026-11-09: admitted-frame stability and caller ownership

The new admission experiment uses the original UART ISR with controlled context-save/restore interleaves; no real IRQ entry, task priorities, byte cadence, serial adapter or physical device is observed. UART appends preserve the admitted prefix under tested valid counts. Known synchronous helper call paths are serialized by tested GaugeCmdTask startup/service-idle structure, but indirect/other-task ownership remains unproven. No physical latency or external ADC semantics are assigned.


## 2026-11-09: local model restored and startup-helper execution

The original synchronous helper's sender, UART2 output/ISR, memory copy/clear and GPIO helpers execute for startup descriptor IDs9/19. Native output frames are58035b and590059; GPIO bits2/3 are cleared on all40 tested exits. UART status/byte delivery and sleep scheduling remain models; no device access or ADC identity/physical latency is established. The local AI runtime was restored independently on the host GPU; its API-reported residency is analysis tooling, not meter emulation.


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

For tested idle fallback calls on V3.6/V3.8, the original UART2 TX path through `0x80006e10` wrote frames `c000c0`, `c05515`, `c3c3` and `c4c4` for IDs `0x26`, `0x27`, `0x2a` and `0x2b`, respectively. The original RX ISR handled synthetic ACK delivery in eight of the 16 cases. The external peer response and physical timing remain open. See the [replay, firmware hashes and instruction bytes](contributions/COORD-ADC-CADENCE/synchronous/deferred-validation.json).

## 2026-11-09: extended deferred status

The original UART2 write path at `0x80006e10` emitted `c1c1` and `c2c2` for `0x28` and `0x29`, with surrounding helper frames `c05515` and, on recognized status, `c000c0`. At `0x8000400c` and the tail path at `0x80004030`, the GPIO shadow shows bit 2 set then cleared. The peer, line behavior and physical timing remain open. See the [64 original ARM926 cases with both firmware hashes](contributions/COORD-ADC-CADENCE/synchronous/extended-status-validation.json).

## 2026-11-09: calibration status UI

The original UI names the producers for `0x28` and `0x29` as Cal Circuit 1 mode and Cal Circuit 2 mode. The result strings include EEPROM failures. These are user-facing labels grounded by the original registered callbacks and label copy, with physical circuits and peer internals still open. See the [calibration UI replay](contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-validation.json).

## 2026-11-09: original control queue and type 6

In the [real-queue replay](contributions/COORD-ADC-CADENCE/synchronous/type6-queue-validation.json), the type-6 handler tail-calls `0x80006bb8` with UART index 2, clock argument 720000000, baud argument 19200 and IRQ enable 1. Original code writes UART2 divisor `0x0249`, final LCR 3 and the IRQ handler `0x800073bc`. The MMIO register shadows describe programmed values and routing. Physical clock rate and line behavior remain open.

## 2026-11-09: dynamic type-2 selection and compiled plan

The [dynamic replay](contributions/COORD-ADC-CADENCE/synchronous/dynamic-type2-validation.json) verifies actual UART2 second-send frames `590059` through `59055e` for descriptors `0x13..0x18`, and `5a5a` for fallback `0x19`. The controlled replies exercise firmware paths. The electrical meaning of the descriptor arguments remains open.

## 2026-11-09: refresh and first publication

In the [configuration-to-publication replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-publication-validation.json), the original UART2 path sends `6060` for refresh type 3 or `5e5e` for type 4 and handles controlled matching, missing and wrong-header replies. Timer values and reply delivery are model inputs. No physical timing was measured.

## 2026-11-09: refresh rendering and sound

The [rendering and sound replay](contributions/COORD-ADC-CADENCE/synchronous/refresh-rendering-validation.json) exercises original PWM setup at `0x80042d40`. The third reuse of one stored result sets PWM shadow control `0x7f` and period word `0x176f0a8c` in the tested mode-4 fixture. No physical probe or sound timing was measured.

## 2026-11-10 — Native mode entry and sound expiry

The sound countdown suffix calls the original gate with selector 5 and action 0 when active countdown 0 or 1 expires in the tested entry states. The original PWM path writes the duty-off value in the register shadow. The replay models the peripheral and establishes no acoustic or electrical timing. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-validation.json).

## 2026-11-10 — First refreshes after native Fast CONT entry

The original sound gate `0x80006e4c` and PWM path `0x80042d40` set shadow control `0x7f` and period word `0x176f0a8c` on the second refresh with populated retained history. With empty history, the same stored reading leaves shadow duty zero on that refresh. The peripheral uses a register shadow. [ARM926 replay and factory image hashes](contributions/COORD-ADC-CADENCE/synchronous/native-fast-cont-first-refresh-validation.json).

## 2026-11-10 — KeyTask and Fast CONT refresh ordering

With an active count of 1, a KeyTask iteration before refresh writes duty zero and the subsequent refresh re-enables the PWM shadow. Refresh first reloads the count so the same KeyTask iteration leaves duty on. The original watchdog helper `0x800085c4` ORs `0x14af` into its register shadow in every tested loop. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/key-task-fast-cont-order-validation.json).

## 2026-11-10 — Scheduler delays and task wakeup

The delay replay executes `svc #0` at `0x8000222c` and intercepts the exception before context switching. The separate original tick helper runs via direct injection or deferred drain. The hardware IRQ source, clock divisor and timing remain unmeasured. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-delay-wake-validation.json).

## 2026-11-10 — Installed vectors and scheduler context

With INTC pending bit 13 set in the register shadow, the original IRQ handler calls the tick helper and optionally the selector before writing 0 to `0x01c20410` and 1 to `0x01c20c04`. These are observed software writes. Peripheral acknowledgement semantics, tick frequency and hardware time remain open. [Original ARM926 replay and input hashes](contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-context-validation.json).

## 2026-11-10 — Timer0 and UART2 through the installed IRQ route

The original setup writes Timer0 control 7 and interval 24000. IRQ13 and IRQ3 register the Timer0 status helper and UART2 receive handler respectively. The mixed pending fixture takes the tick route before a separate host-injected UART event. Actual interrupt arbitration and timing are open. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-irq-validation.json).

## 2026-11-10 — Scheduled GaugeCmdTask service and fallback

The scheduled service replay supplies Timer0 IRQ13 and UART2 IRQ3 through the installed vector. UART2 IRQ fills the original buffer while GaugeCmdTask is asleep. Timer ticks wake the task and return to the polling code. Counter values are software observations. [Original ARM926 replay and factory hashes](contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-service-validation.json).
