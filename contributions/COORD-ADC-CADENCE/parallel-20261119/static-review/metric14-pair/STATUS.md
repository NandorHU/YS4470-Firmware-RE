# Fresh static audit: STATE metric14 pair

Delegated continuation under COORD-ADC-CADENCE, 2026-11-19. Only this new
subfolder is changed; the preceding palette-tail audit remains untouched.
Base branch commit before this review: `0b46a2c81749bc7a8227145f62146009aeac5345`.

Both original V3.6/V3.8 hashes and sizes are verified against the manifest.
Fresh caller/stub/wrapper/helper ranges decode identically; exact bytes are in
`static-audit.json`. This review executes no firmware and repeats no campaign.

## Confirmed byte-level dataflow

- `590a8` reads byte `[R4+1]`. With the coordinator's R4=STATE binding and
  cold byte1=1, `590b0` takes BEQ to stub`59c60`, which invokes
  `25958(DISPLAY,14)` and rejoins at`590c8`.
- Byte1=2 takes argument12; all other byte values take argument10.
  The LDR at`590b8` does not change the flags selecting MOVEQ/MOVNE.
- `590c8` caches the metric result in R9. Both setters receive that same
  cached result, assuming the native setter preserves R9 as expected.
- First setter`3ddd8` selects **tag10**, then falls through to`3dde4`.
  Second setter`3dd9c` selects **tag11**, then branches to`3dde4`.
  Both copy full R1 into R2 without adding another value conversion.
- Stop`590e4` is before the metric5 call. The following `590ec` call uses
  argument5; its wrapper`3dda8` at callsite`590fc` selects **tag15**.

## Arithmetic and references

For stable getter130, metric14 is `(130*14+80)//160=11`; the pair rawvalues
are `[11,11]`. Alternate selector arguments12/10 yield10/8. Next metric5
is `(130*5+80)//160=4`, outside the current pair stop.

Helper25958 checks full32 input zero before SMULBB's signed low16 multiplication.
The +80 ADD is32-bit wrapped; CMP320 is signed. On the >=320 path the getter
is read again. SMULL uses literal66666667 followed by ASR/sign correction;
the final result is narrowed and sign-extended from16bits. Input0 returns0,
whereas input10000hex has zero low16 but takes the nonzero-input/minimum1 path.

Given the coordinator's count10 reference, new distinct tags10/11 require
realloc66/72 on the all-success path. Failed insertion leaves count unchanged.
Final all-success count is12. Summary remains37hex because bit1 was already
present from tags12/13. No pointer location is guessed.

Dynamic state binding, actual getter results, preservation of cached R9, native
insertion success/failure and full memory/guard/SP references remain the
coordinator's separate proof. No physical unit, complete initializer, allocator
implementation, root/callback or device-timing claim is made here.

Reproduce from this isolated checkout with the existing local Capstone dependency
directory on PYTHONPATH:

```powershell
python contributions/COORD-ADC-CADENCE/parallel-20261119/static-review/metric14-pair/audit_metric14_pair.py
```
