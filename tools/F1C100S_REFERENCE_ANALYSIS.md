# Reference-assisted analysis

Inputs are the four exact upstream revisions under `references/f1c100s` and the
SHA-256-pinned original V3.6/V3.8 images. No firmware is downloaded to a device.
The current run is the first integration, not a completed SoC/firmware map.

## What actually runs

`analyze_f1c100s_references.py` verifies clean pinned checkouts, inventories
licenses and selected source hashes, extracts register definitions, compiles five
driver C files into ARM926 little-endian ARM ELF objects, reads function symbols
and relocations, and compares those bodies with the originals. It also compares
eight existing `F1C100s_info/LIB_RE` objects, explicitly identified as upstream
prebuilt SDK artifacts rather than fresh builds.

Compiler: project-local Zig0.13.0 / Clang, target arm-freestanding-eabi,
CPU arm926ej_s, ARM mode, O2, freestanding, no builtin calls. GCC was absent from
PATH. The chosen compiler does not reproduce an unknown factory compiler. It
is a reproducible source-pattern baseline, not a byte-identical factory build.
Build reports include compiler/source/object hashes. Source is not copied into
the reconstructed firmware. Tools/dependencies: Capstone, pyelftools0.32,
Unicorn2.1.4; existing Ghidra12.1.4/PyGhidra3.1.0 remains in use.

The bounded ARM survey covers linked0x80000000..0x80063800. It records PC-relative
literal loads into mapped peripheral blocks, propagates known constants for up
to12 straight-line instructions, stops at control transfers and invalidates
clobbered registers. Conditional paths and decoded embedded data remain
candidates. It does not silently claim complete Thumb/indirect-call coverage.

Full-body comparison masks relocation words conservatively and records them for
later verification. A normalized ARM instruction comparison is only a ranking
aid: branch targets and PC-relative displacements need separate resolution.
Names, function lengths, short prologues and a shared peripheral base alone do
not prove identity. The initial originals yielded no new full-body or accepted
normalized function candidates among97 eligible reference functions per image.

The reference register map also led to two bounded original-code experiments:
0x800085c4 reads/writes WDG_CTRL with old|0x14af; 0x800085e0 updates WDG_MODE with
old|1. Each helper passes eight seeded register values per original (32 total).
These are inert RAM shadows; watchdog reset/feed timing is not simulated.

## Outputs and observed results

- `references/f1c100s/sources.lock.json`: four revisions, licenses and selected file hashes.
- `references/f1c100s/register-map.json`:34 bases,361 literal register-enum entries,428 annotated-offset claims.
- `evidence/2026-11-07-f1c100s-reference/reference-analysis.json`: build hashes, candidates, watchdog experiments and proof-gated labels.
- Per original:142 MMIO-literal leads,129 following access candidates,10 CP15 leads,11,914 aligned ARM BL candidates and1,004 target candidates.
- `V3.6/V3.8-call-candidates.json.gz`: deterministic gzip of the full linear candidate-edge graph, with uncompressed SHA-256 in the report. This is not a validated function call graph.
- `pyghidra-reference-validation.json`: real PyGhidra labels/assembly/decompilation for the six proof-backed entries per original and automated validation results.

The direct-code survey results agree across originals. This does not turn the
unchanged nearby data into a known role or prove whole-firmware equivalence.

## Ghidra integration and name preservation

The existing `pyghidra_inventory.py` accepts `--reference-report`. The helper
`reference_ghidra_labels.py` checks version/image hash, exact guarded bytes,
independent execution proof and explicit RE_ analysis names. Candidate matches
never authorize a label. Existing USER_DEFINED, IMPORTED and ANALYSIS names are
preserved. Existing comments are retained and an evidence marker is appended
once. It does not create a second function inside an existing body.

Real Ghidra runs export six proof-backed entries, including the new watchdog
helpers. SoundControlGate retains its prior name. These are new local disposable
projects; the export is the durable repository artifact. No claim is made that
another analyst's existing Ghidra project was modified or saved. Ghidra inferred
function-body limits are reported separately from emulation proof scope.

## Reproduce

```powershell
./tools/fetch_f1c100s_references.ps1
python -m pip install --target work/analysis-python -r tools/analysis-requirements.txt
python -m pip install --target work/reference-compiler --no-deps ziglang==0.13.0
$env:PYTHONPATH = "$PWD\work\analysis-python"
python tools/analyze_f1c100s_references.py `
  --references references/f1c100s --zig work/reference-compiler/ziglang/zig.exe `
  --input 'V3.6=<original path>' --input 'V3.8=<original path>' `
  --sound-evidence evidence/2026-11-07-sound-pwm-path.json `
  --out-dir work/reference-output
$env:PYTHONPATH = "$PWD\work\analysis-python;$PWD\tools"
python -m unittest discover -s tools -p test_reference_pipeline.py -v
```

Pass the generated `reference-analysis.json` to the existing inventory's
`--reference-report`, using its existing `--ghidra`, `--input` and `--out-dir`
arguments and the project's PyGhidra/JDK paths. `open_program()` works on the
installed version but emits a deprecation warning; API migration is deferred.
On this Windows sandbox, Zig's child-process temporary-file handling required
unsandboxed local compilation after cache relocation alone failed. Compilation
and analysis write only into the selected workspace output/cache directories.

Continuation: the INTC/timer leads have since been verified by4446 original-code
cases and five real Ghidra exports per original; see `INTC_TIMER_PATH.md`.
Fast CONT helper0x80007c88 has also been reconstructed as a freestanding C
component, agreeing with original ARM/Python in3958 state steps; see
`FAST_CONT_FILTER.md`. These are semantic/bounded proofs, not newly found whole
reference-function byte identities. The original reference-match counts above
remain unchanged.

The existing inventory now accepts these proof reports and `--labels-only`,
which exports their guarded entries without repeating the13-seed baseline.
Next: fresh-result admission and tick/scheduler consumers; resolved relocation
targets and wider Thumb matching remain pending. No full firmware image has
been reconstructed or physically installed by this workflow.
