# Current continuation entry point

Use [collaboration/CURRENT_HANDOFF.md](collaboration/CURRENT_HANDOFF.md),
[CONTRIBUTING.md](CONTRIBUTING.md) and the live
[task registry](collaboration/TASK_REGISTRY.json) on `re/2026-11-04-pyghidra-fel`.
The original analysis inputs are documented in [original-firmware/README.md](original-firmware/README.md).
The notes below are historical 1.0 release notes, not the current research plan.

# YS-4470 1.0 - continuation notes

Repository: https://github.com/NandorHU/YS4470-Firmware-RE
Release: https://github.com/NandorHU/YS4470-Firmware-RE/releases/tag/v1.0

The README and PROJECT-STATUS.md describe the goal, current implementation, research addresses, and next steps.

I installed and tested the 1.0 continuous build. A complete 16 MiB readback matched the intended image byte for byte, and the build works well on the tested device. The physical verification record is in evidence/physical-install-1.0.json. Earlier offline manifests retain their creation-time status.

Measurement speed takes priority over continuous sound. The patch adds no sleep or extra measurement command and retains the core Beta3 timing and display optimizations. Objective physical latency measurements are still needed. A separate timed-tone fallback remains available.

Compiled firmware belongs in Release assets only. Keep full flash backups, USB logs, native external executables, and local out/inputs/tools directories private. The portable build requires an exact hash-verified Beta3 full backup. This project provides binary patches, not the manufacturer's complete source code.

Further experimental device writes and physical tests require explicit approval. Next steps are latency measurements and complete mode regression; improved accuracy, new ranges, and maximum hardware speed have not been established.
