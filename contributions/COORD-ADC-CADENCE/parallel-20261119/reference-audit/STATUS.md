# Independent HEAP+20 continuation reference audit — 2026-11-19

Owner scope: the existing coordinator-owned `COORD-ADC-CADENCE` task. This is a
delegated review artifact, not a new task claim or integrated firmware result.

Branch: `external/reference-cold-palette-20261119`.
Base: `4908c7a598dd48bb5372fa79eed793f2f9cf5542`.
Live ownership registry revision 67 was read; owner remains
`codex-ys4470-20261109-01a1c110`.

## Artifact and actual verification

`style_reference.py` is an independent, standard-library-only byte reference. It
does not import any replay implementation and does not execute ARM or Unicorn.
The caller must supply the four raw values captured at original wrapper inputs.
That mandatory argument prevents this reference from silently inventing the
opaque retained high halfword in tag44's payload.

`test_style_reference.py`: **7 unit tests passed**, including all 16 Boolean
success/null schedules against an independent selection/count/pointer oracle.
They verify values-then-tags serialization, old-vector immutability, successful
prefix-copy plus poison-tail fixtures, null invariance, and preservation of the
entire 504-byte heap except its exact eight-byte header at offset `0x20`.
These are synthetic reference tests, **not 16 or 32 new original-image cases**.

Reproduce from this worktree:

```powershell
python -m unittest discover -s contributions/COORD-ADC-CADENCE/parallel-20261119/reference-audit -v
```

The companion `reference-validation.json` freezes all 16 illustrative outcomes,
source hashes and limits. Its payload fixture is explicitly marked unconfirmed;
the coordinator must substitute/confirm native captures before evidence use.

## Independent expected contract

- Initial style bytes: `008001120b000503`; values `13, ff, 1201e71c`, tags
  `0b,21,20`, vector pointer `12018000`.
- The four newly requested tags are `44,40,45,42`. They are distinct from the
  retained tags; successful insertion appends, it does not replace an old tag.
- Vector layout is all `n` little-endian u32 values followed by all `n` u16 tags.
  It is not an interleaved array of six-byte value/tag records.
- Each request size is `6 * (current_count + 1)`. A null result does not change
  count, pointer, old vector or header. Later request sizes depend on how many
  **earlier requests succeeded**, not on the current step's index.
- With all requests null, every request remains 24 bytes and the final header
  stays `008001120b000503`.
- With all requests successful, sizes are `24,30,36,42`, the pointer is
  `1201c000`, retained first-tag halfword is still `000b`, count is seven and
  final header is `00c001120b001507`.
- All four tags contribute the same summary bit, bit 4. The final summary is
  `0x15` if any new insertion succeeds, otherwise `0x05`. Merely attempting a
  tag cannot add its summary bit after a null result.
- Original wrapper `0x8003dfac..0x8003dfc4` keeps incoming R2 HIGH16 and incoming
  R1 LOW16. That high halfword is opaque; this reference assigns no physical
  color meaning. Scalar payloads and their getter arithmetic still require
  the coordinator/static audit's native input binding.

## Guard and inheritance hazards for the coordinator's continuation

1. Disable `metric16_style_phase` after running the initial all-success prefix.
   Its hook at `0x80025958` asserts `[DISPLAY,16]`; leaving it active rejects
   the later metric helper even if the new continuation is correct.
2. The inherited initializer/configuration and earlier outcome phases are not
   all disabled by the existing ladder. Admit only the newly justified PC
   ranges in the new override before falling through. Do not widen an ancestor
   hook just to suppress a failing assertion.
3. For this count-three-and-up insertion path, native buffer writes are tag
   shifts at `0x8003deb8` and new tag/value stores at `0x8003ddf0/0x8003ddf4`.
   Header writes are at `0x8003de98`, `0x8003ded0`, `0x8003df98`. No count-one
   allocator path is expected from this prefix.
4. Preserve every previous vector and its guard pair, not just the current
   vector. A later moving success must not hide corruption of an old allocation.
5. The full BSS snapshot already covers the driver and BSS objects, while DATA,
   display, timer, heap and all old/new guarded vectors remain separate checks.
6. SP equality proves the pointer was restored, not saved-frame preservation.
   Freeze the live caller frame `[sp, STACK)` as well if claiming its bytes are
   preserved. Do not compare all below-SP scratch, which callees legitimately use.
7. Allocate the new guarded fixtures at `12019000/1201a000/1201b000/1201c000`.
   Never use `1100f000`, which is the active stack. Python `mem_write` setup is
   a fixture operation, not a native write or a guard-hook observation.

## Limits and handoff

No existing CPU campaign was repeated. No shared source, registry, database,
firmware, device, branch or remote was modified by this audit. Native allocator
semantics, free/reuse, full configuration/initializer return, later callbacks,
physical units, display output and physical timing remain unproven.

The parent coordinator owns native execution, result comparison and integration.
