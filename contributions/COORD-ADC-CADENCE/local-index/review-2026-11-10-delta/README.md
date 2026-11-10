# Resident Ollama instruction-index review, 2026-11-10

This incremental snapshot covers 428 completed drafts in 214 batches
after the [previous checked export](../review-2026-11-10/README.md).
The coordinator checked packet identity, original ARM instruction bytes
and exact assembly quotes against both manifest-pinned images. All 428
rows passed. The TSV records addresses and instruction text for lookup.
The bounded original execution is tracked separately in the
[control producer replay](../../synchronous/control-producer-suffix-replay.json).

- [Review receipt and firmware hashes](review.json)
- [Checked ARM instruction index](accepted-arm-index-01.tsv)
- [Incremental audit script](audit_ollama_index_queue.py)
