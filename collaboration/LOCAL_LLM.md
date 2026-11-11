# Local LLM collaboration — measured limits, 2026-11-08

The current Codex agent remains coordinator. Local drafts and tools are isolated
on [the reviewed external branch snapshot](https://github.com/NandorHU/YS4470-Firmware-RE/tree/460405fa04971992d2d8830bac1d6ba914a927fc/contributions/EXT-EVIDENCE-AUDIT). main stays read-only.

## What I actually checked

I found the existing local Ollama service at http://127.0.0.1:11435, with
qwen3.5:9b and qwen2.5-coder:14b installed. The earlier31-task profile draft was
already complete. Its source hashes matched, but22 replies ended at the token
limit and its binary-build provenance was unverified. I did not repeat that batch.

I ran six short source-cited reviews on qwen2.5-coder:14b. They generated3,065
local tokens in77 seconds of model requests. All six responses were complete.
Of24 citations,15 were exact,6 were relocated by a unique exact quote, and3
were ungrounded. My semantic review confirmed6 existing facts and7 documented
limits and rejected11 findings. No new firmware claim was promoted.

A test-only in-memory unexpected counter store is rejected by the existing
getter write guard, contrary to a model's proposed missing check.
See the external snapshot's coordinator-review.json and lessons-evaluation.json.
The verified FSM result remains commit66d02a5:13,302 checks and59 function records.

## What “teaching” means here

LESSONS.md contains checked rules and worked examples, applied by
run_taught_review.py to every new request. This is in-context preparation,
not weight training. Other clients do not inherit these instructions automatically.

The same two small ARM-classification cases scored0/2 without the examples
and1/2 with them in one run. This is too small to establish general improvement;
the remaining unsigned-equality error still fails the intended quality gate.
No overall time saving or autonomous firmware-analysis capability is claimed.

## Current allocation

- The primary agent continues the binary/emulation task and owns integration.
- Use the local model only for a small, assigned extraction/index/draft task.
  Source arithmetic, hashes, exact quotes and line locations are computed by tools.
- Keep a local batch under two minutes initially; stop expanding it when checking
  the drafts costs more than doing the bounded task directly.
- Treat a citation match as grounding, not semantic proof. Never promote model
  names, units, physical timing or hardware identities automatically.
- No model shell/Git/device tools, paid external API or automatic code application.
  Do not repeat completed jobs; make a new frozen manifest for a new scope.

The raw failed probes are retained locally; the strict-schema worker records
all completion reasons and rejects token-cutoff responses. The old worker,
model weights and original firmware were not changed.

## Ready-made projects checked on 2026-11-08

- [promptfoo](https://github.com/promptfoo/promptfoo): regression evaluations and
  model/prompt comparisons; its [Ollama provider](https://github.com/promptfoo/promptfoo/blob/main/site/docs/providers/ollama.md)
  can run locally. Use deterministic assertions and a fixed held-out test set.
- [DSPy/GEPA](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/getting-started/gepa-optimization.md):
  optimize instructions/examples against training cases and a metric without
  changing base weights. Configure local models explicitly.
- [Unsloth](https://github.com/unslothai/unsloth): actual LoRA/QLoRA fine-tuning.
- [LlamaFactory](https://github.com/hiyouga/LlamaFactory): alternative trainer
  with GUI, supervised fine-tuning and LoRA/QLoRA support.

promptfoo and DSPy are now installed and exercised; see the coordinator-owned tools below. Unsloth/LlamaFactory remain researched options, not installed trainers or promises of a gain.
Before weight training, curate independently checked ARM/source-to-explanation
pairs. Split evaluation by function/byte identity so matching V3.6/V3.8 bodies
do not leak between training and test. Do not train on uncorrected local drafts.
GPU memory suitability and post-training accuracy must be measured separately.

Next firmware task remains the coordinator-reserved COORD-ADC-CADENCE.


## Installed tools and current packet workflow (2026-11-08)

Use [COORD-LOCAL-TOOLS](../contributions/COORD-LOCAL-TOOLS/README.md) for pins and measured calibration/REA scope, and [COORD-FUNCTION-PACKETS](../contributions/COORD-FUNCTION-PACKETS/README.md) for the current checked-lessons worker, full-function packets and SQLite/FTS5 lookup. Historical raw local drafts remain on their separate external snapshot; do not rerun them.

The current worker rejects every completion reason other than stop, keeps token-cutoff JSON incomplete, records attempts atomically, retries at most once, and skips reviewed/exhausted tasks on resume. Only source-grounded drafts reach coordinator review. The six-packet index requires an explicit original binary hash. REA access tested here is a single fixed read-only file-evidence view; it does not supply raw-ARM decompilation. No free-form tool/code/device execution is delegated.

I ran13 regression tests and a zero-new-call resume. The new three-question-per-context comparison establishes source coverage only:3/3 full versus1/3 eight-instruction views, with no fair timing/general-quality claim. See comparison-review.json for the initial quote-gate mistake and offline correction. Continue COORD-ADC-CADENCE; completed calibrations are not daily work.


## 2026-11-09: original UART correlation proof

A fresh checksum-extraction task completed in6.656s with46 generated tokens; its0x80005ed4 quote was checked against original bytes/Ghidra. Its external-power-consumption limit was true but not useful to conversion semantics; no independent firmware finding was promoted. At the owner's next request I prepared two new small owned extraction contexts (RX register/count index; synchronous shared-buffer clear/delay index) under contributions/COORD-ADC-CADENCE/uart/local-collab-2026-11-09/. Both calls encountered WinError10061 on127.0.0.1:11435; source packets and failed receipts are retained, not marked complete. The owner was asked for the current service/program address. Do not rerun completed jobs or change firmware evidence to match model output. Coordinator binary analysis/integration continues independently.


## 2026-11-09: local model restored and startup-helper execution

The owner explicitly asked the coordinator to start the local model while away. I located the existing signed portable executable at the legacy project's local-ai/runtime/ollama.exe and models under local-ai/models, then started a hidden loopback-only0.40.15 server with OLLAMA_NO_CLOUD=1, one request/model, flash attention/q8_0 cache; logs/temp are in an isolated writable workspace. Executable SHA256544216ca2082b8bc19b4ba94b513f0098fa06774b232f3c140090e3449e322a5; coder digest remains9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849. The API reports size=size_vram9,107,029,359/context4096. Two explicit retries of transport-only failures produced183 tokens in12.062s; both violated requested JSON keys and one grounded pointer quote was semantically wrong. Manual review accepted3/4 extractions. A separate checked UART lesson and NEW held-out TX-ID question produced a correct response (19 tokens/1.094s), not a fine-tune/general improvement result. Base lessons/frozen jobs were not edited. Use contributions/COORD-ADC-CADENCE/synchronous/ for runtime recovery, raw replies, feedback and limits; no model tools or generated-code execution are enabled.

## 2026-11-10 — KeyTask ordering index

The existing pinned Ollama server was restarted after confirming the loopback
port was free. Two new address-extraction tasks used the checked lessons and
bounded packet worker. Both exhausted their two attempts after returning the
evidence address as the function entry. The claim that the countdown store
receives zero in both paths also disagrees with the original binary.

A separate, narrower batch indexed the immediate loads at `0x80006eec` and
`0x8005d244`. Both completed on the first attempt and were checked against
the two original images. The [coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/key-task-local-index-review.json)
contains the exact bytes, firmware hashes and limits. The local model supplied
index drafts. The coordinator ran the original-code experiments.

## 2026-11-10 — Scheduler instruction index

The existing pinned local service remained reachable. Two successive
batches each indexed two new instructions from short original V3.8 address
listings using the checked lessons and bounded packet worker. All four
drafts completed on the first attempt. The [coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/scheduler-local-index-review.json)
checks their exact addresses, bytes and decoded instructions against both
factory images. The coordinator ran the original scheduler experiments.

## 2026-11-10 — IRQ, SVC and low-vector instruction index

The existing pinned service ran three successive batches with two new
instructions per batch. All six drafts completed on their first attempt.
The [coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/scheduler-irq-local-index-review.json) confirms exact addresses,
bytes and decoded instructions against both factory images. The coordinator
ran the original context-switch and vector-install tests independently.

## 2026-11-10 — Timer0, UART2 and parser instruction index

The pinned local model ran three new two-instruction batches with the
checked lessons. All six drafts completed on their first attempt. The
[coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/timer0-uart2-local-index-review.json) pins addresses, quotes and
original bytes for both firmware versions. The original ARM926 tests
establish the linked IRQ and parser behavior.

## 2026-11-10 — Scheduled GaugeCmdTask instruction index

The pinned local model processed four successive two-instruction batches
with the checked lessons. All eight drafts completed on the first attempt.
The [coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/gauge-scheduled-local-index-review.json) checks their addresses, exact
assembly and original bytes on both factory images. The coordinator ran the
scheduled queue, IRQ and fallback experiments independently.

## 2026-11-10 — Long fallback instruction index

The pinned Ollama service ran three successive batches of two new
instruction extracts using the checked lessons. All six drafts completed
on the first attempt. The [coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/gauge-long-fallback-local-index-review.json)
checks each address, quote and original bytes on both factory images.
The dynamic waits and UART behavior come from the original ARM926 replay.

## 2026-11-10 — Live calibration UI instruction index

The checked Ollama worker completed six new extracts across three
batches. The [coordinator review](../contributions/COORD-ADC-CADENCE/synchronous/calibration-ui-live-local-index-review.json) confirms
the instruction addresses and original bytes on both factory images.
The shared-memory timer behavior was tested independently.

## 2026-11-10 — Resident instruction queue

The owner requested a continuous local worker alongside the coordinator.
The [resident queue](../contributions/COORD-ADC-CADENCE/local-index/README.md) processes new
factory-byte-checked instruction windows in bounded batches and writes
local receipts for periodic review. The coordinator’s existing three-hour
heartbeat checks progress and continues the next original-code analysis.

## 2026-11-10 — Resident queue refill

The first resident catalog completed and the same process resumed from a
[630-address refill](../contributions/COORD-ADC-CADENCE/local-index/queue-uart-ui-refill.json). The coordinator checked the words
against both factory images before publishing the catalog to the inbox.
Ten recent drafts matched the exact address and quote check. They remain
static index evidence.

## 2026-11-10 — First complete resident snapshot review

The coordinator audited 2,653 completed resident drafts against the
frozen packets and both originals. The [checked export](../contributions/COORD-ADC-CADENCE/local-index/review-2026-11-10/README.md)
contains 2,652 exact instruction rows. One draft used the wrong identity
and was excluded. The queue continued running during the review and
received 160 additional original queue and scheduler addresses.

## 2026-11-10 — Direct-producer and field-signature indexes

The coordinator checked [428 additional instruction rows](../contributions/COORD-ADC-CADENCE/local-index/review-2026-11-10-delta/README.md)
against both factory images and the frozen packets. The resident worker
received 68 new direct-suffix addresses, eight additional executed
prefix addresses, and 67 addresses from bounded field-signature
contexts. All catalogs were checked against the originals and
deduplicated before they entered the existing queue.

## 2026-11-10 — GUI field and glyph bitmap work

The coordinator checked [201 additional instruction extracts](../contributions/COORD-ADC-CADENCE/local-index/review-2026-11-10-gui-field/README.md),
including all 67 field-context addresses and the 134 addresses from the
new GUI constructor catalog. The next batch has 93 verified ARM
addresses from the original glyph lookup. Each catalog was checked
against both originals and deduplicated before entering the resident queue.

## 2026-11-10 — Event registration and dispatcher work

The coordinator checked [220 new instruction rows](../contributions/COORD-ADC-CADENCE/local-index/review-2026-11-10-control-events/README.md).
This snapshot covers the 93 glyph-lookup and 127 event-registration
addresses. The existing worker received a separate catalog of 78
byte-checked addresses from the second GUI registration block and
the next callback.

## 2026-11-11 — Diode/Buzzer callback instruction index

The coordinator checked ten exact callback-window drafts at `0x8000d06c..0x8000d080` and `0x8000d118..0x8000d124` against both factory images. The independent ARM926 replay establishes the dispatcher and queue observations. [Replay and firmware identities](../contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-validation.json).

## 2026-11-11 — Diode/Buzzer secondary command excerpts

The coordinator queued 46 new addresses in four small catalogs covering the readiness guard, frame tail, transport edge and setting writer. All 46 exact quotes passed independent checks against the manifest-pinned V3.6 and V3.8 bytes, with zero incomplete, rejected or missing results. These are instruction extracts. The runtime evidence comes from the [separate original-code replay](../contributions/COORD-ADC-CADENCE/synchronous/control-gui-cfd0-secondary-validation.json).

## 2026-11-11 — Native sender and guard-word index review

All 52 previously queued excerpts around `0x8005fc08` and `0x8005e750` passed independent exact instruction, address and original-byte checks on both firmware images. There were no incomplete, rejected or missing excerpts. [Independent execution and firmware identities](../contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-lifecycle-validation.json).

## 2026-11-11 — USB RX and TX-clear address extracts

All 58 extracts in the RX FIFO, mode dispatch, type-3 record and TX busy-clear catalogs passed independent original-byte and instruction checks on both factory images. There were zero incomplete, rejected or missing results. [Separate runtime evidence](../contributions/COORD-ADC-CADENCE/synchronous/secondary-usb-rx-validation.json).

## 2026-11-11 — Native checkbox and timer excerpts

All 38 new extracts from the checkbox release, class delegation, nested event and timer deadline catalogs passed independent original-byte and instruction checks on both factory images. There were zero incomplete, rejected or missing results.
