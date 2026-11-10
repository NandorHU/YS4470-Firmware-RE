# Resident Ollama instruction index

The coordinator supplies a catalog of known ARM instruction addresses.
The runner checks each word against both factory images and uses the
existing checked-lessons packet worker with the pinned local model. It
takes two new addresses per batch, writes immutable manifests and
attempt receipts, and moves directly to the next batch. Exact address
and quote checks are recorded separately from semantic review.

The seed catalog contains 2255 ARM words taken from
previously executed traces for the calibration UI, scheduler, IRQ routes,
GaugeCmdTask and measurement refresh. The runner skips addresses already
present in its frozen jobs or earlier local task manifests. A Windows
lock prevents a second worker in the same state directory. The
[startup check](resident-index-queue-smoke.json) records 30 exact
drafts checked and the rejected duplicate launch.

The service stays on the existing Ollama endpoint at 127.0.0.1:11435.
The resident queue accepts only the pinned qwen2.5-coder:14b model digest.
It waits if that service is unavailable and waits for new catalogs if
the inbox is exhausted. Runtime state, logs and raw receipts stay local.
The model supplies drafts and has no firmware, Git or shell actions.

Run the worker from a checked-out workspace with Python, Capstone and
the existing model available. The following example uses a writable
local state directory. Keep it across runs to preserve the frozen
jobs and avoid repeats.

```powershell
$state = Join-Path $PWD 'work/ollama-index'
New-Item -ItemType Directory -Force (Join-Path $state 'inbox') | Out-Null
Copy-Item contributions/COORD-ADC-CADENCE/local-index/initial-arm-catalog.json (Join-Path $state 'inbox')
python -B contributions/COORD-ADC-CADENCE/synchronous/run_ollama_index_queue.py --state $state --repo $PWD
```

For the running instance, read `status.json` and
`jobs/*/index-review.json` under its state directory. Add reviewed JSON
catalogs to `inbox` using the same schema. A file named `stop.request`
asks the worker to stop after its current batch. Remove the marker before
starting the same command to resume from saved jobs. Jobs left with an orphaned
wrapper lock require coordinator review.

## Queue, UART and UI refill

The [additional catalog](queue-uart-ui-refill.json) contains 630
previously unqueued ARM words selected from original control-queue,
UART and calibration/measurement traces. Each word was checked against
both factory binaries before it entered the resident inbox. The running
worker took the new jobs without a restart. A sample of ten completed
drafts passed the exact address and quote checks.
