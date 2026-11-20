# RTOS tasks and timing (V3.8 / beta.4 image), 2026-11-20

Static disassembly of the original task-creation block 0x80005930..0x800059f8 and each task's loop.
Earlier executed evidence: delay/wake, tick IRQ, Timer0 setup (MEMORY_MAP.md 2026-11-10 sections).

## Kernel identification (static; fingerprints)
0x80061d5c is FreeRTOS `xTaskCreate(entry, name, depth_words, param, prio, handle)`:
TCB 0x54 bytes, stack = depth·4 bytes filled with 0xA5, name copied up to 8 bytes,
`prio >= 4 → 3` (configMAX_PRIORITIES = 4), event-list value `4 − prio` (0x80061e14),
global task counter at scheduler 0x805abbbc+8. Higher number = higher priority.
0x80060fbc is `vTaskDelay(ticks)` (suspend-all, insert into delayed list, resume, yield if needed).

## Tick
Timer0 setup 0x800617ec calls `timer_configure(0, 1000, 1)` (0x800071a0), which programs interval
24000 and control 7 (enable, auto-reload, OSC24M, /1): **1 tick = 1 ms** (configTICK_RATE_HZ = 1000).
This rests on the F1C100s 24 MHz oscillator; it is not a measurement on the device.

## Tasks
| Prio | Task | Entry | Stack | Loop (ms) |
|---:|---|---|---:|---|
| 3 | GaugeCmdTask | 0x80003dbc | 16 KiB | startup cmds 0x09 (`58 03`), 0x13 (`59 00`); then service 0x80005b6c forever, `vTaskDelay(1)` inside service → ≈1 ms |
| 2 | GUI_Task | 0x800031e0 | 16 KiB | init, `vTaskDelay(1000)`, then loop 0x800085e0, 0x800085c4, 0x8005ea28, 0x8004092c, `vTaskDelay(5)` |
| 1 | MainADCTask | 0x80005a78 | 8 KiB | 0x80005a8c every 5 ms: reads two floats via 0x800066e8 into RESULT+8/+0xc (thresholds 0.1 / ≈3e-4); not the meter chip UART |
| 1 | KeyTask | 0x8000551c | 8 KiB | key sample → 0x805abb9c, `vTaskDelay(50)`, then sound countdown RESULT+0x50 −1 and expiry off |
| 0 | UsbChargeTask | 0x8000807c | 8 KiB | 0x80007fb4, delay 20, 0x80007de0, delay 20 |
| – | init task | – | – | 0x80002804 + `vTaskDelay(1000)` forever |

## Consequences for diode mode (ms assume 1 tick = 1 ms)
- The meter-chip transaction, parser and the E2 reply-path sound decision (profiles 1–4) run in the
  **highest-priority** task. GUI rendering (prio 2) cannot delay them; rendering itself can be delayed.
- Display refresh is an LVGL timer inside GUI_Task (period 25 at Highspeed=1; model units = ms).
- Sound countdown is decremented only by KeyTask every ≈50 ms: short tone hold ≤ 13 × 50 = 650 ms after
  the last short reading; junction one-shot = countdown 2 → 50–100 ms beep. Release (≥ 700 mV)
  switches off immediately only while countdown > 3.
- Mode entry: setup command, ~50–100 ms inter-command wait in the FSM, second setup command, then two
  discarded replies before the first published diode value.

## What this does and does not explain
The firmware order is reply → (sound decision, same task, highest priority) → later GUI render.
A tone that is audibly later than the display is therefore not produced by task priorities.
The remaining firmware-consistent explanation: the tone needs raw < 100 (0.100 V), while the display
shows every intermediate value. If the reading after contact decays through 0.6…0.1 V over several
conversions (chip averaging/settling), the display moves at once but the short tone waits for the
crossing below 0.100 V. To check on hardware: watch whether the displayed value passes through
intermediate values before 0.000 when shorting the probes.
