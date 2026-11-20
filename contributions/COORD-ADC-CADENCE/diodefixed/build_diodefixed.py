"""Build the 4-site diode fixed-range image on top of the reproducible ownprotocol build. No device I/O.

The type-2 diode / non-Fast Buzzer record (2,0x0e,0x19) becomes (2,0x0e,0x13), so the meter is sent
`59 00` (fixed range 0, as the factory Fast CONT path does) instead of `5a` (hypothesis: autorange).
0x80044ec0 is deliberately NOT patched: its r8 also feeds UI+8 of the V / cfg 0x0c / cfg 0x0f modes.
"""
import argparse, hashlib, json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / 'ownprotocol'))
from build_ownprotocol import build, reproduce

BASE = 0x7FFFFFE0
OWN_SHA = 'b081860a2383e5c1251ea80abf25cb4f39bdf74a340a376975acf2b0ff6f9c8e'
OUT_SHA = '934a2557f7b069645ca3484a70e64e4e33844bf0b0892d2f3583078cadae9417'
# 'mov rX,#0x19' site -> paired 'mov rY,#0x0e'
SITES = {0x8000D000: 0x8000D004, 0x8000D0BC: 0x8000D0C0, 0x80045044: 0x80045048, 0x800450C4: 0x800450C8}
def sha(b): return hashlib.sha256(b).hexdigest()

def apply(own):
    assert sha(own) == OWN_SHA, 'unexpected ownprotocol base'
    d = bytearray(own); edits = []
    for a, b in SITES.items():
        w = int.from_bytes(d[a-BASE:a-BASE+4], 'little'); wb = int.from_bytes(d[b-BASE:b-BASE+4], 'little')
        if (w & 0xFFFF0FFF) != 0xE3A00019 or (wb & 0xFFFF0FFF) != 0xE3A0000E:
            raise ValueError(f'preimage mismatch at {a:#x}')
        d[a-BASE] = 0x13; edits.append(dict(address=hex(a), old=f'{w:08x}', new=f'{(w & ~0xff) | 0x13:08x}'))
    out = bytes(d)
    assert sha(out) == OUT_SHA and len(out) == len(own) and out[:32] == own[:32]
    return out, edits

def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args()
    original = (ROOT / 'original-firmware/V3.8/f1c100s.bin').read_bytes()
    own, _ = build(reproduce(original)[0]['profiles-E2'])
    image, edits = apply(own)
    receipt = dict(schema='ys4470.diodefixed.v1', base_application_sha256=OWN_SHA, application_sha256=OUT_SHA,
                   image_bytes=len(image), edits=edits, skipped_sites={'0x80044ec0': 'shared r8 also stores UI+8 for V/0x0c/0x0f',
                   '0x80044f20': 'voltage record', '0x80044f74': 'cfg 0x0c record', '0x80044fd0': 'cfg 0x0f record'},
                   physical_device_operations=0, physical_speedup_established=False)
    a.out.mkdir(parents=True, exist_ok=True)
    for name, data in (('ys4470-e2-ownprotocol-diodefixed-OFFLINE.bin', image), ('build-receipt.json', (json.dumps(receipt, indent=2)+'\n').encode())):
        p = a.out / name
        if p.exists() and p.read_bytes() != data: raise ValueError(f'Output differs: {p}')
        p.write_bytes(data)
    print(json.dumps(receipt, indent=2))
if __name__ == '__main__': main()
