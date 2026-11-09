# Coordinator handoff — verified checkpoint, 2026-11-09

## Start from this state

Repository: https://github.com/NandorHU/YS4470-Firmware-RE (public).
Authoritative development branch: `re/2026-11-04-pyghidra-fel`.
Last research commit: **a2e5e7ebd2f661f37f88507f55a62a14c5df3f9f**;
tree `7924caa4d34f57914bcf031e0d553c0e7a29647c`.
At that checkpoint FUNCTION_DATABASE.json has62 records and TASK_REGISTRY.json
revision17. The migration documentation adds a subsequent registry revision,
not additional firmware coverage. Consult the live branch before continuing.

The owner wants full original V3.6/V3.8 understanding and a standalone functional
source reconstruction. Diode/continuity speed is an immediate priority, not the
whole project. Existing modified Beta3/1.0 images and the English GUI installer
are not a source-equivalent firmware. Only bounded C components exist so far.
No honest single completion percentage is available.

The old Windows project directory is a file snapshot without .git and partly
lags upstream. Some latest artifacts were generated in writable isolated staging
directories and integrated through GitHub's Git-data API. Start from a fresh
dev checkout or the transfer bundle. Do not overlay a stale directory onto it.

Read AGENTS.md, CONTRIBUTING.md, CURRENT_HANDOFF.md, live TASK_REGISTRY.json,
LOCAL_LLM.md and the seven central status/maps before selecting work. New
sections at the ends of older documents supersede their historical introductions.
In particular older60-record/failed-Ollama remarks are superseded by62 records
and the restored local API. Role names are bounded research labels unless an
original string/caller binding is proven.

## Owner authorizations and constraints

- Work on a development branch. External agents work in separate checkouts on
  their own branches/forks, never main. The coordinator reviews and integrates.
- Publication of the two manifest-pinned original application images was
  explicitly authorized on2026-11-07. No other private full-flash, calibration,
  credentials or device dumps are authorized for an automatic public handoff.
- The public patcher and installer publication and PR#2 merge were authorized
  and completed earlier. This handoff does not grant a new main merge or hardware
  action. Preserve original inputs, checksums, rollback and evidence.
- Latest explicit restriction: **do not write firmware to a device**. No flash,
  bootloader modification or unreviewed RAM execution. Older broad permissions
  to speed up research do not override this later restriction.
- No paid external APIs. Do useful bounded analysis; do not repeat completed
  matrices or claim a test that was not run.
- Emulation counters/requested sleep units are not physical probe-to-sound delay.
  Synthetic UART delivery does not establish external ADC behavior.

## Inputs and address conventions

| Input | Bytes | SHA-256 |
|---|---:|---|
| original-firmware/V3.6/f1c100s.bin |5943296|7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9|
| original-firmware/V3.8/f1c100s.bin |5943296|7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290|

Both contain a32-byte eGON.EXE header. Raw linked base is **0x7fffffe0**;
code begins0x80000000. Convert with file_offset=linked_address-0x7fffffe0.
Application size0x5ab000. A16MiB flash container places the application at
0x50000, exclusive end0x5fb000. Original images are application inputs, not
personal full-chip backups or proof of flash safety.

A bounded original loader experiment proves flash0x50020→RAM0x80000000,
length5943264 in12 cases with SPI/printf modeled. It does not execute complete
DRAM/cold-boot initialization. Never load a full-flash dump at the app link base.

The current E2 experimental four-profile image has SHA
`b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1`.
`contributions/COORD-ADC-CADENCE/reproduce_profiles.py` recreates it from the
published V3.8 app and pinned patch/reply/threshold chain with158 ordered
preimage-checked recorded edits. This is **recorded-edit replay**, not independent
source-generator equivalence. See profile-inputs.json/profile-chain.json.
Original, modified Release and experimental inputs are not interchangeable.

The original V3.6/V3.8 raw comparison is already done:
evidence/2026-11-06-v36-v38-raw-diff.json records20 differing bytes in10 ranges
(4 header bytes and16 data bytes across9 cells). The bounded PyGhidra comparison
in evidence/2026-11-06-v36-v38-pyghidra-function-compare.json has13/13 identical
exported bodies, not proof that all functions/globals are equivalent. Labels
containing Beta3 in the old seed report remain candidates even on a stock image;
the label does not prove that modified code exists there. Prefer current packets
and database corrections over those earlier seed names.

## Research checkpoints to reuse

All listed tests are bounded experiments with different units. Their counts
must not be added into an overall coverage percentage.

| Area | Existing evidence and scope |
|---|---|
| F1C100S references | references/f1c100s/, sources.lock.json, register-map.json, F1C100S_REFERENCE_MAP.md; candidate scoring and proof-gated labels; selected drivers cross-compiled, not blindly copied |
| INTC/timer | tools/INTC_TIMER_PATH.md; evidence/2026-11-07-intc-timer-path.json:4446 reported cases. Timer0 interval24000/control7/IRQ13; nominal1kHz still depends on actual24MHz source |
| Fast CONT retained median/history | tools/FAST_CONT_FILTER.md; evidence/2026-11-07-fast-cont-filter.json:3958 reported persistent steps; independent reconstruction/fast_cont.c |
| Stored result freshness | tools/RESULT_FRESHNESS.md; evidence/2026-11-07-result-freshness.json:752 cases/steps; refresh can reuse a stored result without fresh UART |
| Refresh/queue/renderer | tools/REFRESH_SIDE_EFFECTS.md;2396 checks,14 Ghidra exports; queue10 records×68 bytes, event4. Full RTOS scheduling not emulated |
| FSM timeout | contributions/COORD-FSM-TIMEOUT/:13302 checks with real getter/critical helpers, independent Python/C; equality expires under unsigned elapsed/wrap. Hypothetical30/40 comparison is not proof of Beta3 provenance |
| Six full-local-CFG packets | contributions/COORD-FUNCTION-PACKETS/:3 functions×2 originals,360 byte checks,388 CFG edges,4 outer-loop executions; packet-index.json pins all hashes |
| Equal-Highspeed E2 profiles | contributions/COORD-ADC-CADENCE/profile-validation.json and README.md:64 waveform cases,64 active/requested switches,16 candidate comparisons,268 assertion groups |
| Original UART | uart/validation.json and README.md:12704 original/Python/independent ARM-C transport cases,184 delayed schedules,12 controlled ISR interleaves,4 concatenations,2 cross-command rejects,2 bounded blocked-TX prefixes |
| Admission/caller ownership | admission/validation.json:1200 prefix-stability and24 service-idle cases; synchronous-static.json classifies9 raw BL sites plus tail8000404c→80005f14;95-instruction helper static context |
| Latest original execution | synchronous/synchronous-validation.json:40 cases,20 per original, only proven startup IDs9/19; real helper/sender/ISR/copy/clear/GPIO with modeled sleep/UART delivery |

Recent commits separating the evidence layers:
- ed71bdb5d2dc3745ab700c1a80fe544788044077 — E2/profile matrix.
- d4140e2fd396c4f0edc4b8590c227fc6a50eaf6c — UART correlation and pure C.
- bf33ebad2b3539fa29665c5548b28ad039f440f1 — prefix stability/caller ownership.
- a2e5e7ebd2f661f37f88507f55a62a14c5df3f9f — restored local server/startup helper.

## Corrected functions, globals and timing facts

| Address | Established meaning or explicit limitation |
|---|---|
|80003dbc|GaugeCmdTask entry: original static name binding at5948..5954 reaches call5958 with R0=3dbc,R1=5a10→GaugeCmdTask. Setup5d24, startup helper5f14 arguments9 then19, loop3dd0→5b6c/backedge3dd4 |
|80005b6c|Service body, **not** GaugeCmdTask entry. Original idle path calls FSM4490 then sleep(1) through tail5d14→60fbc. Requested units are not a measured task period |
|80005a78|MainADCTask candidate; separate I2C monitor branch. Not established as source of diode results |
|80004490|MeasurementFSM; root805ac694. +2c start, +30 duration cached inR5, +34 busy |
|80061f84|Real counter getter→805abbc8 under critical helpers; modulo unsigned elapsed, deadline equality expires |
|800037c0|ResultDispatch entry; old37bc was literal data |
|8005d048|MeasurementRefreshCallback; old5d1a0 is a callsite, not function entry |
|80006e4c|SoundControlGate→60d0→42d40→PA2/PWM0; off uses zero active duty with gate/enable still set |
|800073bc|UART RX ISR entry/literal-pointer load; actual UART status read is73c8. Count store7408 precedes buffer store740c |
|80005e84|UART sender; byte output6dc8; readiness loop6e00..6e08 tests UART+7c bit1, actual TX store6e10→UART+0 |
|80005f14|Synchronous ACK helper; full original execution now proven for startup IDs9/19 only |
|80003dd8|Fallback/deferred-control handler role; static body context and idle-gated entry proven, not all command paths |
|805b408c..805b4154|RX buffer,200 bytes, exclusive end; count805ab938 |
|805b4154..805b421c|TX buffer,200 bytes, exclusive end |
|805aae8c|Control object; discard+1, configured+8 |
|805abefc|UI object |
|805ac714|Result object; raw+1c, selector+20 |
|805ac6d0..805ac714|Deferred68-byte record, after3c-byte FSM object; pointer literal80005d20 |
|80060a90|E2 experimental profile bytes: active/requested at offsets0/1, apply only idle |

The UART peripheral base is0x01c25800. Measurement descriptor1d has source60,
wire6060 with additive checksum; descriptor1b source5e, wire5e5e. Source-buffer
boundary is not the wire-frame boundary. Measurement state3 requires5 bytes
with correct header and admits a complete valid frame before checking deadline;
these descriptor durations are30 raw units. Other descriptor setup/settle
constants80/50/100 require their own path context, not a universal delay claim.

Original initialized globals are generated by original copy124/decompressc8:
5604 bytes at805aaab4..805ac098, SHA
`524ba48c4f8e6b7876fc1da735f82f197eb436947e65eac043f2d9f2b96f8be0`.
Do not replace them all with zeros in a profile comparison. V3.6/V3.8 changed
data cell starts at file63ac8..63ae8/link80063aa8..63ac8 (last cell ends at
file63aea/link80063aca, exclusively) are separate from unchanged
PWM table80063acc (pointer80042d98). Changed data is not automatically buzzer data.

### Why Base can feel faster: what is and is not proven

At identical Highspeed settings the E2 active-profile sound ownership condition
differs from the GUI refresh period. active!=0 can move sound to the reply path;
active/requested must be tracked separately across idle application. For modeled
stable low input over250 units, Highspeed1 yields Base/Direct10 requests,
Auto32, Ready42; Base accepts at106/sounds125, Direct accepts/sounds106,
and both render125. A short contact101..109 yields modeled on/off times
Base125/150, Direct106/131, Auto110/118, Ready107/113. Different audible pulse
length is a plausible perception hypothesis, not a measured physical explanation.
The current proof does not establish Base's physical superiority or warrant a fix.

UART proof also establishes a late matching first reply can be accepted after
retry: request0, timeout30, retry selected31, send32, old bytes33..37, result38.
Matching header identifies command class, not request instance in that path.
An old reply after RX clear/before TX can survive a controlled interleave.
Two concatenated frames publish only the first; count10 survives finalization
and builder until next state1 clears the tail. Permanently not-ready UART can
remain in a polling loop before the FSM's post-send timestamp. None of these
injected schedules proves actual ADC conversion/restart/buffering behavior.

Admission tests show append-only ISR delivery preserves an admitted prefix.
The known deferred-handler route is service-idle-gated. Do not infer a feasible
live clear/parse race from a shared pointer alone. Other aliases/tasks and
indirect calls remain open. UART C equivalence excludes corrupt signed counts,
source-count+1 wrap and overlapping buffers; tested count domain is0..201,
accepted transmit source lengths0..199.

### Latest result: startup synchronous helper

For command9 source5803→wire58035b; command19 source5900→wire590059.
Matching first header byte before the first check returns1 with **zero sleeps**;
a five-byte reply with arbitrary trailing bytes also passes and remains buffered.
The helper checks before sleep, up to500 iterations per attempt, at most2 sends.
Missing/wrong header returns0 after1000 requested sleep(1) calls. A match after
499 first-attempt sleeps passes; after500 it is cleared before retry. A match
after499 second-attempt sleeps passes after999 total; after500 the function
returns0 with the matching header still present because there is no final check.
Old matching header during TX also passes in the controlled tested schedule.
GPIO bits2/3 cleanup, callee-saved ABI and nesting checks pass.

500 is a loop limit, neither a fixed mandatory wait nor500ms. This helper's
one-byte ACK contract is separate from the measurement FSM's five-byte admission.
Its boundary behavior is not automatically a bug or a justified speed patch.

## Exact next bounded research task

Continue **COORD-ADC-CADENCE**, currently in_progress, owned by coordinator.
1. Reuse admission/synchronous-static.json, the six packets and latest40 cases.
2. Trace further reachable fallback-handler80003dd8 argument paths and the
   producers of the deferred68-byte record805ac6d0. Include the tail edge4004c.
3. Establish actual caller/idle preconditions before executing more helper IDs.
   Run original instructions with explicit guards and document modeled leaves.
4. Trace other writers/aliases and indirect calls before broad buffer-ownership
   or concurrent-clear claims. Do not assume every raw BL decode is reachable.
5. Only if this reveals an independently justified fault, create a separate
   offline fix candidate and differential tests. No hardware installation.

Remaining physical questions: actual installed application hash/profile, external
measurement peer/ADC identity and conversion/restart latency, live scheduler
frequency, asynchronous UART delivery and acoustic/display timing. Current meter
mode/firmware identity is not established by this handoff. FEL was demonstrated
earlier but is BootROM mode, not a normal-firmware live debugger. Owner has a
UART TTL adapter but it is not wired; passive UART task stays blocked. No logic
analyzer is available. Other full-firmware subsystems remain largely open; consult
ROADMAP.md rather than treating the narrow timing task as the whole project.

## Patcher and installer status

Public CLI patcher/ys4470_patch.py is stdlib-only: inspect/apply/revert raw app
or16MiB container. It requires exact known app hash and preimage/output checks,
separate nonexisting output, no force/in-place overwrite, and preserves outside
the app.14 tests and12 loader-window cases passed. Private Beta3 is no longer a
prerequisite. V3.6 is offline-tested, not physically verified.

patch-data.json SHA:
`9b06a2bd42cb0278488cc75b8e28c7840771d08ed8d540a83aa328b78d4b03b8`.
Expected modified app hashes:

| Input/variant | Output SHA-256 |
|---|---|
|V3.8 continuous|697d160047e9f040b31acd79d5b0febb940bc712f15eb6e2d91d997a5608011d|
|V3.8 timed|89a5bb79ec304a57a758e33bf89d6d7b3848982573460a476fb53e7412877729|
|V3.6 continuous|2e3c4251e568a9dd076ddf98c2fedd97eaa22a976970b276f02ff882d941ca45|
|V3.6 timed|373ea64a5240c567810ef2e1c1dc6c0a2ce4bbf81e26347091b6e0c9885d4fc0|

English installer1.1.0-beta.2 source commit/tag target
`c12fdef3fcb56c1f6b504ac1330f02965e6bc727` bundles stockV3.8, Python/TclTk,
FEL, Zadig and patch data. End users need no separate Python. Offline file
generation needs no device. Actual writing is explicitly user initiated and
guarded by two matching16MiB reads, per-user recovery backup/plan/fsync,
known F1C100S/Winbond16MiB identity, only changed64KiB app blocks and full readback.
Zadig driver installation still requires explicit device choice and Windows UAC;
normal→FEL is not automatic. Read installer/README.md, RELEASE-NOTES.md and
contributions/COORD-EASY-INSTALLER/ before changing it.

Earlier CI run42499845896/job128789999855 passed19 installer/driver tests,
14 patcher tests and8 packaged-resource checks (Tcl8.6.15). Asset digests were
download-verified before beta.2 publication. GUI appearance and this packaged
FEL version were **not** physically validated. Historical owner report of
working1.0 does not prove the new installer. Installer1.1 is not a new measured
firmware-speed release.

**Migration availability check:** beta.2 Release tag and ID438367330 both return
404, while Git tag/source remain. Public v1.0 remains listed; beta.1 is a draft.
No open PRs; issue#1 remains open with historical patcher requirements. Do not
restart its obsolete private-Beta3 prerequisite. Cause of missing beta.2 unknown.
The local kit retains the exact earlier verified Windows ZIP:
`YS4470-Installer-1.1.0-beta.2-Windows-x64.zip`,18586707 bytes, SHA
`7beb67b4187d63c9756a1e336d29386bbe95b40272402d53b69a2d7743502d72`.
Historical publication receipt is contributions/COORD-EASY-INSTALLER/published-release.json.
Do not silently republish or substitute beta.1. Beta.2 source is in Git even
though its historical Sources.zip is not locally retained.

## References, rights and reconstruction boundaries

Four pinned reference repos, fetched with tools/fetch_f1c100s_references.ps1:

| Repo | Commit | Root licensing caveat |
|---|---|---|
|mikljohansson/fnirsi-1013d-mcp|fa8377b2b1d148f8596a8befe638df79062c2bd8|GPL-3.0|
|nminaylov/F1C100s_projects|c11422e99c9f33e8419a5ac4dcab6684c8d38296|GPL-3.0; retain component notices|
|nminaylov/F1C100s_info|ec42b9b4147070b4277e86d12324d5cd0662cd1a|No root license; upstream BROM/SDK objects not republished|
|minilogic/f1c_nonos|73933dbb56d2cbdeb1f260a484bb7c525866616f|No root license; component-specific licenses|

Use root NOTICE.md, sources.lock.json and derived register-map evidence. Raw
reference checkouts are ignored, reproducible separately and not in the bundle.
Reference structures can be inconsistent; do not import a driver layout or
board-specific FPGA/ADC wiring as fact about YS-4470.

Selected reference MMIO anchors: INTC01c20400, timer/watchdog01c20c00,
GPIO01c20800, PWM01c21000, UART201c25800, CCU01c20000, SPI001c05000,
TWI001c27000, DMA01c02000, DRAMC01c01000, TCON01c0c000,
DEFE01e00000, DEBE01e60000. Full offsets/provenance/methods are in
references/f1c100s/F1C100S_REFERENCE_MAP.md and register-map.json. Internal
KEYADC/RTP are separate from the proven external measurement UART transport.

reconstruction/fast_cont.c, fsm_timeout.c and uart_transport.c are independent
pure semantic components with differential evidence, not a complete firmware,
hardware drivers or a full scheduler. Ghidra decompilation and model prose are
analysis aids, never independent evidence of source equivalence.

## Task ownership snapshot and handover

COORD-FSM-TIMEOUT, COORD-LOCAL-TOOLS, COORD-FUNCTION-PACKETS,
COORD-PUBLIC-PATCHER, COORD-EASY-INSTALLER and EXT-EVIDENCE-AUDIT are complete.
COORD-ADC-CADENCE remains in_progress. LOCAL-PROFILE-LATENCY is review;
the old incomplete31-task batch is quarantined, not a fresh task.
EXT-DATA9, EXT-QUEUE-WAIT, EXT-RECORD-TEXT, EXT-UART-REFERENCE and
EXT-LITERAL-AUDIT are available in the observed registry. HW-UART-PASSIVE is
blocked on wiring. Read live upstream before reserving any of them.

Each external result supplies task ID, own branch/fork, base/result commit,
changed paths, validation commands/results and limits. Use contributions/TASK-ID/
and the collaboration request/handoff templates. Central status/database writes
remain coordinator-owned. Silence never releases a task. On actual takeover,
the successor records a unique coordinator identity and task ownership against
the latest branch head with a lease. This package only prepares the handoff;
it does not start another coordinator or relinquish active tasks automatically.
