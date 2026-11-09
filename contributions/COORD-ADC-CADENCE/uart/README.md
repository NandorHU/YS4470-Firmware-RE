# Original UART transport and delayed-reply attribution — 2026-11-08

This continues the equal-Highspeed experiment without repeating its matrix.
The new bounded task replaces its UART-send leaf with the original sender,
byte-output polling, ISR, builder, FSM, copy/clear, critical helpers and tick
getter. Both SHA-256-pinned factory V3.6/V3.8 applications execute on ARM926.
There is no physical device, UART adapter, flash write or Release change.

## Established result

A deliberately old response can be published after an original retry. The
tested path has no check that ties a response to a particular request instance.
The command header distinguishes0x1b from0x1d; it does not distinguish two
successive requests of the same command. This is a software counterexample
with a controlled byte fixture, not a measurement of its frequency on a meter.

| Synthetic counter | Original0x1d experiment |
|---:|---|
|0| State1 clears RX, sends descriptor `60` as UART writes `60 60`, starts state3/duration30 |
|30| Incomplete response selects state6 |
|31| Retry count0→1, state1 selected |
|32| RX cleared again; the same `60 60` request is sent |
|33..37| The fixture delivers the **first request's** delayed `60 32 00 00 00`; the retry has no fresh reply |
|37| Count5 and matching header admit state5 |
|38| Original parser0x800047b4 publishes raw50 |

Times are injected RTOS counter values. They are not milliseconds, conversion
times, wire timings or probe-to-beep measurements. The fixture's attribution
is known to the test; the firmware sees only received bytes.

An additional controlled interleave admits a complete old response **before
the new request is sent**: state1 releases its critical section after clearing
RX, then the ISR is explicitly invoked at0x8000456c. The old frame survives the
new send and is published. Interleaves after the first UART write at0x80005efc
and just before the timestamp getter at0x800045e4 behave the same. All injected
sites are IRQ-enabled; original RX-clear stores are checked IRQ-masked with
positive critical nesting. The host saves/restores CPU context and uses a
separate ISR stack. This establishes an explicit sequential interleaving, not
the actual exception-entry, task priority or preemption rate on hardware.

## Transport reconstruction

- Sender0x80005e84 copies source bytes to0x805b4154, appends their additive
  sum modulo256, and calls selector-byte-output0x80006dc8 with selector2 for
  each byte. The original returns success1. Thus source `60` produces two
  UART-register writes `60 60`; this was previously a static result and is
  now executed through the real copy/sender/output code.
- Output0x80006dc8 tests bit1 at UART2+0x7c, then writes the byte as a word to
  UART2+0. The model makes readiness immediate or inserts two not-ready reads
  per byte. With readiness permanently withheld, a160-instruction probe stays
  in the original polling loop with no UART write. The FSM's post-send tick
  snapshot has not been reached. No physical stall duration is inferred.
- ISR0x800073bc tests bit2 at UART2+8, reads the low byte from UART2+0, and
  appends it at RX[count] while the tested nonnegative count is below200.
  This routine does not attach a request identifier or mark complete frames.
- RX is0x805b408c..0x805b4154 exclusive; TX buffer starts at0x805b4154.
  Receiver bounds and TX-buffer preservation are checked with canaries.

The independent [C component](../../../reconstruction/uart_transport.c) and
[header](../../../reconstruction/uart_transport.h) reconstruct the bounded
data transformations, not a UART driver. The frame API returns wire length,
while the original sender returns success1. Both are compared to an independent
Python sum/append specification. Original source counts200/201 reject; counts
0..199 emit count+1 bytes. RX tests cover counts0/1/198/199/200/201, four status
patterns and every possible byte. Arbitrary negative/corrupt RX counts,
overlapping buffers and the original count+1 wrap at UINT_MAX are outside the
established equivalence contract. The C API's safer rejection outside that
domain is not evidence of original behavior there.

## Concatenation and reset boundary

For each command, the fixture supplies two valid five-byte replies before
the FSM processes them. Count10 admits state5, and the parser consumes only
the first five bytes, publishing raw50. The second raw600 is not published.
Finalization leaves count10 and the RX bytes intact; the next builder also
leaves them intact. The next **state1** clears count/buffer and loses the
trailing reply. This corrects the initial test assumption that finalization
itself clears RX. The corrected assertion checks the observed retention and
the subsequent original clear; it does not silently drop the condition.

An old0x5e header in a new0x1d transaction instead selects state6 without a
publication. The same-header late fixture demonstrates the unresolved request
instance correlation. Neither experiment identifies the external ADC or proves
whether a repeated request restarts its conversion, queues work, or reads
buffered data.

## Evidence and validation

[validation.json](validation.json) records, **per original**:

- 208 source/alignment/payload/UART-ready framing cases;
- 6,144 ISR byte/status/buffer-edge cases;
- 92 delayed-arrival schedules (two commands,46 first-byte positions);
- 6 controlled ISR interleavings,2 concatenated-response cases,
  one cross-command reject and one blocked-TX prefix.

The12,704 transport cases compare original ARM, separate compiled ARM C and
Python. Both originals have the same transport fingerprint and identical late,
interleaved, concatenation and cross-command records. These are distinct test
units; do not total them into whole-firmware coverage. All408 observed original
instruction addresses per version are byte-pinned in the report.

[ghidra-functions.json](ghidra-functions.json) contains six actual complete
local ARM function exports (three per original),158 checked assembly instructions, decompilation,
literal/access candidates, local edges and raw BL caller candidates. New
disposable projects are used; temporary body changes are rolled back and
analyst names/comments are preserved. The raw BL matches may include data;
transitive/indirect callers are not claimed complete. Decompilation is an aid,
not an independent behavioral proof.

## Reproduce

With the pinned tools/analysis-requirements.txt installed, from repository root:

```powershell
New-Item -ItemType Directory -Path work/uart-correlation -Force | Out-Null
$env:ZIG_GLOBAL_CACHE_DIR="$PWD\work\uart-correlation\cache"
work/reference-compiler/ziglang/zig.exe cc -target arm-freestanding-eabi `
  -mcpu=arm926ej_s -marm -O2 -ffreestanding -fno-builtin -ffunction-sections `
  -std=c11 -Wall -Wextra -Werror -c reconstruction/uart_transport.c `
  -o work/uart-correlation/uart_transport.o
$env:PYTHONPATH="$PWD\work\analysis-python"
python contributions/COORD-ADC-CADENCE/uart/validate_uart_correlation.py `
  --object work/uart-correlation/uart_transport.o
```

Zig's Windows sandbox temporary-file child process failed with `Unexpected`;
the same workspace-contained compile succeeded with approved local execution.
No dependency installation was needed. The ARM ELF code sections have no
relocations and run separately from the original firmware.

For Ghidra, use the existing JDK21/Ghidra12.1.4 and project PYTHONPATH setup
documented in COORD-FUNCTION-PACKETS/README.md, with user.home and APPDATA under
work/uart-correlation/home. Create that home and its AppData/Roaming directory
first; then run export_ghidra.py --ghidra <installation>. Projects live only
under work/uart-correlation/ghidra. The first launch failed because the new
home directory was absent; creating it resolved the launch and all six exports
completed. Source generators and the earlier profile matrix are not rerun.

## Next step and limits

The more-frequent-request profiles can encounter different buffer/response
interleavings, but this result does **not** establish the user's physical Base
advantage. No correlation fix or shorter timeout is justified without external
response behavior. A late same-header frame contains no tested information
that lets the software reliably distinguish its request instance.

Next bound the receive count/read/parse interval: the ISR can append after
state3 admits5 but before state5 parses. Prove which bytes are stable and who
else can clear/reuse the shared buffer, including synchronous command helper
0x80005f14. Keep the external request restart/buffer behavior and installed
image identity open. No physical speed, new firmware Release or flash-ready
claim follows from this task.
