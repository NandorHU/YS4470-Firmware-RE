# Synchronous startup commands and restored local collaboration — 2026-11-09

The owner explicitly requested starting the installed local model while away
from the computer and continuing collaboration. I located the existing signed
portable Ollama under the legacy project's local-ai/runtime, rather than
reinstalling it or downloading weights. The executable SHA-256 is
`544216ca2082b8bc19b4ba94b513f0098fa06774b232f3c140090e3449e322a5`;
Authenticode reported Valid, publisher Ollama Inc. Ollama0.40.15 now listens
on127.0.0.1:11435 with cloud disabled, one concurrent request/model, flash
attention and q8_0 KV cache. Logs/temp files are in an isolated writable workspace.
No login startup, Windows service, registry or firmware change is made.

Both existing models are available. The reviewed coder is qwen2.5-coder:14b,
digest `9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849`.
After inference, /api/ps reported size=size_vram=9,107,029,359 and context4096.
This is runtime residency evidence, not a comparative quality/speed claim.

## The local model's bounded work

I explicitly retried the two failed transport-only requests from the previous
run. Their original manifests, inputs and WinError10061 receipts remain intact;
neither task had reached model inference before. The model received checked
lessons and source only, with no shell/Git/REA/device tools.

- The RX index reply quoted the RAM count store correctly, but mislabeled the
  pointer-literal load0x800073bc as UART status. The actual status read is
  0x800073c8. Its claimed final-write limit was also wrong: byte store0x8000740c
  follows the count store0x80007408.
- The synchronous-helper reply correctly selected clear0x80005f30 and delay
  call0x80005fe8. Its limitation merely restated BL and was not useful.
- All four quotes matched supplied source, yet only three semantic extractions
  were correct. Both replies used the wrong requested JSON keys. They were
  manually reviewed; no automated database/firmware finding was accepted.

The two requests produced183 tokens in12.062s, including the first model load.
I recorded the correction in a separate versioned LESSONS-UART.md rather than
editing the base lessons and breaking frozen-job hashes. A **new**, held-out TX
classification question then returned the correct two candidate IDs with the
exact requested schema (19 tokens,1.094s). This is one in-context exercise,
not weight training or evidence of general reasoning improvement. There is
no model-generated code execution. See local-review/ and local-heldout/.

## Coordinator binary execution

While the model indexed source, I executed the complete original synchronous
helper0x80005f14, its real sender/byte-output/ISR/copy/clear/GPIO routines for
the two previously proven GaugeCmdTask startup arguments9 and19 (0x09/0x13).
Both originals pass the same20 cases,40 total; initial FSM is idle. The native
caller arguments were already bound by the earlier GaugeCmdTask packet proof.
Other descriptor IDs/UI modes are outside this new execution proof.

| Observation | Established for the tested startup helper |
|---|---|
| Source/wire | ID9 source5803→wire58035b; ID19 source5900→wire590059 |
| Matching one-byte header before first check | Return1 without a sleep |
| Matching five-byte input with arbitrary trailing payload | Return1; all5 RX bytes remain |
| No/wrong header | Two sends; return0 after1,000 requested sleep(1) calls |
| First attempt: matching header after499 sleeps | Return1 after499 sleeps |
| First attempt: header delivered after500th sleep | Header is cleared before retry; no new reply gives return0 |
| Second attempt: header before first check | Return1 after500 total sleeps |
| Second attempt: header after499 sleeps | Return1 after999 total sleeps |
| Second attempt: header after500th sleep | Return0 with matching RX header/count1 still present |
| Matching old header injected during TX | Return1; no request-instance identity is checked in this tested path |

The loop checks RX **before** each sleep, then increments its loop counter.
Delivery after the final sleep can therefore miss the final check. This is an
instruction-order/deadline-boundary result, not an established bug, physical
delay or justified speed patch. The500 constant is a per-attempt maximum loop
count, not a mandatory delay and not500 milliseconds. The helper ACK condition
uses a matching first byte, distinct from the measurement FSM's five-byte rule.
Only byte delivery, sleep scheduling and UART status are models; CPU context
interleave uses the previous explicit harness. GPIO bits2/3 are cleared on
all tested exits; callee-saved registers and nesting are preserved.

[synchronous-validation.json](synchronous-validation.json) pins both inputs,
the reused harness, source,40 cases and203 observed instruction addresses per
original. These results do not measure external ADC conversion/restart,
actual task scheduling, Base profile superiority or acoustic response.

## Reproduction and continuation

With pinned analysis dependencies installed:

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python"
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_synchronous_helper.py
```

Use --repo and --out-dir for an isolated output path. Existing originals stay
unchanged. No source generator, patched firmware or device operation occurs.

start_local_server.ps1 takes explicit OllamaExe, ModelDirectory and writable
StateDirectory arguments, verifies the reviewed executable/signature, and
starts only an absent local server with hidden windows and loopback binding.
It never pulls models or stops an existing server. The already-running API
was rechecked successfully; the cold-start path was executed by the equivalent
recorded native launch before this reusable script was written.

The local retry/exercise folders are frozen completed jobs. Do not rerun them
or the old31-task batch. For new local tasks, use the checked base lessons plus
the UART correction, a new small source/manifest and strict completion, exact
schema, quote and semantic review gates. Keep exact arithmetic/hashes and ARM
execution with deterministic tools/coordinator. Native server remains available
for subsequent bounded tasks; model keep-alive is30m, not an endless work batch.

Next prove further **reachable** deferred-handler command/helper paths and their
message producers. Keep the known service-idle precondition, other aliases,
installed application identity and physical ADC/latency questions separate.
The normal asynchronous measurement FSM is not this startup ACK helper.

## Deferred producer paths

The replay starts immediately after each caller's queue drain, runs its original
record-producing suffix and `0x80006778`, then runs `0x80005b6c` with the FSM
idle. The original service consumes the record, copies 68 bytes to
`0x805ac6d0` and back to its stack, clears the pending byte and calls the
fallback after `0x80004390` returns zero.

| Producer call | Record (type, +4, +5) | Helper call | ID | UART frame |
|---|---|---|---|---|
| `0x8000e634` | `0, 09, 13` | tail `0x8000404c` | `26` | `c000c0` |
| `0x8000e6c4` | `1, 2b, 00` | `0x80003eac` | `2b` | `c4c4` |
| `0x8000e750` | `1, 2a, 00` | `0x80003eac` | `2a` | `c3c3` |
| `0x8000e7e0` | `1, 27, 13` | `0x80003eac` | `27` | `c05515` |

All 16 cases agree across the two originals. A one-byte matching header
injected before the first check gives return 1 with one send and zero helper
sleeps. A missing reply gives return 0 with two sends and 1,000 requested
helper sleeps. The type-0 path separately requests sleep(200); the service
requests sleep(1) at the end of all cases. Queue transfer, UART status/arrival
and sleep are explicit models. Upstream UI dispatch and physical timing remain
outside the replay.

The [report](deferred-validation.json) includes both firmware SHA-256 hashes
and executed instruction bytes. Reproduce from the checkout with the existing
analysis dependencies:

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_deferred_producers.py --out work/deferred-validation.json
```

Create the output parent directory before running. Next trace the producers
at `0x8000e50c` and `0x8000e5a0` into the extended `0x28`/`0x29` path at
`0x80003eb8` and distinguish its later status bytes from the helper ACK.

## Extended status after 0x28/0x29

The original caller suffixes at `0x8000e4f4`/`0x8000e588` send type-1
records via `0x80006778` with byte +4 equal to `0x28`/`0x29`. The idle
service delivers each record to `0x80003dd8`, which branches to
`0x80003eb8`. Both original images pass the same 32 cases (64 total).

1. At `0x80003ec4` the handler calls the helper with `0x27` (UART frame
   `c05515`). A zero return still leads to the next helper.
2. At `0x80003f10` it calls the helper with `0x28` (`c1c1`) or `0x29`
   (`c2c2`). A matching first byte is enough to return 1. Return 0 skips
   the status loop after the helper's two failed attempts.
3. The original critical sections clear the RX count and buffer twice,
   with a requested sleep(10000) between them. A status behind the ACK
   or injected between the clears is discarded in the tested schedules.
4. At `0x80003f60` the loop requests sleep(1000) and then checks RX byte 0
   at `0x80003f68`, for up to 230 iterations. A recognized `a0`/`a1`
   header selects a read of RX byte 1. A single `a0` byte after a clear
   takes this path with byte 1 still zero. An unknown leading byte kept
   polling even after a valid pair was appended behind it.
5. A recognized header leads to helper ID `0x26` (`c000c0`) at
   `0x80003fe8` even when byte 1 does not map to a value. This is
   followed by the original flag and GPIO cleanup. With no recognized
   header by poll 230, the handler clears the flag and exits without
   calling the `0x26` helper.

| RX prefix | Value stored to `0x805ab920` |
|---|---|
| `a0 01`, `a0 02`, `a0 03` | 1, 2, 3 |
| `a1 01`, `a1 02`, `a1 03`, `a1 04` | 4, 5, 6, 7 |
| Recognized header with an unmapped second byte | Remains at the entry value 0 |

The [validation report](extended-status-validation.json) pins both image
hashes, the caller and helper instruction bytes, return values, wire frames
and representative RX samples. The run executes the original service,
critical helpers, UART sender and RX ISR. The queue, requested sleeps,
UART status and interrupt delivery schedule are controlled fixtures.
The report records software arguments and iteration counts. Peer semantics,
physical timing and complete task scheduling remain open.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_extended_status.py --out work/extended-status-validation.json
```

Use the existing analysis dependencies and create the output parent
directory before running. Next validate the status reader candidate at
`0x8005dac4` and trace where the seven decoded values go.

## Calibration status UI

The original registration suffix at `0x8004c454` installs callbacks
`0x8000e4c8` and `0x8000e55c` with event code 1. The two original
callbacks drain the queue through `0x80003d74`, submit type-1 records
for `0x28` and `0x29`, and write the original labels
`Cal Circuit 1 mode` and `Cal Circuit 2 mode`, respectively.

The original registration at `0x8004c4ec` constructs a periodic timer
with callback `0x8005da88` and initial period 2000. Its due path calls
the callback at `0x80040a0c`. The callback reads the stored status at
`0x8005dac4` and, when status is zero, the flag at `0x8005dbfc`.
The original Thumb formatter and original label setter/copy execute.

| Status | Original label text |
|---|---|
| 1 | `Power On OK01` |
| 2 | `Cal circuit 1 OK02` |
| 3 | `Cal circuit 2 OK03` |
| 4 | `EEPROM error01` |
| 5 | `EEPROM initail error02` |
| 6 | `EEPROM write error03` |
| 7 | `Cal over range04` |

For status 0 with flag 1, the callback displays `Calibration ...` and
keeps period 2000. A recognized result selects period 200. Status 0
with flag 0 queues a type-3 record and selects period 200. The
raw-result sentinel fixture in this branch displays `.OL`.
The eight linked sequences use status snapshots from the original
deferred writer. On the same timer they cover waiting, the result or
timeout, one repeated refresh, and a refresh after the two original
reset stores at `0x80046cb0`/`0x80046cb8`. Each deadline is checked at
equality and one raw counter unit before it, including counter wrap.

The [UI replay](calibration-ui-validation.json) includes 40 status
cases, eight linked sequences, both image hashes and observed bytes.
The experiment uses fixture objects, allocation/queue/GUI invalidation
leaves and a one-item timer list. Snapshot transfer is a controlled
task boundary. Counter units, label strings and copied text do not
establish physical calibration timing, peer implementation or pixels.

The [producer index](control-producer-index.json) scans all aligned
ARM immediate branches to `0x80006778` in both images. The 31 matches
have local setup types 0–5. The report preserves the exact four
instructions per site. Indirect branches and alternate queue writers
remain separate from this index.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_calibration_ui.py --out work/calibration-ui-validation.json
python -B contributions/COORD-ADC-CADENCE/synchronous/index_control_producers.py --out work/control-producer-index.json
```
