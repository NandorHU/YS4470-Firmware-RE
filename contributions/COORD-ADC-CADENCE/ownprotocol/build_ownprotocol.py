"""Compose a guarded offline V3.8 E2+volume+ownprotocol application; no device I/O."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import struct
import sys
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE.parent), str(ROOT / 'contributions/COORD-DIODE-VOLUME')]
import build_diode_volume as volume
from reproduce_profiles import reproduce
BASE, BITMAP, BITMAP_END = volume.BASE, volume.BITMAP, volume.BITMAP_END
sha = volume.digest


def pack_lz(raw):
    """1..127 literal length; 128..255 copy length 3..130 + u16 distance; 0 end."""
    out, literal = bytearray(), bytearray()
    index = defaultdict(list)
    def flush():
        if literal:
            out.append(len(literal)); out.extend(literal); literal.clear()
    i = 0
    while i < len(raw):
        best, distance = 0, 0
        for j in reversed(index[raw[i:i+3]]):
            if i-j > 65535:
                break
            n = 3
            while n < min(130, len(raw)-i) and raw[j+n] == raw[i+n]:
                n += 1
            if n > best:
                best, distance = n, i-j
                if n == 130:
                    break
        take = best if best >= 3 else 1
        if best >= 3:
            flush(); out.extend((128 | (best-3), distance & 255, distance >> 8))
        else:
            literal.append(raw[i])
            if len(literal) == 127:
                flush()
        for j in range(i, i+take):
            if j+3 <= len(raw):
                index[raw[j:j+3]].append(j)
        i += take
    flush(); out.append(0)
    return bytes(out)


def build(e2):
    # Reuse all existing manifest, descriptor and bitmap-reference validation.
    _, volume_receipt = volume.build(e2)
    source = (volume.HERE / 'volume_overlay.s').read_text(encoding='utf-8')
    raw = e2[BITMAP-BASE:BITMAP_END-BASE]
    packed = pack_lz(raw)
    # Replace only the RLE copy arm. The rest of the independently tested volume
    # overlay, including its public entry offsets and lazy allocation, is retained.
    start, end = source.index('decode_run:'), source.index('decode_done:')
    source = source[:start] + '''decode_run:
    bic r2, r2, #128
    add r2, r2, #3
    sub r3, r8, r0
    cmp r2, r3
    bhi decode_failed
    sub r3, ip, r1
    cmp r3, #2
    blo decode_failed
    ldrb r3, [r1], #1
    ldrb r6, [r1], #1
    orrs r3, r3, r6, lsl #8
    beq decode_failed
    sub r6, r0, r7
    cmp r3, r6
    bhi decode_failed
    sub r6, r0, r3
lz_loop:
    ldrb r3, [r6], #1
    strb r3, [r0], #1
    subs r2, r2, #1
    bne lz_loop
    @ Restore descriptor register clobbered by the back-reference copy.
    ldr r6, [r4, #16]
    b decode_next
''' + source[end:]
    table = struct.unpack_from('<I', e2, 0x800609d8-BASE)[0]
    labels = struct.unpack_from('<4I', e2, table-BASE)
    constants = '\n'.join(f'.equ {name}_LABEL, {addr}' for name, addr in zip(('BASE','DIRECT','AUTO','READY'), labels))
    extra = (HERE / 'ownprotocol.s').read_text(encoding='utf-8-sig')
    # Table entry offsets +16,+20,+24 make hook targets independent of code size.
    entries = 'b own_auto\nb own_cycle\nb own_label\n'
    source = source.replace('b get_bitmap\n', 'b get_bitmap\n' + entries, 1)
    # Keep numeric external branches before the first literal/data pool: Keystone
    # 0.9.2 otherwise misrelocates branches assembled after a pool. ARM replays
    # exercise every new code hook rather than trusting assembler success.
    source = source.replace('\n.ltorg', '\n' + extra + '\n.ltorg', 1)
    program, _ = Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(f'.equ PACKED_SIZE, {len(packed)}\n{constants}\n{source}', BITMAP, as_bytes=True)
    if len(program)+len(packed) > len(raw):
        raise ValueError('Overlay exceeds verified reclaimed bitmap region')
    out = bytearray(e2)
    edits = []
    def replace(addr, old, new):
        off = addr-BASE
        if len(old) != len(new) or bytes(out[off:off+len(old)]) != old:
            raise ValueError(f'Preimage mismatch at {addr:#x}')
        out[off:off+len(old)] = new
        edits.append(dict(address=hex(addr), bytes=len(new), before_sha256=sha(old), after_sha256=sha(new)))
    def word(addr, old, new):
        replace(addr, struct.pack('<I', old), struct.pack('<I', new))
    br = volume.branch
    replace(BITMAP, raw, (program+packed).ljust(len(raw), b'\0'))
    word(0x80051c0c, br(0x80051c0c,0x80060a08),br(0x80051c0c,BITMAP))
    word(0x8005d048, br(0x8005d048,0x8001b5cc),br(0x8005d048,BITMAP+4))
    word(0x80006ecc, br(0x80006ecc,0x800630a4,True),br(0x80006ecc,BITMAP+8,True))
    word(volume.FONT+4,0x8002c844,BITMAP+12)
    word(0x8001110c,0xe92d4010,br(0x8001110c,BITMAP+16))
    word(0x8005f8b0,0xe2000003,br(0x8005f8b0,BITMAP+20))
    word(0x800609c0,0xe59f1010,br(0x800609c0,BITMAP+24))
    # Ready completion progression is shared by Ready (3) and ownprotocol (4).
    word(0x80007f8c,0x18bd8830,0x38bd8830)
    assert len(out)==len(e2) and out[:32]==e2[:32]
    return bytes(out),dict(schema='ys4470.ownprotocol.v1', profile_id=4, profile_name='ownprotocol',
        factory_application_sha256='7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290',
        base_application_sha256=volume.E2_SHA, application_sha256=sha(out), image_bytes=len(out),
        overlay_bytes=len(program), packed_bytes=len(packed), bitmap_bytes=len(raw),
        volume_reference_sha256=volume_receipt['application_sha256'],
        arm_overlay_sha256=sha(program), packed_bitmap_sha256=sha(packed), edits=edits,
        physical_device_operations=0, physical_time_units_established=False)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args()
    original=(ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes()
    e2=reproduce(original)[0]['profiles-E2']
    image,receipt=build(e2)
    args.out.mkdir(parents=True,exist_ok=True)
    for name,data in [('ys4470-e2-ownprotocol-OFFLINE.bin',image),('build-receipt.json',(json.dumps(receipt,indent=2)+'\n').encode())]:
        p=args.out/name
        if p.exists() and p.read_bytes()!=data:
            raise ValueError(f'Output differs: {p}')
        p.write_bytes(data)
    print(json.dumps(receipt,indent=2))
if __name__=='__main__':main()
