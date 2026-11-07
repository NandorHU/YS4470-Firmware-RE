# Original INTC and timer reconstruction

Reference register anchors from the pinned F1C100s_projects, FNIRSI and nonos
sources were applied to original YS-4470 ARM, not copied as replacement drivers.
The YS dispatch architecture differs from the reference examples.

## Proven entry points

| Entry, both originals | Behavior |
|---|---|
| 0x80005260 | Read INTC_VECTOR at0x01c20400, dereference that returned pointer, BX to the loaded handler. The test stops at its target, including ARM/Thumb interworking. |
| 0x80005274 | Initialize INTC_BASE_ADDR once to0x805ab944 using flag0x805ab940. Mode0 exchanges a slot at0x805ab9e8; modes1..7 exchange at0x805ab944. Modes>=8 update priority/enable without changing a handler. |
| 0x800071a0 | Configure channel low8(r0): reset control, set source bit2/reload bit1, interval=low32(24*r1), IRQ enable only if low8(r2)==1. Does not set timer enable bit0. |
| 0x8000725c | Set selected timer-control bit0; preserves other bits. |
| 0x8005bf54 | Read timer IRQ status0x01c20c04 and write old|1. Inert shadows do not model real interrupt-clear semantics. |

Registration replaces two priority bits per IRQ and sets its enable bit.
Priority input is not masked to two bits; diagnostic tests show high values can
spill into adjacent priority fields. Use validated priority0..3 and IRQ0..40;
out-of-range IRQ/channel indices were not executed. Mode0's table role remains
unnamed. A second init call with a nonzero flag preserves the existing base.

## Timer/RTOS linkage

Original startup slice0x800617ec..0x80061818 executes configure(0,1000,1),
register(mode1,IRQ13,handler0x8005bf54,priority3), then enable timer0. Final
timer0 control=7 and interval=24000: nominal1kHz if its source is24MHz. The test
stops before the RTOS context-restoring call at0x800021fc.

IRQ-bridge slice0x8000230c..0x80002364 tests INTC pending bit13. If absent, the
real vector dispatcher runs and the selected handler is a stop boundary. If
present, it calls tick routine0x80061fa4, conditionally calls0x800612f8 if the
tick returns nonzero, then writes0 to INTC pending0 and1 to timer IRQ status.
Tick/scheduler bodies are explicit stubs in this slice. The registered timer0
status helper0x8005bf54 is distinct from the directly called tick routine.

Startup vectors at0x800023b0 and CPSR/vector-copy code are static context,
not a claim of full exception/context-switch execution. Nominal tick setup does
not prove measurement response cadence, queue timeout units or acoustic delay.

## Validation

`tools/trace_intc_timer_path.py` checks exact non-stack writes, table/RAM
preservation, return values, stack/callee-saved registers, register-index
boundaries, ARM/Thumb targets and startup linkage on UC_CPU_ARM_926.

Per original:1652 registration,164 dispatch,360 configuration,24 enable,
four status-update,18 bridge and one startup case. Total across V3.6/V3.8:
**4446 cases**, identical result fingerprints and zero failures. PIO/INTC/timer
are inert memory shadows; no device access or clock progression occurs.
Real PyGhidra names/exports all five entries; the guard rejects mismatched input
hashes/windows and preserves existing analyst names/comments.

```powershell
$env:PYTHONPATH="$PWD\work\analysis-python;$PWD\tools"
python tools/trace_intc_timer_path.py `
  --input 'V3.6=<original path>' --input 'V3.8=<original path>' `
  --out evidence/2026-11-07-intc-timer-path.json
```

Evidence: `evidence/2026-11-07-intc-timer-path.json` and
`evidence/2026-11-07-intc-timer-ghidra.json`. Next: bound the tick/scheduler
bodies and the consumer of FSM timeout field+0x30 before assigning timing units.
