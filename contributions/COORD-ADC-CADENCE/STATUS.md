# COORD-ADC-CADENCE — continuation, 2026-11-09

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
