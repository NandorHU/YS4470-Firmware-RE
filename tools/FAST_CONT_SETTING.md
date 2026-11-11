# Fast CONT setting and persistence

The formerly unnamed word at 0x805ac788 (settings object 0x805ac770+0x18)
belongs to the UI option **Fast CONT**. This names the option selecting the
alternate Buzzer event path; it does not establish an acoustic response time.

## UI evidence

- English label tail 0x8004557c assigns text at 0x800456a0, "Fast CONT",
  to GUI root field +0x320. The Chinese tail assigns "快速通断".
- The neighboring checkbox is root +0x31c. Registration at 0x80054910 binds
  callback 0x8005a3bc with event argument 0x1c and user data zero.
- That callback calls the original state getter 0x8003752c, which reads the
  widget's halfword +0x20 and masks bit 0. It writes the normalized 0/1
  result to 0x805ac788, then reaches SoundControlGate(5,1).
- GUI restoration at 0x80054a4c checks nonzero to choose the state-setting
  boundary. The Buzzer consumer, by contrast, tests exact equality to one.

The callback and state getter both execute original instructions in the
harness. GUI state setters and SoundControlGate are stop boundaries.

## Persistent format and default

| Property | Proven value |
|---|---|
| Flash record offset | 0x00f00000 |
| Record size | 0x48 / 72 bytes |
| Fast CONT word within record | +0x18 |
| CRC-covered data | bytes +0x00..+0x43 |
| Stored CRC | little-endian u32 at +0x44 |
| Algorithm | zlib-compatible CRC32 / CRC-32/ISO-HDLC |
| Invalid-record Fast CONT default | 1 |

Loader 0x80008098 stages a flash record, validates CRC, and reaches a
72-byte copy on success. On failure its default block writes the first
seven words, including Fast CONT=1, computes CRC and reaches the storage
write boundary at 0x80006374. Save routine 0x800082c0 recomputes the same CRC
and reaches that boundary with arguments (0,settings,0xf00000,0x48).

The CRC loop uses mask 0x12477cdf with BIC, equivalent to the reflected
0xedb88320 polynomial when the low bit is set. Its results are compared
with Python zlib.crc32, not with a second translation of the same loop.

The default block does not initialize the whole record in the tested
slice: bytes +0x1c..+0x43 retain the initial RAM pattern before CRC is
calculated. Later loader metadata updates are outside this experiment.

Valid CRC alone is not range validation. Synthetic records with word 2 or
0xffffffff are accepted; UI restore treats them as checked, while the
Buzzer event branch requires exact 1. Ordinary checkbox updates normalize
the field to 0/1. No such noncanonical value was found in the device snapshot.

## Historical device snapshot

The private 2026-11-06 E2-modified 16 MiB backup contains a valid settings
record at 0xf00000 with Fast CONT=1. This is an offline historical record,
not a new observation of a running device. Only hashes, CRC validity and
this selected flag are exported; the raw settings record remains private.

## Reproduce

```powershell
$env:PYTHONPATH = "$PWD\work\analysis-python"
python tools/trace_fast_cont_setting.py `
  --input 'V3.6=<verified original path>' `
  --input 'V3.8=<verified original path>' `
  --out evidence/fast-cont-setting.json
```

Optionally add `--flash <private known 2026-11-06 backup>` for snapshot
verification. The tool pins its SHA-256 and opens it read-only.

Across the two originals: 524 widget-state cases, 48 save CRC cases,
48 valid records, 144 damaged records rejected, 12 default cases, eight
checkbox-restore cases, six UI-binding slices and 14 checkbox-to-event
checks. Every storage/GUI/sound API implementation is excluded from
execution. No physical flash writes occur.

Next: follow the additional Fast CONT read at 0x80003878 in ResultDispatch
into sound control, keeping timing and actual buzzer behavior unassigned.


## Factory save event verified (2026-11-11)

Original registration `0x8001b2d0` binds the settings save callback `0x800453c8` to GUI context `+0x394`. In the three tested event codes, event 1 reaches the original CRC and storage routine. The other tested events leave the record unchanged. A Fast CONT checkbox update alone changes the RAM word. At `0x80006374` the original save reads a 4 KiB sector. A blank record prefix goes directly to one 72-byte program. A nonblank prefix takes erase, scratch merge and sixteen 256-byte program calls. Both paths preserve the adjacent synthetic bytes when transfers succeed. [Original event and round-trip evidence](../contributions/COORD-DIODE-VOLUME/factory-settings-ui-validation.json) · [Original sector wrapper](../contributions/COORD-DIODE-VOLUME/factory-settings-sector-validation.json).
