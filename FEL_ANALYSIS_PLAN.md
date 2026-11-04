# FEL-based analysis plan

## Established evidence and scope

A dated project artifact from 2026-11-02 records two non-destructive FEL observations:

- `sunxi-fel --list` reported an **Allwinner F1C100s** device.
- `sunxi-fel spiflash-info` reported Winbond manufacturer `EFh`, model `40h`, size 16 MiB.

Those observations establish that FEL worked at that time. They do not establish a current connection, a live firmware debugger, DRAM initialization, or runtime memory capture.

The repository helper `tools/fel_readonly_probe.py` is intentionally constrained to those two operations plus an offline parser/policy self-test. It rejects unverified executables and multiple/unexpected devices. It has no flash write/erase, bootloader, RAM-write, RAM-execute, arbitrary read, or firmware-install capability.

## Static map used for planning

| Region | Basis | Status for automatic live access |
|---|---|---|
| `0x00010000..0x00010fff` | F1C100S Linux device tree maps SRAM-D/OTG SRAM here | Not approved: retained boot-ROM/FEL state is unknown |
| `0x01c00000` system control | F1C100S Linux device tree | Static documentation only; no automatic read |
| `0x01c20000` CCU, `0x01c20400` INTC, `0x01c20800` PIO, `0x01c20c00` timers | F1C100S Linux device tree | Static documentation only; no automatic read |
| `0x01c25000`, `0x01c25400`, `0x01c25800` | UART0/1/2 in F1C100S Linux device tree | Static documentation only; no automatic read |
| `0x80000000` | Static firmware eGON load address | Not assumed initialized in FEL; no automatic read |

Sources: [F1C100S datasheet](https://linux-sunxi.org/images/b/ba/F1C100s_Datasheet_V1.0.pdf), [Linux F1C100S device tree](https://code.googlesource.com/linux/torvalds/linux/%2B/3c8f504b3a486e4e984ac8dc619eba3afa24cec4/arch/arm/boot/dts/suniv-f1c100s.dtsi), and [sunxi-tools FEL SoC notes](https://github.com/linux-sunxi/sunxi-tools/blob/master/soc_info.c).

## Safety-gated sequence

1. **Offline only (complete):** identify expected VID/PID output syntax, validate the exact `sunxi-fel` executable digest, and test output parsers. No device I/O.
2. **Live identification (allowed when intentionally connected):** run only `--list`, then `spiflash-info`; store timestamped stdout/stderr. Stop if device identity or SPI identifier differs.
3. **Read-access design review (not authorized by this plan):** before any memory command, determine exact FEL protocol semantics for the installed sunxi-fel build, consult ROM/SRAM reservations, specify target range/length, and obtain explicit approval.
4. **DRAM assessment (not authorized):** do not infer that `0x80000000` is valid merely from a firmware header. Require an independently evidenced initialization path.
5. **Correlation:** compare only observed, dated, reproducible data with static code. FEL is not normal-firmware run-control or a runtime debugger.

No physical firmware installation, SPI flash write/erase, bootloader change, RAM code execution, or unreviewed memory operation is part of this plan.
