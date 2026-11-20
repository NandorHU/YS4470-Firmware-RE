# Resumed multi-agent cold GUI proof — 2026-11-19

Owner remains `codex-ys4470-20261109-01a1c110`, existing `COORD-ADC-CADENCE`.
The owner explicitly resumed RE with the other agents. Live upstream registry67,
open issue1 and PR3 were checked before delegation; no ownership was inferred
from silence. No main/device/remote-publication operation occurred.

## New original execution

`synchronous/validate_native_cold_palette_tail.py` continues the established
all-success metric16 prefix from `0x80058f10` to `0x8005904c`. Thirty-two runs
cover all16 explicit NULL/moving-success realloc schedules on both full-hash
verified originals. They agree byte-for-byte, including recorded instructions.

- New tags:44/40/45/42, captured raw payloads12019cf3/2/7f/2.
- Default getter input0 actually dereferences restored slot805abd60=DISPLAY,
  rather than taking its NULL fallback. All six actual returns are130.
- Local full32 metric4 gives3; native helper25958(DISPLAY,3) gives2. No units.
- Exact API arguments are checked before injecting allocation outcomes.
  All-success sizes24/30/36/42; final style00c001120b001507/count7/summary15.
- The entire504-byte heap, all prior/new vectors and guard pairs, BSS/DATA,
  display/timer and SP are checked after every insertion. Saved caller-frame
  bytes from the captured SP to1100f000 are also frozen and compared.

The native allocator itself, free/reuse behavior, later configuration suffix,
initializer return, roots/callbacks and physical LCD/timing remain open.
The initial all-success probe is preparation, excluded from the32-run campaign.
Early guard/conditional-hook probe failures were corrected before the campaign:
summary store3df98 is a legitimate write, and a Unicorn code hook at conditional
BXEQ does not mean that the instruction's condition was true. The final harness
checks CPSR.Z before counting that conditional return.

## Independent agents and review

- Static agent: original commit0b46a2c81749bc7a8227145f62146009aeac5345,
  integrated locally as29d872f. It verified147 ARM words on both originals and
  distinguished local full32 arithmetic from helper signed16 SMULBB semantics.
- Reference agent: original commit1834ef807c211c8c662eb407aa5d2bc4fa641b91,
  integrated locally asbe35a95. Seven pure-reference tests passed over16 synthetic
  schedules, without counting them as original-image cases.
- `review_palette_tail.py` binds actual wrapper inputs to that separately
  written model; all stage arguments, headers and vectors agree. It does not
  rerun ARM. The independent review receipt pins the native report and reference.

## Reproduce without replacing an active checkout

Some inherited replay helpers are still local uncommitted work predating this
session. `synchronous/cold-palette-tail-source-capsule.zip` freezes the exact
30-file local import closure; its JSON sidecar pins every source hash.
Extract it only into a separate checkout of the documented base, preserving
the relative repository paths. The tracked original-firmware files supply the
two inputs. Provide the existing project-local Unicorn/Capstone dependencies
on PYTHONPATH, then run the main script with `--out` to a fresh output file.
No claim is made that all capsule helpers existed at the old Git base.

Run `python contributions/COORD-ADC-CADENCE/parallel-20261119/review_palette_tail.py`
for the independent comparison and `python -m unittest discover -s
contributions/COORD-ADC-CADENCE/parallel-20261119/reference-audit -p test_style_reference.py`
for its seven synthetic reference checks.

## Local/cloud workers

The new coordinator dispatched two fresh, bounded original-quotation tasks.
Qwen3.5:9b finished tag40 after explicit coordinator correction of a mistaken
tag/task-ID field and punctuation. Its first attempt also exposed missing
validator error feedback; the tool now returns bounded failure output and a
new regression test passes. The accepted artifact remains an instruction
index, not a semantic firmware finding. OpenCode DeepSeek Free again reports
free-usage quota exhaustion and is durably blocked without paid fallback.
Mercury remains installed but unconfigured, not an active worker.

The legacy CPU/GPU queue marker remains deliberately in place so its supervisor
cannot start another GPU consumer. New model jobs use the separate coordinator
profile and existing Ollama11435. The finite native proof runs above are not
reseeded to fill an empty queue.

## Next exact boundary

Continue all-success PaletteTailReplay at5904c. Wrapper3e004 at59058 selects
tag55 and preserves incomingR2 high16 around the halfword read[OBJECT+4].
Capture that halfword and raw payload before assigning meaning. Then actual
OBJECT byte1 branches at59068: value1 goes59c50; otherwise value2 selects
metric20 and other values metric16 before wrappers3ddb4/3ddc0. Prove the
observed cold branch and each exact allocator call with full references.
Do not assume full configuration return, physical color format or units.
