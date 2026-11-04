# Memory map

## Confirmed image layout

| Region | Address/offset | Basis |
|---|---:|---|
| SPI flash capacity | `0x01000000` (16 MiB) | Checked-in installer/device evidence. |
| boot0 | flash `0x00000000` | Existing project status. |
| boot logo region | flash `0x00006000` | Existing boot-logo emulator evidence. |
| main image header | flash `0x00050000` | Existing boot-load emulator evidence. |
| main payload | flash `0x00050020` | Emulator asserts SPI read starts here. |
| main payload destination | `0x80000000` | Emulator asserts this destination. |
| main image link base | `0x7fffffe0` | Published test constants and offset calculation. |

For a main-image ARM virtual address `A`, the corresponding flash offset is:

```
flash_offset = 0x50000 + (A - 0x7fffffe0)
```

Example: `0x80051978` maps to `0x000a1998`; this matches the checked test's string offset.

## Not established

DRAM initialization, MMU/cache configuration, complete RAM allocation, interrupt vectors, and peripherals’ final virtual mappings require an original image and a boot-time trace.
