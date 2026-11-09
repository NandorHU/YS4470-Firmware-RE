# Verified reconstruction components

`fast_cont.c` / `fast_cont.h` are an independently written pure-C reconstruction
of original helper0x80007c88 in both verified V3.6 and V3.8. This is the first
component in this directory, not a complete or deployable firmware.

It preserves a three-value ring, the full-history stability test, the retained
last median, the >1000 reset and the original sound-selector bands. No code from
the third-party F1C100S projects is copied into it. Physical units and call timing
remain unassigned. The caller supplies a valid index0..2 and count0..3, as tested.

Build without a board SDK, libc, allocator or peripheral definitions:

```powershell
./work/reference-compiler/ziglang/zig.exe cc `
  -target arm-freestanding-eabi -mcpu=arm926ej_s -marm -O2 `
  -ffreestanding -fno-builtin -ffunction-sections -std=c11 `
  -Wall -Wextra -Werror -c reconstruction/fast_cont.c -o work/derived/fast_cont.o
```

Compiler used: Zig0.13.0. The ARM object has no relocations in this function's
code section. `tools/trace_fast_cont_filter.py` executes this compiled C on an
explicit Unicorn ARM926, separately from the original binary helper, and checks
every persistent state update and selector against an independent Python model.
The original helper also runs into the validated sound gate and PWM code with
inert MMIO shadows. See `tools/FAST_CONT_FILTER.md` and the evidence JSON.

This component requests a sound selector; hardware enable settings, PWM output,
UI formatting, parser admission and scheduling remain separate responsibilities.

The later original-caller experiment (`tools/RESULT_FRESHNESS.md`) shows an
accepted argument range0..999 and rejection paths that bypass this helper while
preserving its state. Its standalone>1000 reset is not the full caller policy.
Repeated uses of a stored result can fill the ring in the bounded refresh model;
this component does not certify that its calls represent fresh UART samples.

## Timed measurement-FSM component

`fsm_timeout.c` / `fsm_timeout.h` independently reconstruct timed states2/3/4
of original entry0x80004490. They use an explicit semantic struct, not the original
RAM layout. The pure step takes an RX observation and raw tick snapshot, returns
requested tick/GPIO effects, and performs no actual I/O or critical section.

```powershell
./work/reference-compiler/ziglang/zig.exe cc -target arm-freestanding-eabi -mcpu=arm926ej_s -marm -O2 -ffreestanding -fno-builtin -ffunction-sections -std=c11 -Wall -Wextra -Werror -c reconstruction/fsm_timeout.c -o work/fsm-timeout/fsm_timeout.o
```

The function's code section has no relocations. On explicit ARM926,12,914
original/Python/compiled-C state cases agree. Separate original getter/setup/
cache/tick-prefix probes bring the report to13,302 checks. See
`contributions/COORD-FSM-TIMEOUT/README.md` and its JSON evidence.
The original GPIO and critical bodies execute on inert shadows; the state1 UART
send remains modeled. Other FSM states, full scheduling and physical units are
not reconstructed here. No third-party reference driver code is copied.


## 2026-11-09: original UART correlation proof

uart_transport.c/.h add two independently written pure-C data components: bounded source framing with additive checksum and RX status/count-gated byte append. The ARM object is compiled separately and executes independently from original code;12,704 original/Python/C cases pass across both factory versions. These functions are not MMIO drivers, complete UART framing protocol or request correlation. Proven domain excludes corrupt signed RX counts, overlapping buffers and the original source-count+1 wrap at UINT_MAX. See ../contributions/COORD-ADC-CADENCE/uart/README.md for build commands, exact hashes, code-section relocation checks and limits.
