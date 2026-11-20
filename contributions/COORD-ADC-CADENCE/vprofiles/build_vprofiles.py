"""Compose V3.8 E2 + volume + ownprotocol-style polling with Beta Diode profiles Base, v1..v4. No device I/O.

v1 = beta.4 (diode fixed range 59 00), v2 = + chip command 68 0a on diode configuration,
v3 = + early short tone from a falling reading, v4 = v2 + v3. Fail closed on any unexpected input.
"""
import argparse, json, struct, sys
from pathlib import Path
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE.parent / 'ownprotocol'), str(HERE.parent / 'diodefixed')]
import build_ownprotocol as own
from build_ownprotocol import volume, pack_lz, reproduce
import build_diodefixed as diodefixed

BASE, BITMAP, BITMAP_END, sha = own.BASE, own.BITMAP, own.BITMAP_END, own.sha
E2_SHA = 'b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1'
DESC_1E = 0x8006367C + 8 * 0x1E
# Overlay entry table offsets (each a 'b' to the routine).
ENTRY = dict(auto=16, cycle=20, label=24, case2=28, classify=32, post_apply=36)
# Every numeric branch target the overlay is allowed to contain.
ALLOWED_EXTERNAL = {0x8001110C, 0x80011110, 0x8000489C, 0x80004490, 0x80006778, 0x80004480, 0x80004470,
                    0x80010754, 0x8005F8B4, 0x8003A2C8, 0x800609C8}


def assemble(e2):
    _, volume_receipt = volume.build(e2)
    source = (volume.HERE / 'volume_overlay.s').read_text(encoding='utf-8')
    raw = e2[BITMAP - BASE:BITMAP_END - BASE]
    packed = pack_lz(raw)
    start, end = source.index('decode_run:'), source.index('decode_done:')
    # Same LZ back-reference arm as build_ownprotocol (kept textually identical).
    own_src = (HERE.parent / 'ownprotocol/build_ownprotocol.py').read_text(encoding='utf-8')
    arm = own_src[own_src.index("'''decode_run:") + 3:own_src.index("''' + source[end:]")]
    source = source[:start] + arm + source[end:]
    table = struct.unpack_from('<I', e2, 0x800609d8 - BASE)[0]
    labels = struct.unpack_from('<4I', e2, table - BASE)
    constants = '\n'.join(f'.equ {n}_LABEL, {a}' for n, a in zip(('BASE', 'DIRECT', 'AUTO', 'READY'), labels))
    extra = (HERE / 'vprofiles.s').read_text(encoding='utf-8-sig')
    entries = 'b own_auto\nb own_cycle\nb own_label\nb own_case2\nb own_classify\nb own_post_apply\n'
    assert source.count('b get_bitmap\n') == 1 and source.count('\n.ltorg') >= 1
    source = source.replace('b get_bitmap\n', 'b get_bitmap\n' + entries, 1)
    source = source.replace('\n.ltorg', '\n' + extra + '\n.ltorg', 1)
    text = f'.equ PACKED_SIZE, {len(packed)}\n{constants}\n{source}'
    ks = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    program, _ = ks.asm(text, BITMAP, as_bytes=True)
    if len(program) + len(packed) > len(raw):
        raise ValueError('Overlay exceeds verified reclaimed bitmap region')
    # Symbol addresses: append a word table after everything; nothing before it moves.
    names = ('own_auto', 'own_post_apply', 'own_reconfig', 'own_case2', 'own_classify', 'own_cycle', 'own_label',
             'own_names', 'own_hist', 'own_state', 'own_cmd68', 'name_v1')
    tail = '\n.align 2\nsymtab_marker:\n.word 0x5eedf00d\n' + ''.join(f'.word {n}\n' for n in names)
    probe, _ = ks.asm(text + tail, BITMAP, as_bytes=True)
    at = probe.rfind(struct.pack('<I', 0x5eedf00d))
    assert at >= len(program) - 4 and probe[:len(program)] == program, 'symbol probe moved code'
    symbols = dict(zip(names, struct.unpack_from(f'<{len(names)}I', probe, at + 4)))
    assert all(BITMAP <= v < BITMAP + len(program) for v in symbols.values()), symbols
    return program, packed, raw, symbols, volume_receipt


def check_branches(program, symbols):
    """Static: decode every B/BL in the overlay; targets must be internal or in ALLOWED_EXTERNAL."""
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    external = set()
    for off in range(0, len(program), 4):
        w, = struct.unpack_from('<I', program, off)
        if (w >> 25) & 7 == 5 and (w >> 28) != 0xF:
            a = BITMAP + off
            t = (a + 8 + ((((w & 0xFFFFFF) ^ 0x800000) - 0x800000) << 2)) & 0xFFFFFFFF
            if not BITMAP <= t < BITMAP + len(program):
                external.add(t)
    # Literal pools can contain words that look like branches; only code words are relevant, so check the
    # required set is present and every out-of-overlay target within the code range is allowed.
    code_end = symbols['own_names']
    bad = []
    for off in range(0, code_end - BITMAP, 4):
        w, = struct.unpack_from('<I', program, off)
        if (w >> 25) & 7 == 5 and (w >> 28) != 0xF:
            a = BITMAP + off
            t = (a + 8 + ((((w & 0xFFFFFF) ^ 0x800000) - 0x800000) << 2)) & 0xFFFFFFFF
            if not BITMAP <= t < BITMAP + len(program) and t not in ALLOWED_EXTERNAL | volume_targets():
                bad.append((hex(a), hex(t)))
    assert not bad, bad
    for o, name in ENTRY.items():
        w, = struct.unpack_from('<I', program, name)
        t = (BITMAP + name + 8 + ((((w & 0xFFFFFF) ^ 0x800000) - 0x800000) << 2)) & 0xFFFFFFFF
        assert t == symbols['own_' + o], (o, hex(t))
    return sorted(hex(t) for t in external)


def volume_targets():
    # External calls already made by the reviewed volume overlay / ownprotocol code.
    rec = json.loads((HERE.parent / 'ownprotocol/build-receipt.json').read_text())
    return set(int(x, 16) for x in rec.get('external_branch_targets', [])) or VOLUME_EXTERNAL


VOLUME_EXTERNAL = set()  # filled by build() from the reviewed ownprotocol image


def build(e2):
    if sha(e2) != E2_SHA:
        raise ValueError('unexpected E2 base')
    own_image, own_receipt = own.build(e2)
    assert sha(own_image) == diodefixed.OWN_SHA
    program, packed, raw, symbols, volume_receipt = assemble(e2)
    # Targets the reviewed ownprotocol overlay already branches to are acceptable as well.
    own_prog = own_image[BITMAP - BASE:BITMAP - BASE + own_receipt['overlay_bytes']]
    for off in range(0, len(own_prog), 4):
        w, = struct.unpack_from('<I', own_prog, off)
        if (w >> 25) & 7 == 5 and (w >> 28) != 0xF:
            t = (BITMAP + off + 8 + ((((w & 0xFFFFFF) ^ 0x800000) - 0x800000) << 2)) & 0xFFFFFFFF
            if not BITMAP <= t < BITMAP + len(own_prog):
                VOLUME_EXTERNAL.add(t)
    external = check_branches(program, symbols)
    out = bytearray(e2)
    edits = []
    def replace(addr, old, new):
        off = addr - BASE
        if len(old) != len(new) or bytes(out[off:off + len(old)]) != old:
            raise ValueError(f'Preimage mismatch at {addr:#x}')
        out[off:off + len(old)] = new
        edits.append(dict(address=hex(addr), bytes=len(new), before=old.hex() if len(old) <= 8 else sha(old),
                          after=new.hex() if len(new) <= 8 else sha(new)))
    def word(addr, old, new):
        replace(addr, struct.pack('<I', old), struct.pack('<I', new))
    br = volume.branch
    replace(BITMAP, raw, (program + packed).ljust(len(raw), b'\0'))
    word(0x80051c0c, br(0x80051c0c, 0x80060a08), br(0x80051c0c, BITMAP))
    word(0x8005d048, br(0x8005d048, 0x8001b5cc), br(0x8005d048, BITMAP + 4))
    word(0x80006ecc, br(0x80006ecc, 0x800630a4, True), br(0x80006ecc, BITMAP + 8, True))
    word(volume.FONT + 4, 0x8002c844, BITMAP + 12)
    word(0x8001110c, 0xe92d4010, br(0x8001110c, BITMAP + ENTRY['auto']))
    word(0x8005f8b0, 0xe2000003, br(0x8005f8b0, BITMAP + ENTRY['cycle']))
    word(0x800609c0, 0xe59f1010, br(0x800609c0, BITMAP + ENTRY['label']))
    word(0x80007f8c, 0x18bd8830, 0x38bd8830)            # 'poplo' (as ownprotocol)
    word(0x80007f88, 0xe3500003, 0xe3500001)            # Ready completion steps for profiles >= 1
    word(0x8000446c, 0xe88d0016, br(0x8000446c, BITMAP + ENTRY['case2']))
    word(0x80060c94, br(0x80060c94, 0x80010754, True), br(0x80060c94, BITMAP + ENTRY['classify'], True))
    word(0x8005fb84, 0x0bfec560, br(0x8005fb84, BITMAP + ENTRY['post_apply'], True))  # was 'bleq 0x8001110c'
    # beta.6: second toggle callback 0x800609e0 maps 2 <-> 4 instead of 0 <-> 1; boot default v2.
    word(0x800609ec, 0xe3500000, 0xe3500002)
    word(0x800609f0, 0x03a00001, 0x03a00004)
    word(0x800609f4, 0x13a00000, 0x13a00002)
    replace(0x80060a90, bytes((0, 0)), bytes((2, 2)))
    replace(DESC_1E, bytes(8), struct.pack('<IB3x', symbols['own_cmd68'], 2))
    image = bytes(out)
    # Beta.4 diode fixed-range sites (same preimage contract as build_diodefixed).
    d = bytearray(image)
    for a, b in diodefixed.SITES.items():
        w = int.from_bytes(d[a - BASE:a - BASE + 4], 'little'); wb = int.from_bytes(d[b - BASE:b - BASE + 4], 'little')
        if (w & 0xFFFF0FFF) != 0xE3A00019 or (wb & 0xFFFF0FFF) != 0xE3A0000E:
            raise ValueError(f'diodefixed preimage mismatch at {a:#x}')
        d[a - BASE] = 0x13
        edits.append(dict(address=hex(a), bytes=1, before='19', after='13'))
    image = bytes(d)
    assert len(image) == len(e2) and image[:32] == e2[:32]
    receipt = dict(schema='ys4470.vprofiles.v1', profiles=['Base', 'v1', 'v2', 'v3', 'v4'], selectable=['v2', 'v4'], boot_profile='v2',
                   factory_application_sha256=own_receipt['factory_application_sha256'],
                   base_application_sha256=E2_SHA, application_sha256=sha(image), image_bytes=len(image),
                   overlay_bytes=len(program), packed_bytes=len(packed), bitmap_bytes=len(raw),
                   symbols={k: hex(v) for k, v in symbols.items()}, external_branch_targets=external,
                   descriptor_0x1e=[hex(symbols['own_cmd68']), 2], edits=edits,
                   physical_device_operations=0, physical_time_units_established=False)
    return image, receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    original = (ROOT / 'original-firmware/V3.8/f1c100s.bin').read_bytes()
    image, receipt = build(reproduce(original)[0]['profiles-E2'])
    a.out.mkdir(parents=True, exist_ok=True)
    for name, data in (('ys4470-e2-vprofiles-OFFLINE.bin', image),
                       ('build-receipt.json', (json.dumps(receipt, indent=2) + '\n').encode())):
        p = a.out / name
        if p.exists() and p.read_bytes() != data:
            raise ValueError(f'Output differs: {p}')
        p.write_bytes(data)
    print(json.dumps({k: receipt[k] for k in ('application_sha256', 'overlay_bytes', 'packed_bytes', 'symbols',
                                              'external_branch_targets')}, indent=2))


if __name__ == '__main__':
    main()
