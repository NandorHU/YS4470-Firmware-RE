# F1C100S references (2026-11-07)

The four upstream repositories are downloaded into separate local checkouts.
They are analysis inputs, not code added to the reconstructed YS-4470 firmware.
`sources.lock.json` records exact revisions and selected source-file hashes.
The fetch script does not execute upstream build/flash/install scripts.

| Repository | Pinned revision | License and examined architecture |
|---|---|---|
| [fnirsi-1013d-mcp](https://github.com/mikljohansson/fnirsi-1013d-mcp/tree/fa8377b2b1d148f8596a8befe638df79062c2bd8) | fa8377b2b1d148f8596a8befe638df79062c2bd8 | Root GPL-3.0 text. `firmware/scope` application, eGON.EXE startup, interrupt/timer code, FPGA acquisition and USB/MCP host tooling. Board-specific FPGA/ADC and pin wiring do not transfer to YS-4470. |
| [F1C100s_projects](https://github.com/nminaylov/F1C100s_projects/tree/c11422e99c9f33e8419a5ac4dcab6684c8d38296) | c11422e99c9f33e8419a5ac4dcab6684c8d38296 | Root GPL-3.0 text; component notices still apply. ARM926 vectors/cache code, register headers, low-level drivers, DRAM/linker setup and simple-loader examples. PWM/GPIO/timer/UART/clock C files were actually cross-compiled. |
| [F1C100s_info](https://github.com/nminaylov/F1C100s_info/tree/ec42b9b4147070b4277e86d12324d5cd0662cd1a) | ec42b9b4147070b4277e86d12324d5cd0662cd1a | No root license found. Documents, upstream BROM dump and reverse-engineered closed-SDK library material. Eight existing SDK objects were read as comparison inputs; they are not our builds and are not redistributed here. |
| [f1c_nonos](https://github.com/minilogic/f1c_nonos/tree/73933dbb56d2cbdeb1f260a484bb7c525866616f) | 73933dbb56d2cbdeb1f260a484bb7c525866616f | No root license found. README disclaimer is not treated as a reuse license. Bare-metal `drv`, boot/DRAM/MMU code, USB, display, SPI/TWI/UART; bundled libraries have separate notices. Header annotations are useful cross-checks, but contain inconsistencies. |

Review scope: repository structure, root licensing, README/build architecture,
startup/vector examples, selected peripheral headers and implementation files.
This does not claim a complete audit of all source, PDFs, FPGA or USB code.

## Reproduce the input acquisition

From the YS-4470 repository root:

```powershell
./tools/fetch_f1c100s_references.ps1
```

The script checks the origin and exact detached revision. The analyzer also
rejects dirty reference checkouts. Source copies and their `.git` directories
are ignored locally; the lock, hashes, derived register map and our tools are
versioned. No upstream project is flashed or run on hardware.

See [the subsystem map](F1C100S_REFERENCE_MAP.md) and
[the analysis workflow](../../tools/F1C100S_REFERENCE_ANALYSIS.md).
