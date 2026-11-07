# Fast CONT history, retained median and sound request

Original helper0x80007c88 executes with a three-value ring at0x805ac7b8.
State at0x805ab924 shares its first word with the separately verified sound
active flag: +4 ring index, +8 sample count, +0xc retained median.

For signed input>1000, it resets count to0, all history slots to1000 and retained
median to-1, but leaves the ring index unchanged. It then inserts that input,
advances the valid ring index modulo3, and raises count to at most3.

With a full history, it computes signed min/max and compares the unsigned64-bit
representations of min*120 and max*100. This corresponds to SMULL, SUBS/SBCS and
the carry condition. For ordinary nonnegative values this admits max<=1.2*min.
A signed64 comparison would produce different mixed-sign behavior and is not
substituted in the reconstruction.

When the condition passes, the median-of-three replaces the stored median.
**When it fails, the previous median remains in use.** Every helper call then
requests sound from the stored median, including calls before a new full/stable
history. This is not an elapsed-time timeout or a guarantee of fresh samples.

Table0x8006397c has11 rows, lower inclusive and upper exclusive:

| Retained value | Selector |
|---|---|
| 0..19 | 10 |
| 20..39 | 8 |
| 40..59 | 6 |
| 60..79 | 4 |
| 80..99 | 2 |
| 100..999, negative or unmatched | off(0,0) |

Original rows split each20-wide band into two10-wide rows. The helper tailcalls
SoundControlGate(selector,1) or SoundControlGate(0,0). The settings enable check,
active flag, duty conversion, pinmux and PWM behavior are executed through the
existing validated original-code harness, not replaced by the Python model.

## What the persistent tests establish

- A valid count0 state requires three helper inputs before its first median
  recalculation; an earlier retained value can still drive sound before then.
  The harness's history1000/median-1 start is explicit test input, not a proven
  factory power-on initialization.
- After stable[5,5,5], the first two500 inputs retain median5/selector10;
  the third500 establishes median500 and requests off.
- After stable5, input1001 resets the median immediately and requests off.
- Input1000 follows the ordinary ring path rather than the >1000 reset.
- Alternating500/5 retains the previous tone through the tested16 unstable
  inputs. The helper contains no independent expiry of the retained median.

The argument's physical unit and helper-call cadence remain unresolved. These
are sample/call-count findings, not measured milliseconds or acoustic behavior.
The preceding parser's two-discard lifecycle is a separate proof; its latency
must not simply be added without linking fresh replies to helper invocations.

## Independent C reconstruction and checks

`reconstruction/fast_cont.c` is a pure component with explicit valid-state
contract. It is independently written from these proven behaviors; it contains
no reference-project driver code. It compiles without board libraries into an
ARM926 object. The original ARM helper, independent Python oracle and compiled
C execute separately and must agree after every input on all history/state
fields and requested selector. Original execution additionally validates the
complete gate/PWM effects on inert shadows.

Evidence: `evidence/2026-11-07-fast-cont-filter.json`; runner:
`tools/trace_fast_cont_filter.py`. Source/header/object SHA-256 and build flags
are recorded. Detailed counts are generated in the report; no full-device
emulation or firmware equivalence is asserted.

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python;$PWD\tools"
python tools/trace_fast_cont_filter.py `
  --input 'V3.6=<original path>' --input 'V3.8=<original path>' `
  --reconstruction-object work/derived/fast_cont.o `
  --out evidence/2026-11-07-fast-cont-filter.json
```

## Caller contract established in the next bounded experiment

`RESULT_FRESHNESS.md` and `evidence/2026-11-07-result-freshness.json` establish
that ResultDispatch accepts only integer0..999 into this helper. A sentinel or
scaled value>=1000 bypasses the helper and requests off while retaining its
history/median. Thus the standalone>1000 reset above exists, but is not reached
through that caller's accepted-value branch.

The bounded refresh model also refills the ring from one unchanged stored
result without a parser entry. Its three filter calls do not imply three new
UART samples. Queue/renderer/printf/creation APIs are explicit stubs there;
factory power-on state, live cadence and acoustic behavior remain open.

The renderer/queue-core audit is now in `REFRESH_SIDE_EFFECTS.md`: original
constructor, send/copy, critical and renderer state code preserve the repeated
stored-result example. Low-level graphics/text/log models and blocking queues
remain separate. Next: bound tick/timeout consumers before assigning time units.
