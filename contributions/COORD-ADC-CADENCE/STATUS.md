# COORD-ADC-CADENCE — continuation, 2026-11-09

## Original AC formatter and native highspeed fallback callers (2026-11-11)

The original C locale initializer `0x800001d0` writes `0x805aaaa4` to slot `0x80d5b894` at `0x800001e0`. The initialized decimal separator is a period. The original Thumb formatter `0x80000544` then agrees with both previous label datasets across 936 regular and 104 highspeed samples, including signed results and overload text. Four original type-1 button callbacks retain shadow selections 9, 12 and 15. Real queue and fallback `0x80003dd8` call `0x80005f14` for `0x26`, the selected configuration and `0x19`. In the 24 scheduled cases, the last helper runs after a successful configuration and after the configuration times out on both attempts. Widget and label sinks, timer-list traversal and UART/Timer0 inputs are modeled. The highspeed configuration-10 result remains a seeded-selector case. Follow the regular renderer call to 0x80045184 through 0x8005f1a8 and the original channel-1 sender, checking report text, units and USB gates. Keep native type-6 producer provenance and physical timing open. [ac-native-formatter-validation](synchronous/ac-native-formatter-validation.json) · [native-highspeed-buttons-validation](synchronous/native-highspeed-buttons-validation.json).

## Factory Filter and the separate highspeed AC label (2026-11-11)

The original highspeed timer callback `0x8005da88` queues a type-3 request and formats the stored result. Its configuration-10 path at `0x8005dd34` uses 2.5 with both Filter values. The regular dispatcher uses 5.5 with Filter enabled. Five highspeed labels per image differ from the corresponding regular labels in the tested 2.5–5.5 interval. The 10 settings cases model storage and GUI allocation. The 104 highspeed cases model numeric formatting and label sinks, with synthetic UART replies and seeded Filter and mode words. Execute original numeric formatting after the C runtime locale initializer at 0x800001d0, and compare normal and highspeed AC text with the modeled formatter. Keep native type-6 producer provenance and physical timing open. [factory-filter-setting-validation](../COORD-DIODE-VOLUME/factory-filter-setting-validation.json) · [ac-highspeed-result-validation](synchronous/ac-highspeed-result-validation.json).

## Signed AC samples, selector clamp and display cutoffs (2026-11-11)

The original UART parser sign-extends the 24-bit sample at `0x8000474c` and clamps selector bytes above 6 to 6 at `0x80004764`. Configuration 9 keeps negative values and explicit signs. Configuration 10 zeroes scaled results below 2.5, or below 5.5 when settings `+0x14` equals 1. Values equal to the active cutoff survive. Both use V for all seven effective selectors. Wire sample `0x7fffff` becomes `.OL` and clears the unit. The 936 synthetic UART cases execute the original checkbox, UART IRQ, parser, dispatcher and renderer in both factory images. The settings word is seeded, and the formatter and display sinks are modeled. Trace the factory settings +0x14 checkbox registration, label and save/load path into the configuration-10 display cutoff. Compare the separate highspeed formatter at 0x8005dc3c once the normal display setting is proven. Keep native type-6 producer provenance and physical timing open. [Original replay evidence](synchronous/ac-result-boundaries-validation.json).

## AC result text from the native renderer (2026-11-11)

The original result dispatcher at `0x800037c0` reaches renderer `0x8000326c` after the native checkbox, UART and refresh path. In 16 ARM926 cases, configuration 9 requests signed three-place formatting and configuration 10 requests three-place formatting without an explicit positive sign. Both use V in the tested selectors. A delayed UART reply can leave the previous stored result on screen until a later refresh. Each factory image now initializes its own unit table. The harness models formatter and GUI sinks. Pixel output and physical scaling remain open. Extend the original AC result presentation to signed samples and unit/scale boundaries. Keep native type-6 producer provenance and physical timing open. [Original replay evidence](synchronous/ac-checkbox-renderer-validation.json).

## AC refresh and concurrent toggles (2026-11-11)

The original timer enqueues a type-3 measurement after the AC checkbox configuration. The first valid reply consumes the remaining discard slot. The next valid reply publishes, and a missing reply delays publication by one request. The modeled view receives the latest stored result on a later native refresh. A second AC release during an active measurement produces a type-2 record. The original service defers that record until the old FSM is idle. An admitted old reply can still publish before the new configuration starts. With two additional releases, the earlier request is drained from the queue or replaced in the deferred slot, and only the last reaches the UART in the tested schedules. Execute the native result dispatcher and renderer on the already verified AC refresh schedules. Keep conversion units and physical timing open; retain native type-6 provenance as a separate question. [Original execution](synchronous/ac-checkbox-rapid-toggle-validation.json).

## AC checkbox and UART checkpoint (2026-11-11)

The AC checkbox class at `0x80068e70` and its base handler `0x80035428` execute the original release-to-value-change path. Checkable release event 8 toggles widget state bit 0 and emits nested event `0x1c`, which reaches the registered callback `0x8000f3b4`. The same original queue record goes through service, FSM and modeled Timer0/UART2 IRQs without host re-enqueue. Follow original 0x8005d048 refresh after the verified AC checkbox release and type-2 UART configuration. Determine which later measurement frames publish and preserve the type-6 provenance question. Review candidate alternate queue writers when a credible code path appears. [Original execution](synchronous/ac-checkbox-uart-validation.json).

## USB RX and remaining GUI callback checkpoint (2026-11-11)

The original USB mode-1 RX handler copies 64-byte type-3 reports from the modeled endpoint-2 FIFO, updates both guard words and stores the 61-byte record at `0x805ac640`. In the eight packet-ready cases across both images the original builder prepares the echo. Four idle cases write it to the channel-1 FIFO and four busy cases suppress that write. The second GUI registration block now has bounded original-dispatch replays for all ten callbacks. The eight newly exercised callbacks add 64 cases and 24 sends across V3.6 and V3.8. Every new send has record type 2. The 0x1c handler `0x8000f3b4` uses widget bit 0 to select argument 9 or 10 and writes timer-object value 2000. Bound additional Thumb-to-ARM and synthesized references to control producer 0x80006778, then classify credible indirect or alternate queue writers. Keep native type-6 provenance open unless demonstrated from an original caller. [USB](synchronous/secondary-usb-rx-validation.json) · [GUI](synchronous/control-gui-second-final-validation.json).

## USB TX lifecycle checkpoint (2026-11-11)

The original source-26 registration suffix `0x8005fa64` installs `0x800606ec`. In one ARM926 state, original submit `0x80060ccc` and sender `0x8005fc08` write the frame, a second submit is suppressed while busy, and a ready TX interrupt clears the flag at `0x800606d4`. A subsequent submit writes its frame. The IRQ vector and exception return execute original bytes. Replay the original mode-1 USB RX endpoint through 0x800603f4 and 0x800606e0 to verify FIFO copy, guard-word initialization and RX status handling. Then trace the mode-1 producer paths that originate native type-6 control-queue records; keep hardware timing open. [Reproducible lifecycle](synchronous/secondary-usb-lifecycle-validation.json).

## Secondary command checkpoint (2026-11-11)

Both factory images pass 48 ARM926 cases in total. The original writer `0x8005a3bc` stores bit 0 of the halfword at widget `+0x20` into `0x805ac788`. The registered callback uses that word to select the type-5 or type-2 record. The separate secondary command builds a 64-byte frame and reaches the original sender `0x80060ccc`. The hardware-facing `0x8005fc08` call is modeled. Trace the device-ready and busy-clear producers for 0x805aac40 and 0x805aac70. Replay the original 0x8005fc08 channel-1 sender with bounded modeled peripheral state. Keep native type-6 provenance open. [Original-code replay](synchronous/control-gui-cfd0-secondary-validation.json).

## Current checkpoint (2026-11-11)

The original second registration block and dispatcher route event 1 from GUI object `+0x2b8` to `0x8000cfd0`. Both factory images agree in 24 ARM926 cases. Mode 3 with word `0x805ac788 == 1` sends type 5 (`05 00 00 00 22 13`). Mode 3 with word 0 or 2 and mode 4 with any tested word send type 2 (`02 00 00 00 0e 19`). Event 2 leaves the callback and queue untouched. The scheduler is idle and selected UI leaves are modeled. Trace the writers of 0x805ac788 and verify the enabled 0x8005f254 route from the registered 0x8000cfd0 callback with realistic queue preconditions. Keep other indirect sends and native type-6 provenance open. [ARM926 replay and original hashes](synchronous/control-gui-cfd0-validation.json).

## Current checkpoint

The [GUI event replay](synchronous/control-gui-event-validation.json) follows original callback
registration and the indirect call at `0x8001b030`. The first ten
handlers drain two prior records and enqueue one type-0 or type-1
record on a matched event. The second block's `0x8000d294` emits type 2
under three tested local states per firmware. Next replay `0x8000cfd0`.

## Previous GUI field checkpoint

The [GUI field replay](synchronous/gui-field-provenance.json) follows the original
initializer from `0x80057948`. In four cases, the `0x80046548` store
holds a constructed label pointer. The control handle and the empty
or populated queue remain byte-identical. Eight original glyph lookups
also locate `0x8009ef10` within the U+007D bitmap. Next trace indirect
control-queue aliases and native type-6 provenance.

## Previous direct-producer checkpoint

The [direct caller replay](synchronous/control-producer-suffix-replay.json) checks 31 native sites
across both original images. All 66 empty-queue sends copy one 68-byte
record. Eight additional cases resolve the `0x8005d35c` signature to
the result block. Next trace `0x80046548` and the remaining indirect
queue-writer candidates.

## Previous full-queue checkpoint

The [full-queue replay](synchronous/queue-interior-full-validation.json) covers six original cases.
The sender times out at ten counts or succeeds after a receive at count
three. The interior branch match remains a raw encoding candidate.
Next resolve executable provenance of remaining indirect queue writers.

## Previous calibration button checkpoint

The [calibration button replay](synchronous/calibration-button-queue-validation.json) covers 12 cases
across both factory images. It distinguishes queued work, active
measurement and drain allocation failure. Next resolve remaining
indirect producers for the type-6 fallback.

## Previous calibration reset checkpoint

The [calibration reset replay](synchronous/calibration-ui-live-validation.json)
follows the original reset into a real type-3 request and new IRQ-fed
publication in four schedules. Next exercise full button callbacks and
their queue drain with pending work.

## Previous live calibration checkpoint

The [live calibration timer replay](synchronous/calibration-ui-live-validation.json) covers four
schedules and 60 original callbacks. The timer reads IRQ-written status
directly, including status 7 before the busy flag clears. Next follow
reset into the actual type-3 measurement queue.

## Previous long fallback checkpoint

The [scheduled long fallback replay](synchronous/gauge-long-fallback-validation.json) covers six
cases and 60,814 injected timer interrupts across both factory images.
The extended commands clear premature status twice and process the
post-clear reply at the first poll. Next link status to the live UI timer.

## Previous GaugeCmdTask checkpoint

The [scheduled GaugeCmdTask replay](synchronous/gauge-scheduled-service-validation.json) runs 26
cases with the original queue and loop, first and second ACK attempts,
measurement deferral, and deferred replacement. Next trace the
longer-delay type-0/1 fallback chains from original producers.

## Previous Timer0 and UART2 checkpoint

The [Timer0 and UART2 replay](synchronous/timer0-uart2-irq-validation.json) covers 40 schedules.
Original IRQ3 receive feeds the original measurement FSM while separately
injected IRQ13 ticks advance the scheduler. Next integrate the original
queue/service loop and trace remaining fallback paths.

## Previous vector and context checkpoint

The [vector and scheduler context replay](synchronous/scheduler-irq-context-validation.json) covers 44
cases across both factory images. The original SVC and IRQ routes switch
tasks and restore ARM/Thumb contexts. The blocked task resumes after 1 or
50 injected IRQ ticks. Next connect Timer0 setup to the tick and ordinary
IRQ routes under controlled pending states.

## Previous scheduler delay checkpoint

The [scheduler delay and wake replay](synchronous/scheduler-delay-wake-validation.json) agrees in 50
schedules across the two factory images. The tested waiting task becomes
ready on the requested applied tick, including overflow-list rotation and
deferred tick drain. Next run the original IRQ tick branch and context
selection with controlled pending interrupt and task contexts.

## Previous KeyTask checkpoint

The [KeyTask ordering replay](synchronous/key-task-fast-cont-order-validation.json) executes eight
schedules. KeyTask-first with active count 1 drives duty off before native
refresh re-arms it. Refresh-first reloads the count before the KeyTask
decrement. Next execute the scheduler delay helper with known task state.

## Previous first-refresh checkpoint

The [first-refresh replay](synchronous/native-fast-cont-first-refresh-validation.json) covers 16 schedules
across both factory images. The second callback uses the retained measurement
before the first fresh publication. A populated filter reactivates the PWM
shadow even after prior sound expiry. The empty-filter control stays off on
the same callback. Next exercise expiry and refresh in both orders.

## Previous native entry checkpoint

The [native entry and countdown replay](synchronous/native-fast-cont-validation.json)
covers 16 mode changes and 12 sound countdown suffixes on the two originals.
Native mode entry and terminal configuration preserve the seeded raw result and
filter history. Active countdown expiry switches off PWM duty in the shadow
while preserving both. Next execute the first two refresh callbacks after
native Fast CONT entry before fresh publication.

## Previous rendering checkpoint

The [rendering and sound replay](synchronous/refresh-rendering-validation.json)
adds original scaling and renderer execution to 18 lifecycle schedules.
Two further Fast CONT fixtures use the original sound path and show one
stored result reused for all three inputs of the filter. Next trace
native mode entry and filter resets.

## Previous publication checkpoint

The [configuration-to-publication replay](synchronous/refresh-publication-validation.json)
agrees in 18 original sequences across both versions. The original timer,
refresh, queue, UART and FSM execute. Missing/wrong frames do not consume
discard. Reconfiguration retains the stored result and re-arms discard.
Next execute ResultDispatch and the renderer on the same schedules.

## Previous dynamic type-2 checkpoint

The [dynamic replay](synchronous/dynamic-type2-validation.json) covers
568 cases on both originals, including the complete byte clamp and
paired callbacks with the original queue drain. The [compiled plan
comparison](synchronous/measurement-plan-validation.json) agrees in
4,108 cases. Next follow native refresh-produced type-3 requests
after type-2 configuration through discard and first publication.

## Previous type-2/5 checkpoint

The [type-2/5 replay](synchronous/deferred-measurement-validation.json)
follows the original Fast CONT choice through the real queue, deferred
dispatcher and the complete tested command lists. Both originals agree
in 20 cases. Next trace the producer at `0x8000d39c` and the dynamic
record byte +5 through the type-2 clamp and descriptor selection.

## Previous original queue checkpoint

The [real-queue replay](synchronous/type6-queue-validation.json) covers
38 cases across both originals. Type 6 uses a host-supplied record.
The original service, constructor/send/receive, helper, UART2 setup and
IRQ registration execute. The [reference index](synchronous/control-queue-index.json)
identifies one direct call to the task-context send routine. Next route
the type-2/5 producer sites `0x8000d0c8`/`0x8000d0a0` through the real queue.

## Previous general type-1 checkpoint

The [general type-1 replay](synchronous/general-type1-validation.json)
covers four original producers and all eight ACK combinations on both
images (64 cases). The handler always invokes `0x26 → record[4] → 0x19`.
Next trace references to the queue handle at control object +4
(`0x805aae90`) and alternate writers that could supply type 6.

## Previous calibration UI checkpoint

The [calibration UI replay](synchronous/calibration-ui-validation.json)
binds the two buttons, confirms all seven status messages and follows four
successive timer deadlines. Both originals agree in 40 status cases and
eight linked sequences. The [producer index](synchronous/control-producer-index.json)
finds 31 aligned ARM immediate call candidates with local types 0–5.
Continue from `0x8000e36c` into the general type-1 fallback, then look for
alternate queue writers that could supply type 6.

## Previous extended-status checkpoint

The extended `0x28`/`0x29` producer paths agree in all 64 original ARM926
cases. The command ACK gates the later status loop, which uses two critical
RX clears before polling. The original handler writes status codes 1–7 to
`0x805ab920` for the verified header/value pairs. See
[method](synchronous/README.md#extended-status-after-0x280x29) and
[validation](synchronous/extended-status-validation.json). Next validate
the reader candidate at `0x8005dac4`. Earlier checkpoints below are historical.

## Previous checkpoint

Four producer suffixes now run through the original idle service and fallback
to helper commands `0x26`, `0x27`, `0x2a` and `0x2b`. All 16 ARM926 cases
agree across both original hashes. See [method](synchronous/README.md#deferred-producer-paths)
and [validation](synchronous/deferred-validation.json). Continue from producer
sites `0x8000e50c`/`0x8000e5a0` into the extended `0x28`/`0x29` handler path
at `0x80003eb8`. Queue/ISR delivery/sleep fixtures bound the current evidence.

One new local indexing request over five original instructions used the frozen
checked UART lessons. The reply stopped normally with the expected schema and
selected `0x8000e7d8` for the final R1 write before the producer call. Capstone
and original bytes `2710a0e3` independently confirmed the selection.

Coordinator-owned/in_progress. Integration baseline for this UART run:
ed71bdb5d2dc3745ab700c1a80fe544788044077. The full project is not complete.

Latest proof: uart/README.md, uart/validation.json, uart/ghidra-functions.json.
On each original V3.6/V3.8 the real UART sender/byte-ready polling, ISR,
builder, FSM, copy/clear/critical/getter code now execute.12,704 transport
cases agree with independent Python and separately compiled ARM C. There
are184 delayed-arrival schedules,12 controlled ISR interleaves,4 concatenation
cases,2 cross-command rejects and2 bounded blocked-TX prefixes. Six Ghidra
exports contain158 byte-checked instructions;816 observed original addresses
are guarded separately. Counts overlap in code and are not firmware coverage.

A delayed first reply can be accepted after the retry: request0, timeout30,
retry selection31, resend32, old five-byte frame33..37, raw50 publication38.
These are injected counters, not milliseconds or actual ADC timing. Matching
headers identify command class, not request instance in the tested path.
Explicit ISR interleaves after RX clear/before send and during send also admit
the old frame. Actual CPU exception entry and scheduling remain unmodeled.

Two concatenated valid frames publish only the first. Count10 remains through
finalization and the next builder, then the next state1 clears the trailing
frame. This corrected the initial test's mistaken finalization-clear assumption.
Permanent not-ready UART status leaves original TX in its polling loop before
the FSM's post-send timestamp; the bounded probe gives no physical duration.

reconstruction/uart_transport.c/.h are new pure data components for framing and
RX append, not a UART driver or a complete firmware. Equivalence excludes
corrupt signed counts, source count+1 wrap and overlapping buffers. No offline
timing/correlation fix or new firmware Release was produced from a hypothesis.

Prior equal-Highspeed E2 matrix remains verified and is not rerun:64 waveform,
64 active/requested switches,16 existing candidate comparisons. It proves the
modeled GUI sound wait removal, not Base physical superiority. Public-input
replay remains available in reproduce_profiles.py without private dumps.

Local assistance: the new checksum extraction completed and its exact quote
was binary-checked; it added no independent finding. On the next day two new
RX/synchronous-helper index requests encountered a refused localhost API.
Their frozen contexts and failures are under uart/local-collab-2026-11-09/;
check current service address before retrying a transport failure. Never rerun
a completed model task or treat an unavailable/incomplete response as proof.

Next bounded work: count/read/parse stability between state3 admission and
state5. An append-only ISR does not itself replace existing first bytes, but
trace other shared-buffer writers and the synchronous helper0x80005f14,
including its actual callers before claiming a feasible concurrent clear.
Reuse the prepared static index and local contexts; the old clear anchors
0x80005f30/0x80005ffc are static until that combined execution is tested.
External conversion restart/buffering, installed image identity and physical
Base latency remain open. No device, flash, main or Release was modified.


## 2026-11-09: admitted-frame stability and caller ownership

New checkpoint: admission/README.md and admission/validation.json. On both originals,1,200 admitted-frame/ISR cases preserve the prefix and match the previous Python parser contract;24 original service cases confirm tested deferred-handler entry is idle-gated. Nine raw BL sites are classified, plus a newly identified0x8000404c tail branch to0x80005f14. admission/synchronous-static.json adds identical95-instruction callee context, not body execution. The earlier UART/profile proofs are reused without reruns. Next: execute synchronous helper success/failure under reachable caller/idle preconditions, and trace fallback record producers/other aliases before claiming global buffer ownership. The local API question remains unresolved; frozen model requests were not repeated. Current run baseline is d4140e2fd396c4f0edc4b8590c227fc6a50eaf6c. Repository working directory was read-only; new artifacts were generated in the permitted isolated workspace and published through GitHub. No device/main/Release change.


## 2026-11-09: local model restored and startup-helper execution

Latest checkpoint: synchronous/README.md, synchronous-validation.json and runtime-verification.json. The local-model service has been restored; two previously transport-only-failed requests completed and were reviewed, with one semantic pointer/status error rejected. A separate versioned UART lesson and new held-out example passed; completed jobs remain frozen. While collaborating, the coordinator executed40 complete original synchronous-helper cases for the two proven startup command IDs9/19. It accepts a matching header byte immediately; each of at most two attempts checks before up to500 sleep(1) calls. A reply after the last sleep can miss the final check; no milliseconds/physical bug or patch is inferred. GPIO cleanup/ABI preservation pass. Candidate database ID is retained but its startup-command scope is now dynamically proven; total database records remain62. Next: trace other reachable deferred-handler arguments/producers and aliases before broader helper/global-ownership claims; preserve external ADC/physical latency uncertainty. Current source baseline: bf33ebad2b3539fa29665c5548b28ad039f440f1. All new artifacts were produced outside the read-only checkout and integrated through GitHub's development branch; no device/main/Release change.
