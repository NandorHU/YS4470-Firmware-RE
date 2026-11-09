# Admission-to-parse stability and known clear ownership — 2026-11-09

This completes the next bounded check after the original UART correlation
experiment. Both SHA-pinned factory V3.6/V3.8 applications run on the reused
ARM926 harness. No firmware image is changed; no device, USB or network access
is involved in these tests. The prior12,704 transport cases are reused, not rerun.

## What the new execution establishes

Across1,200 cases, a frame already admitted by original state3 remains intact
while the original UART ISR appends data before/during state5 parsing. Each
original has600 cases: two commands, six raw values, two selector bytes, five
tail lengths and five injection positions. Raw values include0,50,699,5000,
5001 and0xffffff; selector0/255; tails0/1/5/195/196. The196-byte tail crosses
the buffer limit. The admitted first five bytes and independently predicted
published value/selector remain unchanged; count caps at200.

Interleaves occur before parsing or at original0x80004738,0x8000473c,
0x80004740 and0x8000476c. CPU context is saved/restored and ISR execution uses
a separate stack, as in the prior explicitly modeled interleaving. This tests
append/read interaction, not actual ARM exception entry or live scheduling.
The expected parser result comes from the earlier independent Python contract.

This rules out an append-only ISR overwriting the admitted prefix **under the
tested valid-count/no-other-writer conditions**. It does not rule out another
task/alias resetting the buffer, corrupt negative counts or a different input
image. It does not repair the earlier same-header stale-response ambiguity.

## Which known callers can clear shared RX state?

The raw ARM BL survey's nine candidates for0x80005f14 all resolve into two
local original-code CFGs:

| Containing function | Known synchronous calls | Scope |
|---|---|---|
| GaugeCmdTask0x80003dbc |0x80003dc4,0x80003dcc| Both occur before loop0x80003dd0 |
| Control-record fallback handler0x80003dd8 |0x80003e2c,0x80003e94,0x80003ea4,0x80003eac,0x80003ec4,0x80003f10,0x80003fe8| Static CFG; role is an analyst label |
| Same fallback handler |**0x8000404c→0x80005f14**| Tail branch, absent from the raw BL-only index |

The extra tail edge is byte-checked in both originals. It is a real local
control-flow edge, not a claim that all callers have been found: Thumb,
indirect calls and function-pointer aliases remain outside the index.

The original service0x80005b6c processes a deferred record through this fallback
only after checking FSM+0x34 idle.24 bounded service cases execute the original
queue-drain control flow, copy and input dispatcher. An empty nonblocking queue
and sleep(1) are models; execution stops at the fallback handler entry, before
its potentially long synchronous operations. Tested record cases are0/1/2/5/6/7,
each idle/busy, on both originals. Busy cases preserve pending and do not enter
the handler. Idle cases2/5 are handled by the original input dispatcher;
idle0/1/6/7 reach the fallback with busy=0 and the expected copied record.

Thus known startup/deferred call sites do not establish a concurrent
synchronous-helper clear during the active GaugeCmdTask acquisition. Do not
turn a shared pointer alone into a claimed live race or add an unproven lock.
The separately indexed0x80005f14 body is identical95-instruction local ARM
context in both originals. Its count literal0x80006090 resolves to0x805ab938.
The body is static evidence here; its full runtime behavior is not newly tested.

## Artifacts and reproduction

- [validation.json](validation.json):1,200 parser/ISR cases,24 service gates,
  representative interleavings, fingerprints, byte-pinned observed addresses,
  caller CFGs and the additional tail branch.
- [synchronous-static.json](synchronous-static.json):95-instruction callee CFG
  per original, calls and count literal; no dynamic helper claim.
- [trace_admission_stability.py](trace_admission_stability.py) and
  [index_synchronous_helper.py](index_synchronous_helper.py): reproducible tools.

From repository root with pinned tools/analysis-requirements.txt installed:

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python"
python -B contributions/COORD-ADC-CADENCE/admission/trace_admission_stability.py
python -B contributions/COORD-ADC-CADENCE/admission/index_synchronous_helper.py
```

Both tools accept --repo and --out-dir for an isolated writable output location.
The coordinator's repository directory was read-only during this heartbeat,
so working artifacts were generated in the allowed isolated workspace and
integrated through GitHub's development-branch API. No permission bypass or
unrelated project modification is needed. Existing model jobs were not retried:
the earlier localhost-service problem remains unresolved, with no new model
answer claimed.

## Next exact question

Trace the fallback handler's actual message producers and other callers before
claiming system-wide ownership. In parallel, a new bounded execution of the
synchronous helper should verify its success/failure, shared-buffer cleanup and
blocking behavior for reachable commands, preserving its caller/idle preconditions.
Keep external conversion restart/buffering, installed firmware identity and
physical Base-versus-profile latency open. No new speed patch is justified by
the append-stability result.
