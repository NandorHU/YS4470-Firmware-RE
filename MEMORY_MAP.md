# Memory map

## Confirmed image layout

| Region | Address/offset | Basis |
|---|---:|---|
| SPI flash capacity | `0x01000000` (16 MiB) | Installer/device evidence. |
| boot0 | flash `0x00000000` | Boot-logo test/project status. |
| boot logo | flash `0x00006000` | Boot-logo emulator evidence. |
| main image header | flash `0x00050000` | Boot-load emulator evidence. |
| main payload | flash `0x00050020` | Emulator assertion. |
| published tested payload length | `0x005abf00` (5,943,264 bytes) | `evidence/v1-boot-load-tests.json`. |
| payload destination | `0x80000000` | Emulator assertion. |
| main image link base | `0x7fffffe0` | Published test constants and offset calculation. |

```
flash_offset = 0x50000 + (ARM_address - 0x7fffffe0)
ARM_address = 0x7fffffe0 + (flash_offset - 0x50000)
```

Example: `0x80051978 -> 0x000a1998`, matching the checked switch-label offset.

## Not established

DRAM setup, MMU/cache state, complete RAM allocation, vectors, and peripheral mappings require a supplied original image and boot/runtime trace.
