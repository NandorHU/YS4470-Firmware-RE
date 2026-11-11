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

## General type-1 fallback

The producer suffixes at `0x8000e2dc`, `0x8000e36c`, `0x8000e3f4`
and `0x8000e480` submit type-1 records with +4 equal to `0x09`,
`0x0c`, `0x0f` and `0x0f`, respectively, and +5 equal to `0x19`.
The idle service reaches the original handler. At `0x80003e94`,
`0x80003ea4` and `0x80003eac`, it invokes the original helper with
`0x26 → record[4] → 0x19`. The first call is followed by requested
sleep(600) at `0x80003e9c`.

The [validation report](general-type1-validation.json) covers all
eight ACK-presence combinations for each caller and each original,
64 cases total. The handler proceeds through all three calls even if
all ACKs are absent. Each absent ACK causes its own two sends. The
observed wire frames are `c000c0`, one of `58035b`/`58075f`/`580b63`,
and `5a5a`. The status and flag are both zero at all three helper
entries. This establishes the scoped firmware call order under
the controlled queue, UART and sleep fixtures.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_general_type1.py --out work/general-type1-validation.json
```

## Original control queue and type 6

The constructor call at `0x800418a4` initializes the original 10 ×
68-byte queue and writes its handle to `0x805aae90`. The replay uses
the original constructor, send, receive and service with modeled
allocation and empty waiter lists. The [reference index](control-queue-index.json)
finds one immediate call to task-context send `0x80061acc`, at
`0x800067b8`, in both originals. It covers aligned ARM B/BL and ARMv5
Thumb immediate BLX, and separately records aligned exact pointers and
ARM literal references. Indirect targets and alternate primitives
remain outside that bound.

A host-supplied type-6 record is queued by original producer
`0x80006778`. The idle fallback requests sleep(200), clears the
two status words, calls the synchronous helper using byte +4, and
requests sleep(200) again. It then tail-calls `0x80006bb8` with
`(2, 720000000, 19200, 1)`. The original helper return does not gate
this tail call. Tests cover ACK success, two attempts with no ACK, and
command `0x30` rejected before send. The original setup programs PE7/PE8
mux value 3, UART2 divisor `0x0249` and final LCR 3. The original
interrupt routine writes `0x800073bc` into vector slot `0x805ab950`
and programs priority and enable for source 3. The reset wait and
helper sleeps are modeled and register values are memory shadows.

Queue order is material within the tested original service paths.
Two deferred records overwrite the same slot before dispatch, including
when the queue ring wraps. A type-3/4 record ahead of type 6 starts the
measurement FSM. Type 6 stays pending until the FSM returns idle in
the controlled no-reply schedule. In reverse order the pending type-6
record suppresses the later immediate request in that iteration.

The [replay](type6-queue-validation.json) pins 38 cases, both firmware
hashes, original instruction bytes, UART setup writes and receive
counts. The original producer accepts the supplied type, but these
fixtures do not establish a reachable factory caller supplying type 6.
Next follow type-2 and type-5 original producers through the deferred
dispatcher and measurement builder with the real queue.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_type6_queue.py --out work/type6-queue-validation.json
python -B contributions/COORD-ADC-CADENCE/synchronous/index_control_queue.py --out work/control-queue-index.json
```

## Deferred type-2 and type-5 measurement

The original choice suffix at `0x8000d084` reads the established
Fast CONT word `0x805ac788` (see the root measurement algorithms).
Value 1 takes the type-5 call at `0x8000d0a0` with bytes `22 13`.
The tested values 0 and 2 take the type-2 call at `0x8000d0c8` with
bytes `0e 19`. Both use the original producer and queue.

| Record type | Original builder call | Mode | Command list |
|---|---|---|---|
| 2 | `0x8000447c` | 3 | `0e 19 1d` |
| 5 | `0x80004410` | 3 | `0c 22 13 1d` |

The original deferred dispatcher sets discard count 2, stores the
primary configuration byte as a word and returns handled. With
matching setup headers the original FSM emits the entire selected
list. With the first ACK absent, it sends the first command twice
and returns idle without sending later commands. The first admitted
five-byte `0x1d` reply is consumed by the discard rule. In both
controlled mixed orders the last queued record selects the list.

The [replay](deferred-measurement-validation.json) contains 20
cases, the two original hashes, byte-checked execution and exact wire
frames. The caller suffix starts after its prior queue drain. Mixed
records are an accumulated-queue fixture. Allocation, arrival and
counter progression are modeled. Continue from `0x8000d39c`, where
the type-2 caller loads byte +5 from a live object rather than an
immediate value.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_deferred_measurement.py --out work/deferred-measurement-validation.json
```

## Dynamic type-2 selection

In both originals the setup at `0x80051818`/`0x8005182c` supplies
`0x8000d648`/`0x8000d294` as callback arguments. The callbacks then
execute under controlled UI inputs. The adjacent callback sets
`0x805abefc+1` to 1 at `0x8000d67c`. When Highspeed toggles off in
UI mode 1, the original type-2 producer at `0x8000d39c` uses
`[0x0c, 0x15]` if that byte is 1, else `[0x0c, 0x19]`. The
tested toggle-on branch with the byte set sends `[0x22, 0x15]`.
The adjacent callback can itself send `[0x09, 0x13]`,
`[0x0a, 0x13]` or `[0x0c, 0x15]` for the tested incoming selections.

In paired cases, the second callback's original queue drain removes
the first callback's waiting record before enqueueing its own. The
service then executes the remaining record's three-command list. The
test runs original callbacks, queue, dispatcher, builder and UART
transport. Widget style, feedback, allocation, counter progression
and replies are fixtures.

The dispatcher preserves secondary bytes `0x13..0x18` and maps all
others to `0x19`. All 256 values are tested on each original via the
producer API and checked through the actual second send. In the
[replay](dynamic-type2-validation.json), the 512 clamp/send cases are
separate from 36 Highspeed callback cases and 20 adjacent/paired cases.

### Independent compiled plan

`measurement_plan.c/.h` return a pure command plan for types 2–5.
The result lists the builder mode and commands, and whether to update
configuration and discard. Types 3/4 leave the caller's control state
alone. The function expects a valid output pointer and leaves its
buffer untouched for unhandled types. The result uses a semantic
struct. Original queue arbitration, MMIO and scheduling are separate.

The [differential report](measurement-plan-validation.json) verifies
4,108 cases against the original dispatcher and builder on both
firmware hashes. It covers all secondary byte values for each type
2–5 at two primary values, plus six unhandled record types per image.
The ARM object executes separately under Unicorn and the validator
rejects relocations in the function's section.

With Zig 0.13.0 and the existing analysis dependencies, create the
output directory and run from the checkout:

```powershell
$b='contributions/COORD-ADC-CADENCE/synchronous'
python -B "$b/trace_dynamic_type2.py" --out work/dynamic-type2-validation.json
zig cc -target arm-freestanding-eabi -mcpu=arm926ej_s -marm -O2 -ffreestanding -fno-builtin -ffunction-sections -std=c11 -Wall -Wextra -Werror -c "$b/measurement_plan.c" -o work/measurement_plan.o
python -B "$b/validate_measurement_plan.py" --object work/measurement_plan.o --compiler 'Zig 0.13.0' --out work/measurement-plan-validation.json
```

## Configuration, refresh and first publication

The [replay](refresh-publication-validation.json) executes the
original type-2 configuration callback and the refresh timer
registration at `0x800518c8`. The original timer due gate, refresh
`0x8005d048`, real queue, service, FSM, UART TX and RX ISR all execute.
The two original images agree in 18 sequences.

| Path | Type-3 refresh | Type-4 refresh |
|---|---|---|
| Configuration list | `0c 15 1d` | `22 15 1d` |
| Refresh measurement | `1d` (wire `6060`) | `1b` (wire `5e5e`) |
| First publication with all replies valid | Refresh measurement 2 | Refresh measurement 2 |
| First publication with first refresh absent or wrong header | Refresh measurement 3 | Refresh measurement 3 |

The configuration seeds discard 2. Its accepted terminal frame
consumes one slot. A valid first refresh consumes the remaining slot,
whereas no reply or a wrong header leaves it intact through the
retry and return to idle. Reconfiguration in either direction
re-arms discard while preserving the old result. Later callbacks
reach ResultDispatch with that old result until a fresh frame publishes.

The type-4 overlap fixture uses the original 25-unit period after
warmup. At counter 300 a refresh starts a measurement. At 325 the
next refresh enqueues another record and reaches ResultDispatch with
the prior value, but the service drains and skips the new request
while busy. An injected reply for the first request publishes at
counter 328, and the callback at 350 sees the new value.

Timer list and allocation, style/feedback, downstream
ResultDispatch/renderer behavior, counter steps and reply delivery
are controlled fixtures. The replay observes the stored value at
the dispatch boundary. It leaves actual rendering, peer behavior
and physical timing open.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_refresh_publication.py --out work/refresh-publication-validation.json
```

## Rendering and sound after refresh

The [replay](refresh-rendering-validation.json) extends the 18 lifecycle
sequences through original ResultDispatch `0x800037c0` and renderer
`0x8000326c`. It checks the exact float32 result at record +0x3c against
an independent reference and records the strings passed to display
leaves. The mode-1 fixture uses the original unit-table bytes restored
from V3.8 initialization. Type-3 uses the selector-specific decimal
exponent, and the config-`0x22` path uses float constant `0x41dfd1b7`.

In the extra integrated mode-4 Fast CONT schedule on each original,
the real UART parser publishes raw 14023 once. The three following
timer callbacks use that value before another queued request is
serviced. They enter the original filter at `0x80007c88` with values
5, 5, 5. The third update selects median 5, sound selector 10 and
action 1. Original gate and PWM setup then set shadow control
`0x7f` and period word `0x176f0a8c`. Mode, sound enable and initial
filter contents in this schedule are explicit fixtures.

Original numeric conversion and renderer control execute. The
`%.3f` conversion to text is a scoped host model because the
original formatter exceeded the instruction budget. Widget/display
updates and UI feedback are also models. PWM writes are emulated.
Next trace native mode entry and filter-reset writers.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_refresh_rendering.py --out work/refresh-rendering-validation.json
```

## Native mode entry and sound expiry

[Validation evidence](native-fast-cont-validation.json) records both factory
SHA-256s, per-case outputs, aligned literal hits and executed instruction bytes.
The two images agree in eight mode-transition cases and six countdown suffix
cases each.

The event-1 registration at `0x80051894..0x800518a4` loads callback
`0x8000cfd0` via literal `0x800519b4`. The original callback switches mode
1 to 4 and mode 4 to 3, sets the refresh warmup byte to 1, updates the timer,
and reaches the original queue and dispatcher. Type 5 sends
`[0x0c, 0x22, 0x13, 0x1d]` only on 1-to-4 with Fast CONT enabled.
The other tested cases use type 2 with `[0x0e, 0x19, 0x1d]`. Both seed discard
2 and the configuration terminal frame leaves 1. The stored raw 14023 and
selector 3, ring [5, 6, 7], index 2, count 3 and median 5 are seeded fixtures
and survive callback, dispatch and terminal frame. Graphical leaves, callback
feedback, heap, counters and UART arrivals are controlled.

The original task-loop suffix `0x8000553c..0x80005578` reaches the sound gate
at call site `0x80005568` with (5, 0) when active countdown 0 or 1 expires.
It clears the active word and writes zero duty through the original PWM path.
Active countdown 2 decrements to 1. No tested suffix modifies the stored result
or filter history. The suffix ends at the outer-loop continuation and uses a
PWM register shadow.

The aligned ARM PC-relative literal scan found `0x80005520`,
`0x80006e84`, `0x80007c8c` and `0x80007c90` for the named state and ring
addresses. The scan covers literal loads for these values. Synthesized aliases
and other task paths remain open. The next replay will link native entry to
the first two refresh callbacks and test the influence of retained history
on sound before fresh publication.

Run from the repository root with the same factory inputs and Unicorn setup.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_native_fast_cont.py
```

## First refreshes after native Fast CONT entry

[Replay evidence](native-fast-cont-first-refresh-validation.json) covers 16 schedules across the two factory
images, with four original timer callbacks per schedule. The matrix varies
presence of the first reply, prior active sound with a countdown of 1, and
populated versus empty filter state. All runs take the actual mode callback
`0x8000cfd0`, type-5 configuration through the queue and FSM, and four
type-4 poll records produced by timer callback `0x8005d048`.

The first callback enqueues the poll and advances warmup from 1 to 2 without
a ResultDispatch call. The second enqueues another poll, reaches ResultDispatch
at `0x8005d1a0`, and changes the timer period from 100 to 25 counter units.
At that point ResultDispatch still reads the seeded raw 14023 and selector 3.
The first valid poll reply consumes the remaining discard. First publication
follows poll 2 when the first reply is present and poll 3 when it is missing.
The next callback reads the newly published raw value.

The second callback passes filter input 5 from call site `0x80003970`.
In the populated case the ring becomes [5, 6, 5], median remains 5, and the
sound gate receives (10, 1). The countdown becomes 3 and the PWM shadow
holds control `0x7f` and period `0x176f0a8c`. This also happens after
original expiry at `0x8000553c` has switched off the prior sound. For the
same retained raw value with empty history the ring becomes [5, 1000, 1000],
fill becomes 1, median remains -1, and the gate receives (0, 0). The PWM duty
shadow stays zero on that callback.

The stored value, initial ring and optional prior active sound are controlled
fixtures. The original task suffix executes for expiry with its explicit
register preconditions. Timer list, heap, GUI leaves, numeric formatting,
UART arrivals and peripheral shadow use controlled models. These schedules
bound software ordering and register effects.

Run from the repository root with both factory images and Unicorn available.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_native_fast_cont_refresh.py
```

## KeyTask and Fast CONT refresh ordering

[Replay evidence](key-task-fast-cont-order-validation.json) covers both factory hashes and eight original
ARM926 schedules. The registration slice `0x800059c0..0x800059dc`
supplies entry `0x8000551c` and name `KeyTask` at `0x80005a68`.
The task creation call is observed at its boundary.

The loop samples a controlled key input, stores it at `0x805abb9c`,
requests delay 50 at `0x80005534`, executes watchdog update
`0x800085c4`, decrements a positive sound count, tests active sound,
increments the result sample counter, and takes the original back edge
at `0x80005578`. The watchdog and PWM are register shadows. Key sampling
and the scheduler delay are modeled leaves.

After original native mode entry and a warmup refresh that consumes the
remaining discard, the second refresh uses the retained reading. With an
initial active count of 1, KeyTask-first reaches the off call at
`0x80005568` before the refresh reloads the count to 3. Refresh-first
reloads 3 before the decrement to 2 and leaves duty on. With initial count 2
neither ordering requests off in the first pair. The remaining count then
expires after two or three isolated KeyTask iterations without a new
refresh. The harness chooses ordering between whole calls, retains the
seeded measurement and withholds the second poll's service.

The loop delay argument 50 and refresh period word 25 describe distinct
software interfaces. The scheduler, clock units, external peer and physical
timing remain open.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_key_task_fast_cont_order.py
```

## Scheduler delays and task wakeup

[Replay evidence](scheduler-delay-wake-validation.json) records 26 delay and 24 wake schedules across
the two factory images. The tested caller slices are `0x80005530` for
KeyTask (argument 50) and `0x80005d10` for the GaugeCmdTask service tail
(argument 1). A direct argument-zero case requests a yield without list
writes. A positive argument removes the task from its ready list through
`0x80060de0`, stores its unsigned deadline at `0x8004288c`, and inserts
through `0x80060e74`. A deadline of `0xffffffff` stays on the current
list, and a wrapped deadline of zero goes on the overflow list. The
nonwrapped path lowers the next-current-deadline word when appropriate.

With a pending yield, the unlock path invokes SVC through `0x8006230c`.
Otherwise the delay helper uses its tail at `0x80060ff0`. Both routes
execute the original `svc #0` instruction at `0x8000222c`. The emulator
traps the exception and does not run the SVC handler.

The wake cases call original `0x80061fa4` and keep the waiting task
off the ready list until the 1st or 50th applied tick, according to the
original caller argument. At counter wrap the two delay-list pointers
swap and the wrap counter increments. The due task is unlinked, inserted
on its priority-ready list, and requests yield against the fixture's
lower-priority current task. In the deferred cases, the suspended tick
increments the pending word and leaves the clock unchanged. Original
unlock `0x80062204` applies the pending tick via `0x800622e4`.

Task ownership and list nodes are controlled fixtures. The host selects
the other ready task after the trapped SVC. The byte-checked IRQ dispatch
at `0x8000232c` loads the tick entry from `0x800023a8` and reaches an
indirect branch at `0x80002334`. This interrupt path was inspected
statically. The next replay will exercise it with controlled exception
and task context. These tests use software counters and supply no
physical interval.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_scheduler_delay_wake.py
```

## Installed vectors and scheduler context

[Replay evidence](scheduler-irq-context-validation.json) covers 4 vector installations, 24 tick IRQ
scenarios and 16 original delay/SVC-to-IRQ round trips across the factory
images. The original slice `0x80000030..0x80000060` clears CP15 control
bit 13 and copies the 64-byte template at `0x800023b0` to low memory.
The test enters through the resulting SVC slot at `0x08` and IRQ slot
at `0x18`.

The IRQ handler `0x800022c0` saves the interrupted r0–r14, status, critical
nesting and IRQ LR. With INTC pending bit 13, the original handler calls
`0x80061fa4` and calls the selector `0x800612f8` only on a nonzero tick
result. Idle, future-deadline and suspended scenarios return to the same
task. A due higher-priority task, a deadline at wrap, or an eligible
same-priority peer produces a switch. Both ARM and Thumb states are restored.
The writes to the two register shadows precede the exception return at
`0x80002390`.

The original delay calls supply 1 or 50. Their `svc #0` reaches the
installed SVC slot and original handler `0x80002234`, then restores the
other ready task via `0x800022bc`. Subsequent tick IRQs leave that task
current until the delayed task is due. The last tick restores the original
task and its delay continuation, including KeyTask return `0x80005538`.
Cases cover ARM and Thumb peer contexts and deadlines that wrap.

The host seeds banked CPU state on exception entry and controls task frames,
list membership and register shadows. Silicon interrupt delivery and clock
frequency are outside the replay.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_scheduler_irq_context.py
```

## Timer0 and UART2 through the installed IRQ route

[Replay evidence](timer0-uart2-irq-validation.json) records 24 routing and 16 linked transport
cases across the two factory images. The original startup slice
`0x800617ec..0x80061818` sets Timer0 control 7 and interval 24000, and
registers IRQ13 with helper `0x8005bf54`. The original UART2 tail at
`0x80006d5c` registers IRQ3 with ISR `0x800073bc`. Both registrations
use the same handler table.

After original low-vector installation, the IRQ entry examines INTC
pending bit 13. With that bit set it executes the scheduler tick and
does not read the INTC vector latch in the tested route. When both bits
are set and the latch points to UART2, the tick route still runs. Only
a later explicit UART IRQ appends the byte. This second event is injected
by the harness. It does not establish whether hardware reasserts it.
With only UART2 pending, `0x80005260` dereferences its registered slot.
The original ISR appends at count 0 or 199, performs no buffer write at
count 200 or with RX-ready clear, and leaves the scheduler count unchanged.
ARM and Thumb interrupted task contexts are restored.

The linked transport cases invoke original transaction builder
`0x8000489c` and FSM `0x80004490`. In each tested reply a Timer0 IRQ
advances the count between UART2 byte IRQs. The original FSM parses a
matching five-byte frame from the shared IRQ-filled buffer. It publishes
raw `0x012345` with selector 6 for command `0x1d` and selector 0 for
`0x1b` with the test input selector 8. A pending discard consumes the
valid frame without changing the stored measurement. A wrong header
produces one retry. A four-byte prefix remains pending in this schedule.
Neither malformed frame publishes.

The host chooses entry points for builder/FSM calls and supplies pending
bits, vector latch, UART status/data, and banked IRQ entry state. These are
software-ordering tests with register shadows. Timer progression, interrupt
arbitration and physical latency are outside their scope.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_timer0_uart2_irq.py
```

## Scheduled GaugeCmdTask service and fallback

[Replay evidence](gauge-scheduled-service-validation.json) contains 26 cases across the two factory images.
The harness enters the original post-startup loop at `0x80003dd0`.
The original queue constructor uses an allocated fixture of 760 bytes
and sets ten 68-byte entries. Enqueue, dequeue, deferred copy, FSM and
fallback execute from original bytes. The already-covered startup IDs
9 and 19 are outside this replay.

For `0x2a` and `0x2b`, the original helper `0x80005f14` waits through
the original SVC path. UART2 IRQ fills the RX buffer while the other
task is current, and an injected Timer0 IRQ wakes GaugeCmdTask. A
matching byte in the first window returns 1. With no match, the
first 500 one-count waits end in an original retry and receive reset.
The second attempt can return 1. Without a reply it waits another 500
counts and returns 0. In the wrong-then-match case the harness leaves
the wrong first byte in place until retry, then offers a matching byte.

A type-3 record starts a measurement before a queued type-1 fallback.
The service preserves the deferred record while the FSM is busy. If
another type-1 record is queued during that interval, the next service
pass drains it into the same deferred slot. The fallback invokes only
the newer command after the measurement publishes and the FSM goes
idle. The original producer slice `0x8000e7c4..0x8000e7e4` supplies
type 1, `0x27`, and secondary `0x13` to the real queue. The scheduled
helper sends `c0 55 15` and accepts a matching UART2 IRQ byte.

The original scheduler and exception handlers run. Queue allocation,
initial task frames, incoming interrupts and UART data are controlled.
For the replacement case the host invokes the original enqueue entry
while GaugeCmdTask is waiting. The other task runs to a fixed stop
boundary. The tick counts establish software ordering, with physical
duration and peer conversion outside the replay.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_gauge_scheduled_service.py
```

## Scheduled long fallback and status waits

[Replay evidence](gauge-long-fallback-validation.json) covers three original producer paths per
factory image. The harness starts at the original producer suffixes
`0x8000e61c` (type 0), `0x8000e4f4` (type 1, `0x28`) and
`0x8000e588` (type 1, `0x29`). The original queue, GaugeCmdTask loop,
SVC selection, Timer0 and UART2 IRQ paths execute. The already verified
earlier queue-drain calls are outside this slice.

The type-0 case waits 200 applied ticks, sends helper `0x26` frame
`c0 00 c0`, and accepts the matching byte after the helper's first
one-count wait. The extended commands wait 600 before helper `0x27`,
then wait 500 twice before the command frame. Each matching ACK is
delivered through UART2 IRQ during the first one-count helper wait.

The command ACK carries two premature status bytes in each fixture.
The critical clear at `0x80003f24` removes all three bytes. A different
two-byte status packet arrives during the next 10,000-count wait.
The critical clear at `0x80003f44` removes it. The first status poll,
at `0x80003f68` after 1,000 additional applied ticks, sees only the
fresh fixture `a0 02` or `a1 04`. The corresponding status is 2 or 7.
Helper `0x26`, the 2,000- and 500-count waits and original GPIO cleanup
complete before the next service sleep. The raw measurement stays at its
seeded value.

In each nonfinal tick of a wait the other task remains current and the
selector stays out of the path. At the deadline the original IRQ selects
GaugeCmdTask, which runs until its next SVC switches back. The six cases
use 60,814 individually injected Timer0 interrupts. The timer source,
physical duration and peer behavior remain outside the replay.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_gauge_long_fallback.py
```

## Live calibration status and UI timer

[Replay evidence](calibration-ui-live-validation.json) contains four schedules, 60 original timer
callbacks and 60 one-count-early controls. The writer and timer share
one emulator. The harness starts from the factory-initialized globals,
runs the original status producer and GaugeCmdTask chain, then invokes
the original GUI timer runner `0x8004092c` on its counter edges after
GaugeCmdTask yields. The constructor call at `0x8004c4ec` binds
`0x8005da88`.

For `0x28`, timer binding at counter 100 produces the first status 2
display at 14,100, after the flag clears. For `0x29`, binding at 702
puts the original timer deadline at 12,702 when the status writer
has just set 7 and is still waiting on the final helper with flag 1.
The callback reads status 7 without reading the flag. Its next result
callback still displays the same text with flag 0. The waiting phase
uses `Calibration ...` and retains 2,000. Status 2 formats
`Cal circuit 1 OK02`, status 7 formats `Cal over range04`, and the
result paths write period 200. The original formatter and label copy run.

The GUI runner entry is host-scheduled. Fixed allocation, invalidation
leaves and a one-item timer list support the original code. The tested
statuses come from the original IRQ and writer path. Peripheral clocks,
pixels and peer behavior are outside the replay.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_calibration_ui_live.py
```

## Calibration reset to fresh measurement

The [same scheduled replay](calibration-ui-live-validation.json) also
continues after each of the four linked calibration schedules. Original
reset stores at `0x80046cb0` and `0x80046cb8` clear the flag and status
at counter 15,203. The next original timer callback reads both zeros and
uses the real queue at call site `0x8005dc38`. The queue receives type 3
with prefix `030000000000`. One-count-early controls still produce no
callback.

The next original service pass dequeues the request and sends `60 60`.
The UART2 IRQ receives `60 45 23 01 03` and the original parser
publishes raw 74565 and selector 3. Both timer phases reach the same
result. The pre-request label `.OL` uses a seeded over-range raw value.
The original reset slice stops after the two stores. The host schedules
the GUI runner and the peripheral interrupts as before.

## Calibration buttons and pending queue

[Replay evidence](calibration-button-queue-validation.json) covers both complete original button
callbacks, `0x8000e4c8` and `0x8000e55c`, in 12 cases across the two
factory images. Each callback resets the original timer to 2,000, calls
the drain at `0x80003d74`, enqueues a type-1 record and formats its mode
label. The drain uses an allocated 68-byte fixture, then runs the actual
zero-wait receive until the queue is empty.

With an old type-3 measurement and type-1 control still queued, the
drain reads both in order. Only the new calibration request is consumed
by GaugeCmdTask. The original scheduled status path and UI timer reach
status 2 or 7 with their factory labels.

With the measurement already sent, the button drains only the queued
control request. GaugeCmdTask defers the new calibration record while
the measurement is busy. A matching UART2 IRQ reply publishes raw
74565 and selector 3. The original fallback then begins its 600-count
wait. This case ends at that wait.

The null-allocation fixture makes the drain return before receiving a
record. With room in the queue, the button still appends the new
calibration request behind both original pending records.

Heap allocation/free, GUI invalidation, task initialization and incoming
IRQs are fixtures. The original queue, scheduler, formatter and status
logic execute. These cases establish software behavior with controlled
counter progression.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_calibration_button_queue.py
```

## Queue entry candidates and full-queue waits

[Replay evidence](queue-interior-full-validation.json) pins both original firmware hashes. The
static index covers external immediate branches into three known queue
regions, including function interiors. It checks ARM B/BL, Thumb BLX,
immediate ADR and literal loads, and four byte phases for exact pointers.
The index finds 38 external raw branch matches, eight object
materializations and seven exact object words. The single raw interior
match at `0x8009ef10` decodes as `ble #0x80061b18`. The byte
neighborhood and the two raw incoming matches are retained for
provenance review. Native type-6 production remains unresolved.

The field scan looks for an ARM word store to +0x38 with same-base
loads at +0x3c and +0x40 within 512 bytes. Three matches occur in the
known queue implementation. The other two neighborhoods have local GUI
or result evidence. At `0x80046548` the stored value is passed to
the original label routine. At `0x8005d35c` the base literal resolves
to the measurement result object at `0x805ac714`. This bounded
signature leaves aliases and alternative access patterns open.

Six ARM926 cases fill the original ten-entry queue. A type-3 zero-wait
request returns zero immediately. The original `0x27` producer at
`0x8000e7c4` blocks on the full queue. With only injected ticks, it
resumes after ten and returns zero, reaching `0x80061b18` from the
sender's back edge. In the other schedule, an original receive at the
third count removes the head and wakes the blocked sender. It returns
one and writes its 68-byte record into the newly available slot. The
other records remain unchanged. Task event-list ownership and priority
are seeded from the original task-creation instructions, and initial
queue allocation and IRQ entry are controlled.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_queue_interior_full.py
```

## Direct control producers and result-block writer

The [replay](control-producer-suffix-replay.json) starts at the original local argument
setup for 31 direct ARM sites that call `0x80006778`. In 33 cases per
factory image the original constructor at `0x800029dc` creates an empty
control queue using a modeled allocator. Its only handle store occurs
at `0x800029f4` and writes `0x805aae90`. The original send at
`0x80061acc` copies all 68 bytes and increments the queue count once.

The suffix beginning at `0x8005d118` reads the local state byte. The
tested `0x21` and `0x22` inputs send types 3 and 4 respectively, each
with zero argument bytes. The `0x8000d378` suffix sets a default second
argument of `0x19` and uses the low byte of `r6` when its original
condition is true. Ten local suffixes also check the original writes to
the selection bytes. The tested direct sites emit types 0–5.

Four result-writer cases per image run the original `r5` literal load
at `0x8005d27c` followed by the writer suffix at `0x8005d34c`.
The store at `0x8005d35c` targets `0x805ac74c`, within the result
block at `0x805ac714`. The six result words clear for signed inputs
below `0x40000000` and remain intact at the boundary. The queue
object and handle stay byte-identical in these cases.

The runs supply an idle scheduler and the incoming local state. The
replay covers the local argument setup and the queue copy. Earlier
caller reachability, intermediate GUI calls in the result-writer
probe and native type-6 provenance remain open.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_control_producer_suffixes.py --out control-producer-suffix-replay.json
```

## GUI field provenance at 0x80046548

The [original replay](gui-field-provenance.json) starts at `0x80057948`, carries
the original context through `0x800579b8` into `0x80045ea8`, and stops
at `0x800466c4`. The original constructor `0x80030ad0` creates and
registers each child, including the label stored at context `+0x38`
by `0x80046548`. The descriptor literal at `0x80030af0` names
`0x80068ee0`. The original indirect call at `0x80034928` reaches the
descriptor's callback `0x800309f0`.

The original callback sets the initial text to `Text`. The initializer
then sets the label at context `+0x38` to the empty string at
`0x800462f0`. The neighboring context `+0x3c` is a parent pointer
and `+0x40` a separate child label. The original text setter and its
Thumb length and copy routines execute. The replay checks six created
labels and child lists in each case.

The two layouts use different context and heap addresses and start
with zero or three records in the original control queue. The control
block and the entire queue allocation are checked byte-for-byte.
Allocation, display roots, parents and selected layout and styling
leaves are fixtures. The test covers initialization up to the stop
address and the stores on that path.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_gui_field_provenance.py --out gui-field-provenance.json
```

### Interior branch-like word in the font bitmap

The factory font descriptor at `0x800a56d4` selects the original
bitmap accessor `0x8002c844`. The format descriptor at `0x800a56bc`
supplies the glyph table and bitmap base. The original lookup and
cache map U+007C, U+007D and U+007E to glyph indices 93, 94 and 95.
Both cold and warm U+007D lookups return `0x8009eec2`.

Glyph 94 has an 11 by 31 bounding box. The packed bytes occupy
`[0x8009eec2, 0x8009ef6d)`, as checked against the next glyph offset
and the packed length. The raw word `000bffda` at `0x8009ef10`
is 78 bytes into that interval. The lookup cases use the original font
data and check the actual cache accesses. They cover the identified
font resource; register-indirect queue-writer coverage remains open.

## Registered GUI callbacks and indirect queue producers

The [replay](control-gui-event-validation.json) executes the original registration block
`[0x8004c3b4, 0x8004c47c)` with ten seeded UI object pointers. The
literal table at `0x8004c50c` supplies the native callbacks. The
original helper at `0x800338dc` initializes an event descriptor
for each object with filter 1 and a zero user value.

The original event sender at `0x8002c758` enters the dispatcher
at `0x8001ae74`. In each of the 20 matched cases across both images,
the dispatcher loads the callback from its runtime descriptor and
calls it through `0x8001b030`. The callback changes the original
timer fields, receives both previously queued records, and appends
one new 68-byte record via `0x80006778` and `0x80061acc`.
The 20 event-code-2 cases preserve the entire queue, timer and
selection. The scheduler count stays fixed.

The second original registration block
`[0x800517f4, 0x800518bc)` binds nine filter-1 callbacks and one
filter-`0x1c` callback. The replay also dispatches `0x8000d294`
from this block. Across all eight binary combinations of the
three local bytes at `0x805abefc`, the handler toggles byte +2.
With byte +0 equal to 1, clearing +2 sends type 2 with argument
`0x0c` and second byte `0x15` or `0x19`, depending on byte +1.
Setting +2 sends type 2 with `0x22, 0x15` when +1 is 1.
The other five combinations leave the queue intact.

UI objects and input events are supplied. Allocators, formatting,
text display and selected style helpers are modeled. The type-2
sound helper executes its disabled branch. The test covers the original dispatch,
queue and timer RAM stores under the idle scheduler fixture.

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_control_gui_events.py --out control-gui-event-validation.json
```

## Second GUI block, callback `0x8000cfd0` (2026-11-11)

The original second registration block and dispatcher route event 1 from GUI object `+0x2b8` to `0x8000cfd0`. Both factory images agree in 24 ARM926 cases. Mode 3 with word `0x805ac788 == 1` sends type 5 (`05 00 00 00 22 13`). Mode 3 with word 0 or 2 and mode 4 with any tested word send type 2 (`02 00 00 00 0e 19`). Event 2 leaves the callback and queue untouched. The scheduler is idle and selected UI leaves are modeled.

The callback executes the original timer-object stores, a secondary helper with arguments `(4, 4, 255)` or `(4, 3, 255)`, and the queue drain at `0x80003d74`. The secondary guard at `0x805aac40` is seeded to 0, so the helper returns `0xffffffff`. The scheduler tick remains 100 and the previous event chain is restored. Physical input, timing and the downstream consumer are outside this run.

From the repository root with `tools/analysis-requirements.txt` installed, run:

```powershell
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_control_gui_cfd0.py --out control-gui-cfd0-validation.json
```

[Recorded cases, original hashes and executed instruction bytes](control-gui-cfd0-validation.json).
