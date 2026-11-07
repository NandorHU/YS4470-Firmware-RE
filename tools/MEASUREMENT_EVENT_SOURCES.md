# GUI to measurement-event sources

The original code links the previously unnamed event pipeline to Diode/Buzzer
GUI labels. This is static UI naming plus bounded execution, not an analog
measurement or audible-latency validation.

## Evidence chain

1. Label assignment calls place Diode/Buzzer literals at GUI root
   0x805ac098 fields +0x2c0/+0x2c4. The literals live at 0x80051940/0x80051948.
2. Callback registration at 0x80051894..0x800518a4 supplies callback
   0x8000cfd0 on root field +0x2b8 with event argument 1 and user data 0.
3. That callback manipulates these label objects and constructs the same
   event tuples as selection API candidate 0x80044e54.
4. The Diode-side tail sends (2,0x0e,0x19). On the Buzzer side word
   0x805ac788 == 1 selects (5,0x22,0x13); other tested values select the
   first tuple. The setting name is unresolved.
5. Event builder 0x80006778 forms a record and reaches 0x80061acc. The
   captured record is passed to the existing dispatcher/parser harness.
   Both paths initialize a discard count of 2.

## Boundary contracts

The builder reads the opaque handle at control object +4. With handle zero it
returns without calling the queue boundary. Otherwise r0 becomes record u32 +0
and low8(r1/r2) become bytes +4/+5. Its 0x44-byte stack frame has no additional
initialization after byte 5 in the test. Queue-boundary r2 is 0 for exact
event word 3, otherwise 10; r3 is 0. No time unit or RTOS identity is inferred.

GUI tests execute only the recorded label/registration, mode switch, and
event-tail slices. All GUI API, queue, TransactionBuilder and common parser
epilogue calls remain outside execution. The pipeline bridges API boundaries
using observed arguments; it does not emulate their implementations.

The whole-image scan finds 31 aligned direct ARM BL candidates to the builder
in each original. These are not exhaustive Thumb/indirect-call results.
Per-word disassembly includes data, literal pools and jump tables; only the
bounded execution paths are verified code.

## Run

Install the project's pinned analysis-requirements.txt and use the same
isolated Python path as the other ARM tests:

~~~powershell
$env:PYTHONPATH = "$PWD\work\analysis-python"
python tools/trace_measurement_event_sources.py `
  --input 'V3.6=<original V3.6 image>' `
  --input 'V3.8=<original V3.8 image>' `
  --out evidence/measurement-event-sources.json
~~~

Per original: 450 builder cases, 32 GUI branches, 48 linked parser entries,
six label/registration slices and nine mode-switch cases. There are zero
failures and equal result fingerprints across original V3.6/V3.8. The saved
experiment was created on 2026-11-06 and re-verified read-only on 2026-11-07.

Next: identify the writers/defaults/storage and GUI name for word 0x805ac788.
