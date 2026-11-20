# Independent static review: cold palette tail

Scope: existing coordinator-owned COORD-ADC-CADENCE continuation, delegated by
the current coordinator on 2026-11-19. This is not a separate task reservation.

- Branch: `external/review-cold-palette-20261119`.
- Base: `4908c7a598dd48bb5372fa79eed793f2f9cf5542`.
- Target: original V3.6/V3.8 application images from `original-firmware/manifest.json`.
- No native execution, hardware/device operation, previous campaign rerun, shared
  metadata edit or remote publication occurred in this review.

## Established from original bytes

`audit.py` verifies both full input hashes/sizes and decodes 147 identical ARM
instruction words across the relevant caller/getter/wrapper/palette ranges.
`static-audit.json` retains the exact original words, disassembly and full hashes.

At `0x80058f10`, `LDRB [OBJECT+0x20]` and `TST #1` control the branch: zero
takes `0x80058f80`; nonzero skips the palette tail to `0x8005904c`.

| Callsite | Wrapper | Tag | Payload under stable getter value 130 |
|---|---|---|---|
| `0x80058f94` | `0x8003dfac` | `0x44` | `(incoming_R2 & 0xffff0000) \| 0x9cf3` |
| `0x80058fe4` | `0x8003dfec` | `0x40` | `2` |
| `0x80058ff4` | `0x8003dfd4` | `0x45` | `0x7f` |
| `0x80059048` | `0x8003dfc8` | `0x42` | `2` |

The literal at `0x8003ae58` points to palette table `0x80068b3c`; its entry18
is `0x9cf3`. Wrapper `3dfac` explicitly preserves incoming R2 HIGH16, while
the other three wrappers simply move R1 to R2 before selecting their tag.

`0x80025ca4(0)` reads the default display slot at `0x805abd60`, reached from
literal `0x805abd54`. A NULL slot returns 130. A non-NULL slot follows the
driver pointer and returns `(driver_flags >> 7) & 0x3ff`; flags `0x413c`
also yield 130. These two routes must not be conflated merely because the
raw result agrees.

The coordinator separately reported its actual dynamic prefix capture:
default slot is `DISPLAY=0x11001000`, not NULL; incoming R2 at `58f10` is
`0x12018010`. This message is context for the coordinator's continuation,
not an independent dynamic result produced by this static reviewer.

## Arithmetic and signedness

The local metric3 and metric4 calculations use full32 ADD/LSL, a signed
comparison against320 and signed SMULL with `0x66666667`, then signed16
narrowing. On the >=320 branch the default getter is called a second time;
the arithmetic table assumes those getter results remain equal.

- Local metric3: `(130*3+80)/160 = 470/160`, truncated to2.
- Local metric4: `(130*4+80)/160 = 600/160`, truncated to3.
- Final helper `25958(DISPLAY,3)`: `(130*3+80)/160`, truncated to2.

Unlike the local calculations, helper `25958` uses SMULBB, multiplying the
signed low16 halves of its getter result and input. It first tests the full32
input for zero. Thus input `0` returns0, while input `0x10000` is nonzero yet
has a zero low16 operand and yields the minimum1 branch. No physical unit is
assigned to these raw values.

Starting with the existing count3 style, all four new distinct tags use
realloc, never the count1 allocator. All-success requested sizes are24/30/36/42.
Expected all-success tags are `b,21,20,44,40,45,42`; payloads are
`13,ff,1201e71c,12019cf3,2,7f,2` when the incoming opaque high16 is1201.
Summary becomes `0x15` and count7. For final pointer `0x1201c000`, style bytes
are `00c001120b001507`. These are continuation reference expectations, not
claims that this reviewer executed the 16 outcome schedules.

## Reproduce

Add the existing project-local Capstone dependency directory to PYTHONPATH,
then run from this isolated checkout:

```powershell
python contributions/COORD-ADC-CADENCE/parallel-20261119/static-review/audit.py
```

Observed output: 147 equal original instruction words, tags44/40/45/42,
conditional raw values `opaque-high16|9cf3,2,127,2`. The audit also checks the
signed16/full32-zero distinction above.

The coordinator must still validate all dynamic getter inputs/results,
allocation outcomes, complete memory/guard/SP references, and raw R2 dataflow.
Allocator/free/reuse semantics, the complete initializer, roots, callbacks and
physical timing remain open.
