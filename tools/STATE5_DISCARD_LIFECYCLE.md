# State-5 sample-discard countdown producers

This extends the bounded ARM926 parser experiment with the original input
dispatcher, preserving control/result RAM across subsequent parser entries.
Both verified originals, V3.6 and V3.8, produce identical results.

## Proven producers

The input record passed in r0 is read as a word at +0, a configuration byte
at +4, and a secondary byte at +5. The following are software case values,
not identified physical measurement modes.

| Input case | Control +8 | Control +1 | Command words passed to TransactionBuilder |
|---|---|---|---|
| 2 | record byte +4 | 2 | [record[4], normalize(record[5]), 0x1d] |
| 5 | 0x22 | 2 | [0x0c, 0x22, 0x13, 0x1d] |
| 3 | unchanged | unchanged | [0x1d] |
| 4 | unchanged | unchanged | [0x1b] |

Normalization retains secondary values 0x13..0x18 inclusive and substitutes
0x19 for every other byte. The count=2 assignments are at 0x800043ec and
0x80004468, using r12 initialized to 2 at 0x800043cc. Control is rooted at
0x805aae8c, so its discard byte is 0x805aae8d.

## Persistent parser effect

For cases 2 and 5, retain the producer's RAM and execute the original
state-5 slice once for each synthetic, already admitted response:

| Parser entry | Counter before | Counter after | Result publication |
|---|---:|---:|---|
| first | 2 | 1 | previous result/selector retained |
| second | 1 | 0 | previous result/selector retained |
| third | 0 | 0 | parsed value or saturation sentinel published |
| fourth | 0 | 0 | next parsed value or saturation sentinel published |

This proves a count of accepted state-5 responses. It does not establish a
millisecond delay, UART polling period, settling purpose, or physical mode.

## Task routing and false-positive correction

At the task selection block 0x80005bb8, only input cases 3 and 4 reach the
immediate branch at 0x80005be4. Other cases reach the deferred-copy call at
0x80005bd4. When FSM object +0x34 is zero and control byte +0 is nonzero,
the later code at 0x80005cd8..0x80005cf4 copies the deferred record, clears
the flag, and calls the input dispatcher. These latter conditions are
static observations; queue scheduling and the memory-copy helper are not
emulated in this experiment.

Consequently the duplicate case-2/case-5 stores at 0x80005c60/0x80005c80
are not reached through the normal task-selection guard in the tested
entry path. This corrects any interpretation of those static blocks as
proof of ordinary immediate execution. Alternate entry points remain open.

The old linear literal tracer also suggests 0x80005e60 as a +1 write after
an earlier r4 load. That candidate is rejected: 0x80005e50 reloads r4 with a
different UART startup buffer pointer before the write. The tracer is a
candidate finder, not complete register or alias tracking.

## Reproduce

```powershell
$env:PYTHONPATH = "$PWD\work\analysis-python"
python work/re_tools/trace_state5_discard_lifecycle.py `
  --input 'V3.6=<original V3.6 image path>' `
  --input 'V3.8=<original V3.8 image path>' `
  --out evidence/state5-discard-lifecycle.json
```

Per version the harness checks 592 producer inputs, 48 persistent-RAM
scenarios with four parser entries each, and eight task guard cases.
It stops before TransactionBuilder and before the shared parser epilogue.
No queue, UART, ADC, MMIO, or physical device is modeled or accessed.
