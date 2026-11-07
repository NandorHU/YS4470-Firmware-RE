# Stored-result reuse in the Fast CONT refresh path

## Bounded result

The tested original refresh path can call the filter repeatedly using one
unchanged stored result. A filter invocation is therefore not, by itself,
evidence of a distinct UART reply or a newly published sample. This is a
synthetic original-code counterexample, not a capture of live device timing.

The original callback at0x8005d048 enqueues event4 when UI configuration+7 is0x22.
Existing command-dispatch evidence maps that event to command0x1b. It sanitizes
the stored selector and uses UI byte0x805abefc+9 as an initial two-call counter.
At counter>=2 it calls ResultDispatch at0x8005d1a0. The tested path does not
require a changed result, inspect UART RX data, or decrement the parser's
discard count before that call. Queue delivery and scheduling are outside this
experiment; enqueuing a poll is not modeled as a completed reply.

ResultDispatch's actual entry is0x800037c0. In the Fast CONT branch it executes
the numeric conversion, then calls the actual history filter at0x80003970.
The complete original filter/gate/arithmetic/PIO/PWM path executes on ARM926.

## Persistent counterexample

Explicit initial state: mode4, Fast CONT=1, config0x22, notification state0,
warmup0, stored raw result14023, discard count2, history=[1000,1000,1000],
count0/median-1, sound enabled and inactive. This is a test fixture, not a claim
about the factory power-on state. No parser or UART ISR runs between callbacks.

| Callback | Warmup after call | Filter count | Median | Emulated active flag |
|---|---|---|---|---|
| 1 | 1 | 0 | -1 | 0 |
| 2 | 2 | 0 | -1 | 0 |
| 3 | 2 | 1 | -1 | 0 |
| 4 | 2 | 2 | -1 | 0 |
| 5 | 2 | 3 | 5 | 1 |

All five calls preserve the raw result/selector and RX buffer. Parser-entry
count remains0; discard count remains2. This demonstrates that a ring full of
equal values need not represent three distinct parser publications.

A second sequence runs admitted original command0x1b parser slices between
callbacks. The first two entries decrement discard2→1→0 and retain the previous
result; callbacks still run the filter. The third entry publishes raw1402300,
which converts to500. After this single publication, three callback uses of
that stored value establish median500/off, with no further parser entry.

## Caller conversion and reset distinction

The original branch converts the signed result to float32 and divides by literal
bits0x452f499a (2804.60009765625). It clears negative finite outputs through the
observed unsigned-bit comparison and rejects values>=float32(1000.0). Accepted
values are truncated to integer0..999 before the filter call. The source scalar's
physical unit remains unassigned.

Raw14023 gives helper argument5. Raw2804600 remains just below1000 in this
float32 sequence and gives999; raw2804601 enters the reject branch. The
0x007fffff sentinel also takes its own off branch.

Both rejection paths request SoundControlGate(0,0) without calling the filter.
They leave its history/count/retained median intact in this tested callback
model. After a stable median5, rejection turns the emulated active flag off;
returning to the accepted stored value requests the old tone on the next call.
The standalone helper's >1000 history reset, proved previously, is not reached
through this caller's accepted0..999 argument path. The pure-C component remains
correct as a helper reconstruction; it is not the entire caller policy.

## Registration, period arguments and entry corrections

Original slice0x800518bc..0x800518d8 passes(callback0x8005d048,100,0) to API
0x80040894 and stores its returned handle at0x805abeb8. The creation API itself
is a stub. Original0x80040b84 stores the requested word into handle+0.

Tail-branch probes establish arguments25 for mode4 (also mode1/highspeed1/
secondary21),100 for the other highspeed1 paths, and200 otherwise. These are
period-field arguments, not proven milliseconds, actual callback intervals or
response rates. Earlier warmup returns skip this tail update.

Two old seed interpretations are corrected:

- 0x800037bc contains literal0x805abf10, read by PC loads at0x80003688,
  0x80003710 and0x80003774. It is not the ResultDispatch entry;0x800037c0 is.
- 0x8005d1a0 is the callback's BL ResultDispatch, not a separate
  HighspeedDiodePeriodSelector function entry. The callback begins0x8005d048.

The inventory seeds and machine database are corrected. Historical13-seed
reports remain evidence of their saved byte windows/exports; their labels do
not establish genuine whole-function boundaries at these two old coordinates.

## Reproduce and scope

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python;$PWD\tools"
python tools/trace_result_freshness.py `
  --input 'V3.6=<original path>' --input 'V3.8=<original path>' `
  --out evidence/2026-11-07-result-freshness.json
```

Per original:295 callback matrix cases,23 persistent callback steps,3 admitted
parser steps,54 period-branch probes and one binding slice. Across originals:
752 checked cases/steps; identical fingerprints, zero failures. Actual PyGhidra
exports five proof-labelled entries per original without rerunning the13-seed
inventory. Nine proof-label/provenance tests pass. See the two result-freshness evidence
JSON files for read traces, state sequences, guards, assembly and decompilation.

Future inventory exports record the corrected seed revision. The comparison
tool rejects mixed seed revisions/analysis modes and duplicate version labels;
a seed-coordinate correction must not become a claimed firmware modification.

Executed originals: callback control, memclr, numeric conversions, filter,
gate/arithmetic/PIO/PWM, period store and the state5 parser slice. Explicit API
stubs: queue builder0x80006778, renderer0x8000326c, printf0x80000544 and creation
API0x80040894. Renderer/queue side effects are not a full live-system model;
notification states1/2 and arbitrary GUI activity are excluded. No physical
device, live UART receive, scheduler clock or acoustic timing was measured.

The next `REFRESH_SIDE_EFFECTS.md` experiment removes the top-level queue and
renderer stubs: original construction/send/copy/critical code and renderer state
helpers preserve the counterexample across2396 checks. Display/text/log leaves
and heap allocation remain models; timed full queues and live scheduling are
not covered.

Next for timing: the inspected FSM prologue has a direct+0x30 reader at
0x800044a8 via ADD-zero alias r1=sb; the older MOV-only tracer missed that alias.
Bound its tick-difference consumers and0x80061f84 before assigning units or
interpreting the Beta3 timeout change.
