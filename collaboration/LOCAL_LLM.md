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

These are researched options, not installed integrations or promises of a gain.
Before weight training, curate independently checked ARM/source-to-explanation
pairs. Split evaluation by function/byte identity so matching V3.6/V3.8 bodies
do not leak between training and test. Do not train on uncorrected local drafts.
GPU memory suitability and post-training accuracy must be measured separately.

Next firmware task remains the coordinator-reserved COORD-ADC-CADENCE.
