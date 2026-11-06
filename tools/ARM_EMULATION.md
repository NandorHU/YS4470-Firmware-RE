# Bounded ARM926 emulation

Install `analysis-requirements.txt` in a project-local environment. In the
current workspace the installed packages are under `work/analysis-python`:

```powershell
$env:PYTHONPATH = "$PWD\work\analysis-python"
python work/re_tools/test_emulation_stack.py
python work/re_tools/emulate_state5_parser.py `
  --input 'V3.6=<local original V3.6 path>' `
  --input 'V3.8=<local original V3.8 path>' `
  --out evidence/state5-arm926-emulation.json
```

The harness checks original image SHA-256 values, executes the actual bytes
at `0x80004738..0x800047bc`, and selects Unicorn's `UC_CPU_ARM_926` model. It
maps the code/literal page and the control, result, and UART RX RAM pages.
The RX page is guest-read-only; code is guest-read/execute-only. MMIO and
all other guest addresses are unmapped. Writes are restricted to control
byte `+1` and the result value/selector fields. Execution stops before the
shared FSM epilogue at `0x80004518` and is limited to 64 instructions per case.

The inputs assume state-3 frame admission already succeeded. `r12` points to
the synthetic RX buffer, `r1` is command `0x1b` or `0x1d`, and `r7=0` is
validated against the factory prologue at `0x800044c0`. The harness excludes
UART transport, ADC conversion, interrupt handling, and physical timing.

## Functional reconstruction of this slice

1. Form signed little-endian 24-bit value from RX bytes 1..3.
2. Command `0x1b` forces selector zero; `0x1d` clamps RX byte 4 to 0..6.
3. If control byte `0x805aae8d` was nonzero on entry, decrement it and leave
   both result fields unchanged, including the case where it becomes zero.
4. Otherwise, if control word `0x805aae94` is 13 or 14, compare the sign-extended
   result **as unsigned** against 5001. A match publishes `0x007fffff` and
   selector zero. Thus every negative 24-bit value also takes that branch.
5. Other admitted cases publish the sign-extended result and selector.

The reference function is deliberately arithmetic/conditional Python; the
emulator executes original instructions. Default vectors combine numeric
boundaries, exhaustive selector/control/countdown byte tests, and 512
deterministic random inputs: 2,976 cases per original version. Every one of
the 34 instruction addresses is visited; this is not exhaustive path coverage.

The installed Capstone distribution reports 5.0.9 while its runtime string
reports 5.0.7. Both identities are recorded in reports rather than treating
the package version as the runtime string. Unicorn is 2.1.4.

No input binary is bundled with this code. Reports contain hashes, assembly,
synthetic examples, and verification results, not device-specific flash dumps.
