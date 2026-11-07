# Refresh queue and renderer: fewer modeled boundaries

This experiment continues the stored-result test in `RESULT_FRESHNESS.md`.
The original event builder, queue-send/copy path, critical sections, renderer
control and renderer state helpers now execute instead of the two top-level
queue/renderer stubs. Widget/text/logging leaves and the heap allocator remain
explicit models. No physical device or live scheduler is used.

## Original entry points

| Entry | Behavior established in the tested scope |
|---|---|
| 0x800029dc | Requests a queue with arguments(10,68,0), stores returned handle at0x805aae90, including null result. |
| 0x80061838 | Original constructor allocates0x50+length*itemsize, fills queue fields and initializes empty waiting lists; allocation return is modeled. |
| 0x80006778 | Builds the68-byte event record and sends to the queue. Event3 uses wait0; other tested events use wait10. Null handle returns early. |
| 0x80061acc | With room, copies an item, advances/wraps write pointer, increments count and returns1; full wait0 returns0. |
| 0x8000326c | Renderer control and state helpers execute across the stated matrix without modifying protected freshness/filter state. |
| 0x80060efc | Masks guest IRQ via CPSR bit7 and increments nesting word0x805abbf8. |
| 0x80060f20 | Decrements nesting; enables guest IRQ when nesting reaches0. |

The constructor's original list initializer0x80060e48 and memcpy0x800009c4 also
execute. The factory caller requests10 items of68 bytes; total modeled
allocation is760 bytes. The linked example uses a queue constructed by original
code, not merely a host-filled substitute. The allocator supplies a synthetic
address or null; the real heap algorithm is not executed.

## Queue data contract

Constructor stores and actual send behavior establish these object offsets:

| Offset | Observed role |
|---|---|
| +0/+4 | data start/end pointers |
| +8/+0xc | write/read-side pointer fields |
| +0x10/+0x24 | waiting-list counts/heads |
| +0x38 | occupied item count |
| +0x3c/+0x40 | capacity/item size |
| +0x44/+0x45 | signed lock bytes initialized to-1 |
| +0x4c | constructor's type byte |
| +0x50 | first payload byte in the constructor's contiguous allocation |

Generic circular-buffer probes use capacities1..3, available positions/counts
and full zero-wait rejection. The main linked queue uses the factory arguments.
No waiting task is present, so no task wakeup/context switch is required. Timed
full-queue waits, overwrite modes, semaphores and asynchronous consumers remain
outside the proof. A successful send records a request; it does not wait for a
measurement response. The wait argument10 is not assigned a physical time unit.

## Renderer/state scope

The1152 states per original vary mode0/1/3/4, UI byte+3, record flag+0x40,
matching/mismatched saved mode, UI+0xe state, UI+0x12 countdown0/1/8, refresh
warmup0/2/255, and cold/full auxiliary histories. These raw flags are not given
unproven user-visible option names.

Original helpers0x8000406c/4114/425c/4290/4314 and0x80002e44 execute, including
the exercised four/eight-value history paths and numeric callees. Their storage
includes two64-byte memo buffers at0x80d46fb8/0x80d46ff8, a four-word history
at0x80d47038 and an eight-word history at0x80d47048. These are distinct from the
Fast CONT history at0x805ac7b8. Valid ring/count fixtures are used.

Every queue/renderer write is guarded against overlap with UI warmup+9, parser
discard+1, the raw result/selector, Fast CONT active/index/count/median/history
and RX buffer. Before/after snapshots independently check preservation. The
renderer may change its own display state and auxiliary histories. The tests
do not establish complete visual behavior or semantics of every state helper.

Remaining leaf models: record text0x80003c5c, widget text0x80032038, display
format0x80045184, bounded string copy0x80000578, log enqueue0x800616e4,
printf0x80000544 and heap allocation0x80042aa0. Their host writes are bounded
formatting/allocation contracts. Arbitrary GUI events and log-consumer side
effects are not modeled. The refresh handle/period remains synthetic as in the
preceding test; its timing contract is still open.

## Linked result and validation

Five original callback invocations put five event4 records (prefix040000000000)
into the original-code-constructed queue. No parser entry occurs and discard
count remains2. Filter fills remain[0,0,1,2,3]; the final retained value is5 and
the emulated sound active flag becomes1. The stored raw result remains14023.
The renderer core does not add a freshness gate on these tested paths.

Per original:36 queue cases,1152 renderer states,3 valid critical nesting cases,
2 constructor outcomes and5 linked callbacks:1198 checks. Across both
originals:2396 checks, identical fingerprints and zero failures. Coverage
records include244 renderer,275 helper and52 send-path instruction addresses;
these are observed address sets, not a whole-firmware coverage percentage.
Real Ghidra exports all seven proof-labelled entries for both originals. Nine
label/provenance tests pass.

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python;$PWD\tools"
python tools/trace_refresh_side_effects.py `
  --input 'V3.6=<original path>' --input 'V3.8=<original path>' `
  --out evidence/2026-11-07-refresh-side-effects.json
```

Evidence: `evidence/2026-11-07-refresh-side-effects.json` and
`evidence/2026-11-07-refresh-side-effects-ghidra.json`.

Next: bound the FSM+0x30 reader at0x800044a8, its cached R5 elapsed-tick
comparisons and real tick getter0x80061f84, reusing the verified critical
helpers. Queue blocking/waiter paths and remaining GUI/log leaves stay separate
unfinished work. No callback period, timeout or acoustic delay is assigned
milliseconds by this experiment.
