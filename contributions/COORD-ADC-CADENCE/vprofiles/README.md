# Beta Diode profiles (beta.5: Base, v1..v4; beta.6: only v2/v4 selectable)

`build_vprofiles.py --out out/vprofiles` reproduces the application from the pinned V3.8 original
(E2 chain → volume overlay → ownprotocol-style polling → beta.4 diode fixed range) and adds:

| Address | Change |
|---|---|
| overlay (bitmap region) | own_auto, own_post_apply, own_reconfig, own_case2, own_classify, own_cycle, own_label, state words, `68 0a` bytes, labels v1..v4 |
| 0x8001110c / 0x8005f8b0 / 0x800609c0 | ownprotocol hooks (auto, cycle, label) as before |
| 0x80007f88 | `cmp r0,#3` → `#1`: Ready completion steps for every v profile |
| 0x8000446c | case-2 list build → own_case2 (`[0x0e,0x1e,sec,0x1d]` for v2/v4) |
| 0x80060c94 | reply-sound classifier call → own_classify (v3/v4 "tone first") |
| 0x8005fb84 | `bleq 0x8001110c` → own_post_apply (68-state reconfiguration for every profile) |
| 0x8006376c | descriptor 0x1e = (`68 0a`, 2) |
| 4 diodefixed sites | as beta.4 |

Profile semantics, test results and limits: `validation.json` (from `test_vprofiles.py`),
`../../../installer/RELEASE-NOTES.md`. The only tunable constant is the 200-tick (ms) plateau timeout in
own_classify. `68 0a` is never sent by factory firmware; its chip meaning is a hypothesis.

beta.6 (2026-11-20, after the owner's hardware test rated v2 and v4 excellent): own_cycle alternates
2 ↔ 4, toggle callback 0x800609e0 (0x800609ec..f4) maps to 2 ↔ 4, boot bytes 0x80060a90 = 02 02.
