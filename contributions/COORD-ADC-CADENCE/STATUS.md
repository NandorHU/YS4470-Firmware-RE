# COORD-ADC-CADENCE — continuation, 2026-11-09

## Current checkpoint

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
