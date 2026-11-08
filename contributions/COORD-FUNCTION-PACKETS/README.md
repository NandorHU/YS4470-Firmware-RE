# Original-hash-bound function packets and resumable local drafts

I first repaired completion handling, then exported and checked three whole
local function bodies from each published original image on2026-11-08.
I did not modify the old31-task batch or write to a device.

## Results and scope

| Entry | Packet label | Original instructions | CFG blocks |
|---|---|---:|---:|
| `0x80003dbc` | GaugeCmdTask: static task-name argument binding |7|2|
| `0x80006e4c` | SoundControlGate: prior bounded execution |42|6|
| `0x8005d048` | MeasurementRefreshCallback: prior bounded execution |131|16|

Each row has separate V3.6/V3.8 packets, keyed by the full original SHA-256.
`packet-index.json` pins all six packet files. Ghidra12.1.4/PyGhidra3.1.0
exports contain original bytes, ARM mode, full local CFG assembly, decompiled C,
blocks/edges, call targets, unresolved indirect calls, literal pools, memory
offsets, candidate globals and explicitly limited caller matches.

I reused the existing original-image projects under
`work/fsm-timeout/ghidra/ghidra-projects/`. I checked the entire mapped image
against its original before exporting. Temporary function-body edits are rolled
back; names/comments are read and retained. No broad analysis or rename runs.
Cache keys include firmware, exporter and source-project fingerprints. A second
unchanged invocation returned six cache hits without re-exporting functions.

`complete_local_cfg` means all locally reachable instructions under the documented
ARM/direct-flow/stack-return rules, not transitive callees or all dynamically
feasible paths. Unresolved indirect jumps cause export refusal. Raw BL scans
are caller **candidates**, because data can decode as BL. Constant propagation
is conservative and block-local; unresolved bases/offsets remain in the packet.
Global-reader/writer searches cover these six packets only. Decompiler text is
an aid, not independent proof. No full program map is claimed.

`validation.json` records360 instruction-byte checks,388 CFG edges and four
bounded original ARM926 executions. Independent fixtures cover signed host
representations of high ARM branch addresses, conditional returns and unresolved
indirect branches. The first exporter prototype missed high-address targets;
the new negative/control fixture caught this before any packet was accepted.

At original `0x80005948..0x80005954`, execution reaches the call at
`0x80005958` with R0=`0x80003dbc` and R1=`0x80005a10` → `GaugeCmdTask\0`.
The task entry executes setup call `0x80005d24`, command calls with9 then19,
and repeats call `0x80005b6c` via the back edge at`0x80003dd4`.
The creation callee is not run; the three task callees are return-only models.
This proves the name-argument binding and bounded outer-loop control flow,
not command completion, RTOS timing, MainADCTask identity or acoustic speed.
Function bodies match between originals; changed global data remains separate.

## Completion, checkpoints and actual local comparison

`completion_gate.py` accepts only done=true, done_reason=stop, JSON-object
responses without tool calls. `length`, missing/unknown finish reasons and
valid-but-cutoff JSON stay incomplete. Completed transport yields a **draft**,
never a verified finding. Atomic per-attempt files/checkpoints and a running
lock support resume. At most two attempts and120s per invocation are allowed;
exhausted tasks require a newly reviewed smaller scope. Frozen old jobs are
not automatically requeued. Thirteen regression tests passed, including
length→stop, two cutoffs and resume without new calls.

The offline legacy audit found22 incomplete replies out of31 and left every
old file unchanged. Nine transport-complete Markdown replies remain unreviewed;
they are not validated JSON or firmware proof.

I ran six new questions on the existing qwen2.5-coder:14b with checked
`LESSONS.md`, comparing first-eight-instruction windows to full function views.
The complete views verified3/3 requested original instructions; the short
windows verified1/3. Two requested instructions were absent from the short
windows by design. This demonstrates context coverage, not general model skill.

The first quote gate expected assembly-only while the model quoted exact
address+assembly lines. I corrected that gate and revalidated saved responses
offline, retaining original attempts and appending hash-bound coordinator
reviews. The recorded12 calls include retries from that gate mistake:
17.344s for short windows and17.250s for full views. These are not a fair
steady-state speed comparison. See `comparison-review.json` and the frozen
comparison manifest/results. A resume made zero new model calls, retained four
bounded verified answers, and left two context-insufficient tasks at needs_split.

`model-inventory.json` records the model digest. The Ollama ps observation
reported8192 context and9,539,042,671 bytes both model size and size_vram.
This is an API placement report, not independent GPU instrumentation.

## Reproduction and lookup

Prerequisite: the two unchanged published originals and the existing original
PyGhidra projects created by `tools/pyghidra_inventory.py --labels-only
--reference-report contributions/COORD-FSM-TIMEOUT/fsm-timeout.json` with
`--out-dir work/fsm-timeout/ghidra` and both VERSION=PATH inputs. This importer
sets link base0x7fffffe0. Do not substitute a modified mapped program.

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python;$PWD\work\pyghidra-python;<ghidra>\Ghidra\Features\PyGhidra\pypkg\src"
$env:JAVA_HOME='<existing-jdk21>'
$env:JAVA_TOOL_OPTIONS="-Duser.home=$PWD\work\ghidra-profile"
$env:APPDATA="$PWD\work\ghidra-profile\AppData\Roaming"
python -B contributions/COORD-FUNCTION-PACKETS/export_packets.py --ghidra '<existing-ghidra>'
python -B contributions/COORD-FUNCTION-PACKETS/validate_packets.py
python -B -m unittest discover -s contributions/COORD-FUNCTION-PACKETS -p 'test_*.py' -v
python -B contributions/COORD-FUNCTION-PACKETS/evidence_index.py --db work/function-packets/new-index.sqlite --build
```

The SQLite/FTS5 index is generated locally, not a committed binary. It has six
function rows,360 instructions,114 typed relation rows and six FTS documents.
Same-address/different-hash and FTS tests passed. All queries require an explicit
`--hash`; add `--address` for call/global edges or `--search` for FTS text.
Relations are separate from FTS and retain candidate status. Results trace to
source packet paths/hashes and JSON instruction indices, without invented lines.

`packet_worker.py --job <new-owned-job>` requires a frozen manifest pinning
packet hashes, binary hashes and checked lessons. It sends complete assembly,
decompiler text and relevant relations, omitting duplicated CFG JSON to fit
the8192-token context. It has no shell, Git, device or model-code executor.
Never run `prepare_comparison.py` again on the completed comparison.

Next: reuse these packets/index for coordinator-reserved COORD-ADC-CADENCE.
GaugeCmdTask calls the still-candidate service at0x80005b6c; trace its FSM/delay
placement independently. Base+highspeedv2's perceived physical advantage remains
unproven. Additional heavyweight emulators, embeddings and weight training were
unnecessary for this task and were not installed.
