# Reverse-engineering progress

**Last verified update:** 2026-11-04  
**Development branch:** `re/2026-11-04-pyghidra-fel`

## This session: verified results

- A bounded PyGhidra inventory pipeline now runs with Ghidra 12.1.4, PyGhidra 3.1.0, Jpype1 1.5.2, language `ARM:LE:32:v5t`, and link base `0x7fffffe0`. It exports seeded-function assembly, decompiler output, direct calls, fixed byte-window hashes, and evidence/confidence fields. It intentionally does not represent a full automatic ARM/Thumb analysis.
- The V3.8-to-Beta3 raw equal-layout comparison found **65 changed ranges totaling 931 bytes**. Therefore Beta3 must not be described as a two-patch firmware.
- At V3.8 `0x80006e80`, Beta3 replaces the factory sound-table load with a helper at `0x80010754`. The helper retains the original `ldrh`, and only when its caller return address equals `0x80003a78` it substitutes `r6 = 0x529` (1321 decimal). The target is the previously identified sound-gate call at `0x80003a74`. This proves a call-site-specific sound-parameter override; it does **not** yet prove a physical buzzer frequency or a shorter acoustic delay.
- At V3.8 `0x800037fc`, Beta3 calls helper `0x80060130` instead of loading `[r7,#0x1c]` directly. The helper restores that original load into `r0` and records value/context changes in a new state block rooted at `0x800600ac`. The exact UI/measurement semantics remain a hypothesis.
- A local V3.6 original was not present in the currently accessible workspace. The tooling supports it; no V3.6-to-V3.8 conclusion has been invented.
- The repository contains a deliberately restricted FEL helper. Its offline policy/parser self-test passed. It can issue only `sunxi-fel --list` and `sunxi-fel spiflash-info`; it contains no flash write, RAM execution, arbitrary memory access, boot, or erase operation.
- No USB/FEL operation was executed in this session. Existing 2026-11-02 project artifacts record an F1C100S FEL enumeration and a Winbond 16 MiB SPI-flash identification; that record is historical, not a claim about current device state.

## Exact continuation point

1. Trace the remaining Beta3 changes around `0x800045e0`, `0x8000461c`, and `0x80004738` through the request/reply FSM. Classify each as protocol acceptance, measurement-state change, or unrelated behavior before making latency claims.
2. Obtain or register the original V3.6 image in a local non-public input directory, validate its SHA-256 locally, then run `tools/pyghidra_inventory.py` and `tools/compare_inventories.py`. Do not upload original firmware binaries.
3. Convert the confirmed static call-site sound override into a bounded emulation experiment only after identifying the surrounding parameter contract.
4. Perform a fresh live FEL probe only when the device is intentionally connected; retain its captured output as dated evidence. Never expand the probe to writing, arbitrary memory reads, or RAM code execution without explicit approval.

See `evidence/2026-11-04-pyghidra-beta3-compare.json` for machine-readable session evidence, `FUNCTION_DATABASE.json` for the cross-version function database, and `FEL_ANALYSIS_PLAN.md` for the safety-gated hardware plan.
