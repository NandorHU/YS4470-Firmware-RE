# Reverse-engineering acceleration options

The aim of this list is to prioritize evidence quality and repeatability, not to install every available reverse-engineering tool.

## Active now

- **Unicorn 2.1.4 + Capstone:** installed under `work/analysis-python`; explicit ARM926 emulation of original V3.6/V3.8 state-5 code passed 5,952 cases. Pinned packages and reproduction steps are in `tools/analysis-requirements.txt` and `tools/ARM_EMULATION.md`. Capstone distribution/runtime report 5.0.9/5.0.7 respectively.

- **PyGhidra 3.1.0 + Ghidra 12.1.4:** installed locally from Ghidra's bundled wheel, with JPype 1.5.2. It now exports bounded ARMv5T seed inventories and compares V3.6/V3.8 without modifying source images.
- **Verified FEL read-only path:** the device can be enumerated and its 16 MiB SPI flash can be backed up with `sunxi-fel`; this is BootROM access, not a running-firmware debugger.
- **Raw-image diff and bounded ARM tracers:** use these before a broad analyzer where a narrow question is available.

## Deferred hardware capture

- **USB-to-TTL UART adapter (high value):** when physically available, begin receive-only. Connect adapter GND to low-voltage digital ground and adapter RX to confirmed UART2-TX (PE7/test point). Do not connect adapter TX or VCC initially. Use normal firmware boot, not FEL; start at 19200 8N1. A single adapter captures one direction only.
- **Second receive-only UART adapter or logic analyzer (later):** captures UART2 TX and RX simultaneously. This is the cleanest way to associate firmware command descriptors with real response frames.

## Install only when the next bounded task needs it

- **Rizin/rz-diff:** useful if a later firmware differs in many code regions. The V3.6/V3.8 raw delta is only 20 data/header bytes, so it is not currently the bottleneck.
- **Binwalk/ImHex:** useful for manual classification of the non-main regions of the verified 16 MiB flash backup. They are optional because the existing eGON extractor already identified the main image.
- **Ghidra Version Tracking:** use when pairing functions from a genuinely diverged release rather than V3.6/V3.8, whose seeded code exports are currently identical.

## Explicitly out of scope unless a new question justifies them

- angr/Qiling: too broad until a specific function contract cannot be resolved with bounded tracing or Unicorn.
- OpenOCD/JTAG: no confirmed board connector or debug-chain evidence yet.
- Any flash-write or RAM-execution FEL operation: only after an experiment image, full recovery procedure, and expected evidence are recorded.

