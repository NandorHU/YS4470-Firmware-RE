# Cached FSM deadline and tick snapshot proof

This completes the coordinator's COORD-FSM-TIMEOUT reservation. The original
V3.6/V3.8 instructions run on an explicit Unicorn ARM926. An independent Python
specification and independently compiled C execute separately for timed
states 2/3/4. No physical device, live scheduler or waveform is used.

## Established contract

FSM root is 0x805ac694. Entry 0x80004490 loads +0x2c (start) and +0x30
(duration); 0x800044a8 caches duration in R5. Each timed branch moves the cached
start into R4 across the real tick getter, then checks unsigned 32-bit
(now - start) >= duration. Equality expires. This is a duration comparison,
not a per-call decrement.

| Branch | Tested behavior |
|---|---|
| State 2: no positive count / wrong expected header | Before duration retain2; on expiry set6 |
| State 2: accepted header, command IDs9..15 | New start snapshot; duration100 for13/14 or50 otherwise; state4 |
| State 2: accepted header, other tested selectors | Clear PIO bits3 then2; increment index modulo32, clear retry; state1 |
| State 3: required signed length greater than RX count | Before duration retain3; on expiry set6 |
| State 3: sufficient count | 0x1b requires header0x5e, 0x1d requires0x60; match admits5, mismatch selects6; other tested selectors admit5 |
| State 4 | Before duration retain4; on expiry clear PIO bits3/2, increment index, clear retry, state1 |

State3's complete-frame branch never calls the tick getter. A valid completed
reply can be admitted even when the old time budget has elapsed; a larger
budget does not impose a fixed extra wait on all replies.

Original state1 setup executes from the real FSM entry, clears RX state with
the original memclr and critical helpers, calls a modeled UART-send leaf,
then takes the real tick snapshot. Commands0x1b/0x1d set required5, duration30,
state3; the other tested commands9..15 set an expected header and duration80,
state2. Timestamp means after the send call returns, not measured wire start.

## Real counter access and bounded prefix

Getter 0x80061f84..0x80061fa0 exclusive calls the original critical enter/exit
and returns root0x805abbbc +0xc =0x805abbc8. Every observed read occurs with
IRQ masked and nesting incremented; valid initial nesting0/1/2/7 is restored.

The tick prefix at0x80061fa4 increments this word modulo32 on the unsuspended
path. That experiment stops at0x80061fe8, before counter-wrap list handling.
The tested suspended early-return branch increments root+0x18 and leaves the
main counter unchanged. This is not a complete tick, task-ready or scheduler
model and does not establish clock frequency.

GPIO clear/set instructions also execute, against inert RAM at0x01c208c4.
They establish register-bit effects only; no new physical pin/analog role is
inferred.

## Validation

Per original:

- 3,825 timeout-boundary cases: states2/3/4, 12 durations including0 and32-bit
  extremes, five starts including wrap, three valid critical nesting levels.
- 2,560 admission/header/completion cases.
- 72 signed-length and command-index wrap cases.
- Those 6,457 cases compare original ARM, Python and separately executed
  compiled C, including all semantic output fields and requested effects.
- 20 direct getter cases, 10 tick-prefix cases, 108 original transmit-setup
  cases, 48 explicit cache interventions and eight budget30/40 comparisons.

Both originals total 13,302 checks, of which12,914 are three-way differential
cases. Both produce fingerprint
22212642cf8e42e7be6b1829508a6dc593a116be5f6298b63707f4911f5accfe.
The report records instruction-address coverage separately from case counts;
neither is a whole-firmware coverage percentage. Nine existing provenance
tests pass; four actual Ghidra assembly/decompiler exports are in the companion
JSON. New disposable projects do not alter another analyst's saved project.

At start0xfffffff0, now0x0d gives elapsed29 and remains waiting; now0x0e gives30
and expires at budget30. Tests also cover unsigned 0x7fffffff/0x80000000 and
0xffffffff budgets. A complete 2^32 cycle is inherently indistinguishable from
zero elapsed with this counter alone.

The cache probes deliberately change RAM start/duration at getter entry.
The current comparison still uses the earlier R4/R5 snapshots. This is an
explicit host intervention, not evidence that such a concurrent writer exists.

A synthetic duration40 comparison retains state3 at elapsed30/39 where
duration30 selects6; both expire at40. This explains a hypothetical duration
change as a grace-window change for incomplete replies. No actual Beta3 image
is executed by this runner.

## Independent C component and reproduction

reconstruction/fsm_timeout.c/.h are a semantic component for states2/3/4,
not a binary-compatible in-RAM struct or a complete firmware. uint32_t fields
preserve wrap; signed length uses the ARM target's int32_t interpretation.
The returned effect bits describe the original path's tick read/GPIO request;
the pure function performs neither hardware access nor critical operations.
Original code, Python and compiled C run in separate execution paths.

From repository root, with pinned analysis dependencies installed:


```powershell
New-Item -ItemType Directory -Path work/fsm-timeout -Force | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR="$PWD\work\fsm-timeout\cache"
$env:ZIG_LOCAL_CACHE_DIR="$PWD\work\fsm-timeout\local-cache"
./work/reference-compiler/ziglang/zig.exe cc -target arm-freestanding-eabi -mcpu=arm926ej_s -marm -O2 -ffreestanding -fno-builtin -ffunction-sections -std=c11 -Wall -Wextra -Werror -c reconstruction/fsm_timeout.c -o work/fsm-timeout/fsm_timeout.o
$env:PYTHONPATH="$PWD\work\analysis-python;$PWD\tools"
python -B contributions/COORD-FSM-TIMEOUT/trace_fsm_timeout.py --input 'V3.6=original-firmware/V3.6/f1c100s.bin' --input 'V3.8=original-firmware/V3.8/f1c100s.bin' --reconstruction-object work/fsm-timeout/fsm_timeout.o --out contributions/COORD-FSM-TIMEOUT/fsm-timeout.json
python -B -m unittest discover -s tools -p test_reference_pipeline.py -v
```

Compiler: existing Zig0.13.0 / Clang, ARM926 ARM mode. The loader checks that the
C function section has no relocations. Source/header/object SHA-256 values are
recorded. No compiler, dependency or firmware is installed on the instrument.

For Ghidra, use the existing tools/pyghidra_inventory.py with --labels-only,
--reference-report contributions/COORD-FSM-TIMEOUT/fsm-timeout.json, both input
arguments, the installed Ghidra12.1.4 and a new output directory. The existing
guarded label pipeline preserves names/comments; its new schema is explicitly
tested. Create any dedicated Java user-home directory before launch. The first
launch lacked it and failed before project import; the corrected invocation
exported both images. open_program() still emits its existing deprecation warning.

## Explicit limits and continuation

Only UART send0x80005e84 is a leaf model in state1; physical completion/arrival
timing remains unknown. State6 retry handling, other FSM states, full RTOS
wrap/ready lists and real task cadence are outside this experiment.
Synthetic signed/extreme count fixtures describe the code's arithmetic; they
do not imply physically reachable buffer lengths. Linear Capstone windows
contain jump-table data; only the recorded visited set is execution coverage.

No milliseconds, buzzer latency or actual modified-image behavior is claimed.
Next reserved work is COORD-ADC-CADENCE: validate the MainADCTask candidate and
actual FSM caller/delay loop before deriving raw tick cadence.
