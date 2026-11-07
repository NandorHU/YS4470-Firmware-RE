# F1C100S subsystem identification baseline

The machine-readable [register map](register-map.json) contains 34 peripheral
base definitions, 361 literal register-enum entries in 15 groups, and 428
annotated header-offset claims. Every item retains its source and line.
Offsets are relative to the corresponding block unless stated otherwise.
Reference definitions are distinct from verified YS-4470 accesses.

Primary source families, pinned in sources.lock.json:

- P: `nminaylov/F1C100s_projects`, `f1c100s/drivers/inc` and `src`.
- A: the same project's `arm926/src` and linker scripts.
- N: `minilogic/f1c_nonos`, `drv/f1c100s.h` and `drv/*.c`.
- F: `mikljohansson/fnirsi-1013d-mcp`, `firmware/scope/start.s`, timer/interrupt code.
- I: `nminaylov/F1C100s_info`, BROM and LIB_RE (provenance/rights unresolved).

| Subsystem | Register/address anchors from references | Identification method and present YS-4470 evidence |
|---|---|---|
| ARM926 CPU / exceptions | Vector offsets 0x00 reset, 0x04 undefined, 0x08 SWI, 0x0c prefetch abort, 0x10 data abort, 0x14 reserved, 0x18 IRQ, 0x1c FIQ; low/high vectors selected by CP15 c1 bit13 | A/vectors.S and F/start.s: follow vector loads, validate target mapping, CPSR mode/stack setup and exception returns. Ten CP15 instruction candidates found per original; full startup/exception ownership remains open. |
| Boot ROM / loader | I/BROM artifact named ffff0000; A/image.S and project simple_loader implement eGON headers and DRAM startup | Check eGON length/checksum and branch destination separately from vector tables. Upstream BROM binary is 65,535 bytes, so it is not asserted to be a complete 64-KiB chip dump. It is not a new YS-4470 acquisition. |
| Memory | P linker DRAM_START=0x80000000; YS raw link base independently established as 0x7fffffe0 | Track file offsets versus linked addresses. Do not transplant reference stack/heap/framebuffer locations. SRAM/ROM boundaries still require device-specific documentary confirmation. |
| Interrupt controller | 0x01c20400; VECTOR+0x00, BASE_ADDR+0x04, PEND0/1+0x10/14, ENABLE0/1+0x20/24, MASK0/1+0x30/34, PRIORITY0..3+0x60..6c | P/intc.h/.c. Trace vector read, dispatch indirection, handler table and enable bits. YS literals at 0x80005260/5290/52e4/5308 and 0x8000230c/2350 are candidates; boundaries and dispatch semantics are not yet executed. |
| Timer / watchdog | 0x01c20c00; IRQ_EN/STA+0/4, timer n control+0x10+n*0x10, interval+4, current+8; AVS+0x80/84/88/8c; watchdog IRQ+0xa0/a4, CTRL+0xb0, CFG+0xb4, MODE+0xb8 | P/timer.h/.c. Seek period writes, clock bits, IRQ acknowledgement, counter readers. YS timer-init region near 0x800071a8 remains a candidate. Original ARM926 execution proves 0x800085c4 ORs WDG_CTRL with0x14af and 0x800085e0 ORs WDG_MODE with1 (32 total cases). The reference feed routine writes a constant; YS performs read-modify-write, so byte/function identity is not claimed. |
| GPIO | 0x01c20800; banks stride0x24; CFG0..3+0..c, DATA+0x10, DRV+0x14/18, PULL+0x1c/20; external IRQ bank registers from+0x200 | P/gpio.h/.c. Recognize bank/bit arithmetic and read-modify-write masks, then trace caller pin arguments. PA2 function3 is established for sound; helper0x8000302c is executed. |
| PWM / sound | 0x01c21000; CTRL+0, CH0+4, CH1+8; channel-control stride15 bits, enable4, polarity5, clockgate6, prescaler low4 | P/pwm.h/.c plus existing original-code tests. YS 0x80006e4c→0x800060d0→0x80042d40 reaches PA2/PWM0. Off uses zero active duty while enable/gate remain set. No acoustic timing measurement. |
| Measurement ADC communication | Internal KEYADC=0x01c23400, RTP=0x01c24800; UART2=0x01c25800 | P/periph.h and UART driver. Keep internal converters separate from the known external measurement command/reply transport. UART2 framing/FSM/parser are already established in project evidence; no ADC chip identity or internal-ADC measurement role is inferred. FNIRSI FPGA/ADC acquisition code is board-specific. |
| UART | UART0/1/2=0x01c25000/25400/25800; RBR/THR/DLL+0, IER/DLH+4, IIR/FCR+8, LCR+c, LSR+14, USR+7c | P/uart.h/.c. Validate DLAB-dependent aliases, divisor writes, RX/TX polling and IRQ links. Three UART2 literal sites found; prior project evidence already proves measurement transport on UART2. |
| SPI | SPI0/1=0x01c05000/6000; GC+4, TC+8, IE/IS+10/14, FIFO ctrl/status+18/1c, clock+24, burst/count+30/34/38, TX+200, RX+300 | N/header and spi.c. Seek FIFO/counter loops, chip-select and clock gating, then bound flash storage callers. Four SPI0 literal sites found; no SPI operation is performed by this pipeline. |
| I2C/TWI | I2C0/1/2=0x01c27000/27400/27800; ADDR+0, XADDR+4, DATA+8, CTRL+c, STAT+10, CCR+14, SRST+18, EFR+1c, LCR+20 | N/header and twi.c. Recognize status-code switches, START/STOP/ACK control and byte loops. Fifteen I2C0 literal sites found; peripheral/slave roles are unassigned. |
| DMA | 0x01c02000; interrupt enable/status/priority+0/4/8; normal channels+0x100+n*0x20, dedicated+0x300+n*0x20; CFG/SRC/DST/CNT+0/4/8/c | N/header annotated offsets and I/sys_dma.o as comparison artifact. Track source/destination addresses, byte counts, start/interrupt bits and client call sites. No match or absence-of-use conclusion follows from this initial scan. |
| LCD / framebuffer | TCON=0x01c0c000; DEFE=0x01e00000; DEBE block=0x01e60000, N's register struct begins at0x01e60800 | P/de.h/.c and N/display.c. Trace display clocks, timing, layer address/stride and buffer writers. Two TCON and two DEBE literal sites found. Reference display sizes and buffer addresses are not assigned to YS. |
| Clock / reset | CCU=0x01c20000; PLL CPU+0, audio+8, video+10, DDR+20, peripheral+28; CPU/AHB_APB+50/54; bus gates+60/64/68; resets+2c0/2c4/2d0 | P/clock.h/.c. Link gate/reset masks to actual peripheral calls; evaluate PLL/dividers only after complete setup trace. Fifteen CCU literal sites found. PWM's 24-MHz constant does not measure the real source clock. |
| Cache / MMU / DRAM initialization | CP15 c1 control, c2 translation base, c7 cache operations, c8 TLB; DRAMC=0x01c01000; SRAM controller=0x01c00000 | A/cache-v5.S, armv5_mmu.h, P/DRAM examples, N/mmu.c/dram.c. Follow CP15 operands, table alignment, barriers/drain and DRAM polling. ARM926 lacks ARMv7-only instructions: use the explicit Unicorn ARM926 model. No generic ARMv7 cache sequence is substituted. |

## Evidence grading

The numeric scores rank leads and are not calibrated probabilities. A literal
reference gets0.65, a bounded straight-line address-use candidate0.75, a complete
nonrelocated byte candidate0.90, and a relocation-masked candidate0.80. Normalized
instruction similarity is capped at0.60. None authorizes an automatic name.

An RE_ label requires a verified original image hash, exact guarded bytes and
separate original-code ARM926 execution evidence. Confidence1.0 then describes
the stated bounded behavior only. Function equivalence, live hardware behavior,
full function boundaries and correct timing are separate claims.

## Reference inconsistencies retained for review

N's DRAM struct comments jump from0x14 to0x24 without reserved words, DDMA pointer
macros use the NDMA type, and PD/PE/PF interrupt macros all use the GPIO base.
These are reasons not to import its C layout automatically. Our extraction stores
explicit annotations with provenance rather than claiming compiler offsetof
validation. P's I2C2 base/IRQ definition is also only a reference claim until
checked against the exact chip manual; it is not needed by the proven YS paths.

Next reference-specific work: build path-aware CFGs around timer/INTC candidates,
validate indirect handler targets, then compare MMIO access sequences with
relocation targets and constants resolved. Thumb, scheduler and state-machine
recovery remain separate unfinished stages.
