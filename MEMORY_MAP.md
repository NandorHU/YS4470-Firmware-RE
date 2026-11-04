# Memory map

## Confirmed image layout

| Region | Address/offset | Basis |
|---|---:|---|
| SPI flash capacity | `0x01000000` | Installer/device evidence. |
| boot0 | flash `0x00000000` | Boot-logo evidence. |
| boot logo | flash `0x00006000` | Boot-logo evidence. |
| main image header | flash `0x00050000` | Boot-load evidence. |
| main payload | flash `0x00050020` | Boot loader emulator assertion. |
| factory 3.8 payload length | `0x005abf20` | SHA-checked local input. |
| payload destination | `0x80000000` | Boot loader emulator assertion. |
| raw-image base | `0x7fffffe0` | Successful Ghidra import. |
| RX retry/state object | RAM `0x805aae8c` | Literal pool at `0x8000481c`. |
| RX result/code object | RAM `0x805ac714` | Literal pool at `0x80004820`. |
| E1 profile state | RAM `0x80060a90` | Offline profile builder; active/requested bytes plus GUI pointers. |

~~~text
flash_offset = 0x50000 + (ARM_address - 0x7fffffe0)
ARM_address = 0x7fffffe0 + (flash_offset - 0x50000)
~~~

The E1 profile state is experimental patch state, not a factory structure. DRAM init, MMU/cache state, vectors, and peripheral maps remain unestablished.
