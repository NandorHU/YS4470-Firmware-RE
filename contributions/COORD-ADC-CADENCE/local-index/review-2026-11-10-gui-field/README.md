# Resident Ollama instruction-index review, 2026-11-10

This incremental snapshot covers 201 new drafts in 101 batches from
the GUI field and constructor contexts. The coordinator checked the
original bytes, frozen packet identity and exact instruction text
against the factory V3.6 and V3.8 images. All 201 passed.

The audit excluded the addresses already checked in both earlier
snapshots. Pass each earlier snapshot directory with a separate
`--baseline` argument to the
[reusable audit script](../review-2026-11-10-delta/audit_ollama_index_queue.py).

- [Review receipt](review.json)
- [Checked ARM instruction index](accepted-arm-index-01.tsv)
- [Original execution evidence](../../synchronous/gui-field-provenance.json)
