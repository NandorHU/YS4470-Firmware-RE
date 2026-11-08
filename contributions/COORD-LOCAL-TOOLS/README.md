# Local tools installed and exercised — 2026-11-08

I installed promptfoo0.125.1, DSPy3.4.1 and MCP2.3.0 under
`work/local-llm-tools/`, using existing Python3.12.10 and Node24.22.1.
Existing REA6.8.0, Ghidra and Ollama were retained. No weights, global service,
driver, device firmware or paid inference API was changed.

## Actual results

- `condition-fixtures.json`:70 synthetic ARM926/Unicorn oracle checks,
  four training branch mnemonics and six held-out mnemonics.
- DSPy JSONAdapter:6/6 baseline and6/6 with LabeledFewShot(k=4),12 provider
  calls in6.265s. Examples did not improve this already passing small test.
- promptfoo:4/6 plain and6/6 with the four examples. Wrong-answer and token-cutoff
  negative controls were rejected. These scores are not comparable to DSPy's
  different structured prompts and do not establish general improvement.
- REA: the local Coder14B made a real call through DSPy ReAct → MCP → REA.
  One32-byte original-image observation, three model calls, correct address and
  evidence ID. File SHA-256 and the window were checked deterministically.
  Four mutation/command operations were rejected by the adapter policy.

The REA adapter exposes **one fixed getter evidence view**, not unrestricted
REA tools. Its ARM assembly comes from the existing hash-guarded export.
REA's Windows Ghidra P0 admission does not support this raw ARM926 image;
the REA observation is file identity/entropy, not native ARM decompilation.
Entropy does not establish encryption, code or a peripheral role.

`install-report.json` records pins and package archive hashes. Initial failures
are retained there: slow legacy DSPy routing, a missing native `/v1` suffix,
an MCP field-name correction and a promptfoo assertion formatting mistake.
The promptfoo provider outputs were regraded offline, with no repeat inference.
Their original response-file hash is in `promptfoo-results.json`.

## Reproduction

Use `setup.ps1 -NodeDirectory <existing-node-directory>` for an isolated reinstall.
`requirements.lock.txt` and `package-lock.json` pin dependencies. The setup script
has been syntax checked; it was not used to reinstall already working packages.
Copy `machine.example.json` to `work/local-llm-tools/machine.json` and fill local
REA/Ghidra/Java/Node paths. Machine-specific paths and installed packages are
not published. npm skipped an esbuild postinstall; the exercised CLI/assertion
paths worked without changing global script policy.

`run.ps1 versions` checks the installed clients. `run.ps1 dspy`, `promptfoo`,
and `rea` are one-time owned calibration/smoke commands and refuse completed
outputs. Do not repeat them for daily work. Native DSPy uses
`http://127.0.0.1:11435/v1`; promptfoo uses the Ollama root on11435.
Telemetry/sharing/update checks are disabled in the launcher.

For new firmware work, use the [hash-bound packet workflow](../COORD-FUNCTION-PACKETS/README.md)
and a newly frozen, owned manifest. Checked lessons are in-context preparation,
not weight training. Unsloth/LlamaFactory, embeddings and heavy emulator stacks
were not installed: no measured gap in this bounded task required them.
