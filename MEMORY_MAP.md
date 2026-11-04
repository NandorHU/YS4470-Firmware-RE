# Memory map

| Address/range | Classification | Evidence / meaning |
|---|---|---|
| `0x7fffffe0` | static link base | V3.8 raw ARM import base |
| `0x80000000` | static eGON image load start | Firmware header/payload analysis; not a guarantee of live DRAM in FEL |
| `0x805ac694` | firmware RAM object | Transaction-builder state root (static trace) |
| `0x805ac714` | firmware RAM object | Parsed measurement output object; values written at +0x1c/+0x20 (static trace) |
| `0x805aae8c` | firmware RAM object | Retry selector object (static trace) |
| `0x805b408c` | firmware RAM object | UART RX buffer root (static trace) |
| `0x00010000..0x00010fff` | SRAM-D / OTG SRAM mapping | F1C100S Linux device tree; not approved for automated FEL access |
| `0x01c00000` | system control | F1C100S Linux device tree |
| `0x01c20000` | CCU | F1C100S Linux device tree |
| `0x01c20400` | interrupt controller | F1C100S Linux device tree |
| `0x01c20800` | PIO | F1C100S Linux device tree |
| `0x01c20c00` | timers | F1C100S Linux device tree |
| `0x01c25000/5400/5800` | UART0/1/2 | F1C100S Linux device tree |

Hardware addresses are static mapping information, not authorization to touch a physical device. See `FEL_ANALYSIS_PLAN.md`.
