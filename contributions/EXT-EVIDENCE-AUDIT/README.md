# Local source review — coordinator-reviewed experiment

The user asked to use the installed local LLM alongside the primary Codex agent.
This task runs on its own external branch. The main branch is read-only.

Six source-cited reviews ran on local qwen2.5-coder:14b via loopback
http://127.0.0.1:11435. They generated3,065 tokens in77 seconds of model requests.
All six responses were complete JSON. Of24 citations,15 were exact,6 could be
located by a unique exact quote, and3 could not be grounded. Citation repair
does not establish semantic truth.

Coordinator review confirmed6 existing facts and7 already documented limits;
11 proposed findings were rejected. No new firmware claim was accepted.
A test-only emulated unexpected counter store is rejected by the getter write
guard, contrary to one model suggestion. Originals remain unchanged.

The previous independent31-task profile batch is preserved in its own workspace.
All source/manifest hashes matched, but22 responses ended at the token limit.
Its binary-build provenance remains unknown. It is not a verified explanation
of Base/highspeed performance.

## Actual adaptation and limits

LESSONS.md contains checked examples/rules. run_taught_review.py appends them to
each new request. This is in-context adaptation: no model weights were trained.
The tiny two-case check improved from0/2 to1/2; it is not a broad accuracy result.
The remaining unsigned-equality mistake prevents treating the model as a
reliable independent ARM analyst. No end-to-end productivity gain is claimed.

Source extraction, indexing and short drafting may be useful; firmware semantics,
address arithmetic, hypotheses and test proposals require independent checks.
The primary agent continues the binary work. Additional local work must be a
small owned task and must earn its review cost.

## Reproduce or inspect

- local_review_worker_v3.py: loopback-only worker, no model tool execution.
- jobs/2026-11-08-v3/manifest.json and snapshots/: frozen inputs and hashes.
- Per-task JSON: raw unverified model responses; coordinator-review.json:
  separate tool citation resolution and semantic verdicts.
- evaluate_lessons.py / lessons-evaluation.json: same two cases before/after
  the examples, plus a test-only guard negative control.
- review_receipts.py: deterministic source checks and explicit coordinator verdicts.

Use the prepared job only to inspect the completed results; do not rerun a
completed batch. For a new assigned task create a new immutable job directory.
Then run from repository root:
python -B contributions/EXT-EVIDENCE-AUDIT/run_taught_review.py --job-dir NEW_JOB_DIR

The source records the initial probe ambiguities, subsequent strict schema and
tool-resolved numeric input. Prior attempts remain local and are not presented
as successful training. The model has no shell, Git or physical-device tools.
No paid external API is used. The existing Ollama service/config is unchanged.
