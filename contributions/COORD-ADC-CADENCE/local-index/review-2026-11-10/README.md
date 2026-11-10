# Checked resident instruction index

The [audit report](review.json) covers 2,653 completed
qwen2.5-coder:14b drafts. The audit accepted 2,652 exact extracts and
excluded one incorrect identity. The export is a sorted static ARM
index with address, original little-endian bytes, assembly and local
catalog name. Both factory hashes and each file digest are in the
audit report. The model ran on the existing loopback service.

- [accepted-arm-index-01.tsv](accepted-arm-index-01.tsv) with 500 rows
- [accepted-arm-index-02.tsv](accepted-arm-index-02.tsv) with 500 rows
- [accepted-arm-index-03.tsv](accepted-arm-index-03.tsv) with 500 rows
- [accepted-arm-index-04.tsv](accepted-arm-index-04.tsv) with 500 rows
- [accepted-arm-index-05.tsv](accepted-arm-index-05.tsv) with 500 rows
- [accepted-arm-index-06.tsv](accepted-arm-index-06.tsv) with 152 rows

The auditor checks the manifest and packet hashes, exact quote and
completion reason, and independently decodes every supplied instruction
word after comparing it against both factory binaries. Dynamic claims
come from the original firmware replays linked in the task handoff.
Local catalog names beginning with `cal-` refer to shards of the
published initial catalog.

With the original local queue receipts available, reproduce the export
into a new writable directory.

```powershell
python -B contributions/COORD-ADC-CADENCE/local-index/audit_ollama_index_queue.py --state $state --repo $PWD --out work/ollama-index-review
```
