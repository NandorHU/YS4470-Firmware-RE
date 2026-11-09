# Tools, setup and commands

This inventory distinguishes software actually exercised from requested or
unavailable options. LOCAL_ENVIRONMENT.json in the **local transfer kit** records
exact existing Windows paths, file hashes and detected versions. It is not a
portable installation or an account-credential export.

## Verified working environment

| Tool | Observed version | Actual use and limit |
|---|---|---|
|Windows PowerShell / Python|Python3.12.10|Deterministic hash/byte checks, orchestration, JSON evidence, scripts and tests|
|Git for Windows|2.52.0.windows.1|Public mirror, source checkout, history/bundle/archive; GitHub integration previously also used connected Git-data API with expected-head lease|
|Ghidra / PyGhidra|12.1.4 /3.1.0|Bounded raw ARM import, local CFG, assembly/decompiler/call evidence; preserve analyst names/comments, no blind full-analysis naming|
|Java|Temurin21.0.13+9|Ghidra runtime; isolate user profile/temp settings|
|Capstone|distribution5.0.9, runtime reports5.0.7|ARM instruction decoding; report both version observations honestly|
|Unicorn|2.1.4|Explicit UC_CPU_ARM_926, original ARM instructions and independent compiled C; modeled leaves/MMIO/scheduling, no complete meter emulation|
|pyelftools|0.32|ELF/relocation checking for freestanding ARM components|
|Zig|0.13.0|Cross-compiles freestanding ARM926 C. Use exact existing build commands in evidence/scripts, not a different ARM ABI by assumption|
|Node / REA|24.22.1 /6.8.0|REA file identity/hash/entropy observation and fixed read-only adapter. Its Windows Ghidra P0 admission did not support this raw ARM926 image|
|Ollama|0.40.15|Existing signed portable server, loopback11435, no cloud or model download|
|Local models|qwen2.5-coder:14b; qwen3.5:9b|Small owned source-index/draft tasks. No autonomous Git/shell/device tools or trained adapter|
|promptfoo / DSPy / MCP Python|0.125.1 /3.4.1 /2.3.0|Completed bounded local calibration, strict structured output and fixed evidence adapter; not daily rerun tasks|
|PyInstaller / Tk|build lock; Tcl8.6.15 in package|English Windows installer including runtime and native dependencies. CI/mock/resource checks passed; actual visual/physical test not established|
|sunxi-fel / Zadig|pinned installer/dependencies.lock.json|Historical FEL observation and packaged native tooling. Packaged FEL differs from the older physically used executable; do not claim physical equivalence|

Rizin/rz-diff, Binwalk, ImHex and gh were not found on PATH in the migration
check; that is not proof that no portable copy exists. angr/Qiling/OpenOCD/JTAG
and Unsloth/LlamaFactory trainers were not installed for the proven workflow.
Version Tracking was requested earlier but no completed certified run is claimed.
Do not install all tools or retrain weights merely to reproduce this inventory.
Actual comparison uses bounded hash/relocation/Capstone/PyGhidra evidence.

Tools used through the assistant connection also included GitHub repository/file/
issue/PR/commit/Release APIs and Git-data commits with a branch-head lease,
native execution/file editing, and earlier attempted computer-use preview.
Browser/app controls did not establish a successful installer visual test.
No image-generation or paid external inference API was used for these results.
Tool/plugin connections belong to the old account and must be reconnected.

## Same PC: reuse the installed software

The kit includes LOCAL_ENVIRONMENT.json and LOCAL_MODEL_HEALTH.json. The latter
is a point-in-time localhost observation; an unloaded model is not a dead server.
Do not copy the old workspace over a fresh checkout. Use the ready-workspace
next to the kit, or clone the Git bundle. The old workspace has no .git.

From a new checkout, dot-source this helper with the actual kit path:

```powershell
. .\migration\2026-11-09\set_same_pc_environment.ps1 -Inventory 'C:\path\package\LOCAL_ENVIRONMENT.json'
python -B -c "import capstone,unicorn,elftools; print(capstone.__version__,unicorn.__version__)"
```

The helper only sets process environment variables from existing verified paths.
It does not install packages, connect to a device or launch an LLM. Recreate
missing settings explicitly on another PC. The old original-image Ghidra projects
are reusable, but the manual YS4470.gpr is a **modified/mapped program** and must
not substitute for a hash-verified original raw import.

## New PC: minimal offline-analysis dependencies

Install your own Python3.12, Git, JDK21, Ghidra12.1.4 and the pinned Python packages
only as needed. These are setup commands, not commands executed during migration:

```powershell
python -m venv work/analysis-venv
.\work\analysis-venv\Scripts\python.exe -m pip install -r tools/analysis-requirements.txt
.\work\analysis-venv\Scripts\python.exe -m pip install pyghidra==3.1.0
$env:JAVA_HOME='C:\tools\jdk-21'
# For commands that use Ghidra, supply its actual directory explicitly.
```

The C reconstruction also needs Zig0.13.0. The local LLM is optional for binary
analysis. Its multi-GB model weights are not in the transfer kit; reuse the same
machine's model directory or install them separately under applicable licenses.
Installer build dependencies have a separate installer/requirements-build.lock.txt;
no need to install those merely to analyze ARM or use the packaged installer.
Reference sources are independently fetched using tools/fetch_f1c100s_references.ps1
and references/f1c100s/sources.lock.json. Preserve license and NOTICE.md boundaries.

## Small offline readiness checks

The existing reports are already evidence. A new checkout can smoke-test these
without a device or model call; do not rerun all historical matrices routinely.

```powershell
python -B -m unittest discover -s patcher -p 'test_*.py' -v
python -B contributions/COORD-ADC-CADENCE/synchronous/trace_synchronous_helper.py --repo . --out-dir work/migration-smoke/synchronous
python -B contributions/COORD-FUNCTION-PACKETS/validate_packets.py
```

The first is14 offline patcher tests; the second40 startup-helper cases. The
source scripts can otherwise default to committed report directories, so prefer
an isolated --out-dir for new executions. Patcher commands inspect/apply/revert
only create files and never flash; use a separate nonexisting output path.

Six ready-made function packets already contain assembly/decompiler/CFG data.
Index without starting Ghidra or an LLM:

```powershell
python -B contributions/COORD-FUNCTION-PACKETS/evidence_index.py --db work/function-packets/new-index.sqlite --build
python -B contributions/COORD-FUNCTION-PACKETS/evidence_index.py --db work/function-packets/new-index.sqlite --hash 7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290 --address 0x80003dbc
```

For a fresh Ghidra export, first inspect export_packets.py --help and its README;
it expects original-image projects prepared by tools/pyghidra_inventory.py with
--labels-only --reference-report contributions/COORD-FSM-TIMEOUT/fsm-timeout.json,
both --input VERSION=PATH arguments, --ghidra and --out-dir work/fsm-timeout/ghidra.
Set JAVA_HOME and isolated JAVA_TOOL_OPTIONS/APPDATA as in that README. Use
language ARM:LE:32:v5t, link base0x7fffffe0, broad analysis disabled by default.
Cache keys include firmware/exporter/project identities. Never rename guessed
functions automatically, discard manual comments, or treat decompiler text as proof.
Raw BL matches are candidates; complete_local_cfg is local, not transitive/global.

## Local model: health, restart and task policy

Server: http://127.0.0.1:11435. Native Ollama API /api/version,/api/tags,/api/ps;
DSPy/OpenAI-compatible base http://127.0.0.1:11435/v1. promptfoo uses the root.
Reviewed coder digest:
`9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849`.
Other installed qwen3.5:9b digest:
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.

The owner explicitly requested server startup. It was started hidden with
OLLAMA_MODELS pointing at existing weights, OLLAMA_NO_CLOUD=1,
OLLAMA_FLASH_ATTENTION=1, OLLAMA_KV_CACHE_TYPE=q8_0,
OLLAMA_NUM_PARALLEL=1 and OLLAMA_MAX_LOADED_MODELS=1. No Windows service,
login startup, registry or new model download was added. Keep-alive30m can unload
the model while the API stays healthy. The last observation is in the local kit.

If absent on the same PC, use the reviewed helper with explicit actual paths:

```powershell
.\contributions\COORD-ADC-CADENCE\synchronous\start_local_server.ps1 -OllamaExe 'C:\existing\local-ai\runtime\ollama.exe' -ModelDirectory 'C:\existing\local-ai\models' -StateDirectory "$PWD\work\ollama-state"
```

It verifies executable SHA/signature and loopback, avoids duplicate launch,
and never pulls/stops models. Executable SHA:
`544216ca2082b8bc19b4ba94b513f0098fa06774b232f3c140090e3449e322a5`.
The already-running helper path was checked; initial actual native launch was
equivalent to its cold-start path, which was not separately repeated.

Read collaboration/LOCAL_LLM.md and contributions/COORD-FUNCTION-PACKETS/LESSONS.md.
For UART tasks also use synchronous/local-heldout/LESSONS-UART.md. The policy:
- New small owned scope with immutable source/lesson/firmware hashes and a new manifest.
- Model gets source and structured extraction/index question; exact arithmetic,
  hashes and line lookup are deterministic. No arbitrary shell/Git/device tools.
- Require done=true, done_reason=stop, expected schema, exact quote grounding,
  then coordinator semantic/binary review. Valid JSON or quote alone is insufficient.
- packet_worker.py bounds attempts/checkpoints and rejects token-limit replies.
  Do not automatically expand a batch or retry reviewed/exhausted/completed jobs.
- A semantic pointer/status error was rejected even with an exact source quote:
  ISR entry73bc loads a literal; actual status read73c8. Buffer store740c follows
  count store7408. A new held-out TX-ID exercise passed after a checked lesson;
  this is in-context preparation, not changed model weights or proven general gain.

The31-task old batch had22 incomplete token-limit replies and remains quarantined.
Six prior source reviews rejected11 findings and promoted no new firmware result.
Completed promptfoo/DSPy/MCP/REA calibration and six-packet comparison are not
daily work. Their raw external snapshot is branch external/local-llm/evidence-audit-2026-11-08,
commit460405fa04971992d2d8830bac1d6ba914a927fc, included in the Git bundle.

## Native tools and hardware limits

Packaged sunxi-fel SHA:
`cc1e338a238ab99dc0ca12bdb3558d2781f9e81ed411a9b92d1c4021a67a2acf`.
Older physically used FEL SHA:
`da14ffa7243767d9c8c5579618171fde2956c4b37b82139bb519932aba6e9375`.
Their .text differs. Zadig2.9 SHA:
`4ecaa95df3da3621486a043aef8b3050b8bafe7c901402871e816229ef82039b`.
Do not assert packaged-native-tool physical validation from the old test.

FEL USB VID/PID1F3A:EFE8; expected WinUSB and known F1C100S/WinbondEF/40/16MiB.
FEL is not a running firmware debugger. Hardware state is unknown now. Offline
handoff/readiness commands require no USB probing and perform no device action.
Physical flashing/RAM execution is outside the current authorized task.
