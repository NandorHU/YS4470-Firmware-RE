"""Static original-byte audit; no firmware execution or device operations."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x7fffffe0
RANGES = [(0x80058f10, 0x80059050), (0x8003dfac, 0x8003dff8),
          (0x80025ca4, 0x80025cd4), (0x80025958, 0x800259b0),
          (0x8003ae20, 0x8003ae58)]


def s32(x):
    x &= 0xffffffff
    return x - 0x100000000 if x & 0x80000000 else x


def s16(x):
    x &= 0xffff
    return x - 0x10000 if x & 0x8000 else x


def magic160(n):
    high = (s32(n) * 0x66666667) >> 32
    return (high >> 6) - (high >> 31)


def local_metric_stable(g, multiplier):
    # Explicit stable-getter assumption: native code rereads it on the >=320 path.
    n = s32(multiplier * g + 80)
    return s16(1 if n < 320 else magic160(n))


def display_metric_stable(g, value):
    if value & 0xffffffff == 0:
        return 0
    n = s32(s16(g) * s16(value) + 80)
    return s16(1 if n < 320 else magic160(n))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[4])
    p.add_argument('--out', type=Path, default=Path(__file__).with_name('static-audit.json'))
    args = p.parse_args()
    manifest = json.loads((args.repo / 'original-firmware/manifest.json').read_bytes())
    images, references, outputs = {}, [], []
    for entry in manifest['images']:
        raw = (args.repo / entry['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry['sha256'] and len(raw) == entry['size_bytes']
        images[entry['version']] = digest
        words = {}
        ranges = []
        for lo, hi in RANGES:
            instructions = []
            for i in Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(raw[lo-BASE:hi-BASE], lo):
                assert i.size == 4
                words[hex(i.address)] = i.bytes.hex()
                instructions.append({'address': hex(i.address), 'bytes': i.bytes.hex(),
                                     'mnemonic': i.mnemonic, 'operands': i.op_str})
            assert len(instructions) == (hi-lo)//4
            ranges.append({'begin': hex(lo), 'end_exclusive': hex(hi), 'instructions': instructions})
        word = lambda a: struct.unpack_from('<I', raw, a-BASE)[0]
        palette = word(0x8003ae58)
        assert palette == 0x80068b3c
        assert struct.unpack_from('<H', raw, palette+18*2-BASE)[0] == 0x9cf3
        assert word(0x80025cd4) == 0x805abd54
        assert word(0x80059a00) == word(0x800259b0) == 0x66666667
        references.append(words)
        outputs.append(ranges)
    assert references[0] == references[1] and outputs[0] == outputs[1]
    assert local_metric_stable(130, 3) == 2
    assert local_metric_stable(130, 4) == 3
    assert display_metric_stable(130, 3) == 2
    assert display_metric_stable(130, 0) == 0
    assert display_metric_stable(130, 0x10000) == 1  # nonzero input, signed16 operand zero
    assert display_metric_stable(130, 0xffff) == 1   # signed16 input -1
    report = {
        'schema': 'ys4470.cold-palette-static-audit.v1',
        'images': images,
        'firmware_executed': False,
        'original_ranges_equal': True,
        'instruction_word_count': len(references[0]),
        'instruction_bytes': references[0],
        'disassembly': outputs[0],
        'branch': {'flag_source': 'u8[OBJECT+0x20]', 'tested_mask': 1,
                   'zero_target': '0x80058f80', 'nonzero_target': '0x8005904c'},
        'default_getter': {'entry': '0x80025ca4', 'zero_argument_pointer_slot': '0x805abd60',
                           'slot_parent_literal': '0x805abd54', 'null_slot_return': 130,
                           'nonnull_formula': '((u32(driver_flags << 15)) >> 22) == ((driver_flags >> 7) & 0x3ff)',
                           'driver_flags_0x413c_result': 130,
                           'actual_runtime_slot_value': 'Not established by this static audit; coordinator must capture'},
        'palette18': {'table_literal': '0x8003ae58', 'table_address': '0x80068b3c', 'value': '0x9cf3'},
        'stable_getter_130_arithmetic': [
            {'callsite': '0x80058f94', 'wrapper': '0x8003dfac', 'tag': '0x44',
             'payload': '(incoming_R2 & 0xffff0000) | 0x9cf3', 'example_high16_0x1201': '0x12019cf3'},
            {'callsite': '0x80058fe4', 'wrapper': '0x8003dfec', 'tag': '0x40',
             'numerator': 470, 'signed16_raw_value': 2},
            {'callsite': '0x80058ff4', 'wrapper': '0x8003dfd4', 'tag': '0x45', 'raw_value': 127},
            {'callsite': '0x80059048', 'wrapper': '0x8003dfc8', 'tag': '0x42',
             'local_numerator': 600, 'local_signed16_result': 3,
             'display_metric_numerator': 470, 'signed16_raw_value': 2}],
        'all_success_continuation': {'initial_count': 3, 'requested_realloc_sizes': [24,30,36,42],
                                     'final_count': 7, 'new_tags': ['0x44','0x40','0x45','0x42'],
                                     'all_properties_use_realloc': True,
                                     'allocator_failure_count_change': 0},
        'limits': [
            'This is static decoding plus independent arithmetic, not a new native execution campaign.',
            'OBJECT flag, default display slot, getter inputs/results and incoming palette R2 must be observed dynamically.',
            'Both local metric calculations reread the default getter when the first signed numerator is at least 320; stable-getter arithmetic is explicitly conditional.',
            'Local metric3/4 use full32 ADD/LSL and signed CMP/SMULL, followed by signed16 narrowing. Native 25958 uses signed16 SMULBB and checks full32 input==0 before multiplication.',
            'Tag44 preserves incoming R2 high16. That halfword remains opaque; no physical color/channel/unit claim.',
            'No allocator implementation/free/reuse, complete initializer, root objects, callbacks or physical timing is proved.'],
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    args.out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'equal_original_instruction_words': len(references[0]), 'tags': ['0x44','0x40','0x45','0x42'], 'conditional_raw_values': ['opaque-high16|0x9cf3',2,127,2]}))


if __name__ == '__main__':
    main()
