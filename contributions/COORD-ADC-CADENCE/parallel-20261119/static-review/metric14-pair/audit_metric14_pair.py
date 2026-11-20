"""Independent static-byte review of STATE metric14 pair; no target execution."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

BASE = 0x7fffffe0
RANGES = [(0x800590a0, 0x80059100), (0x80059c60, 0x80059c70),
          (0x8003dd9c, 0x8003ddb4), (0x8003ddd8, 0x8003dde4),
          (0x80025958, 0x800259b0)]


def s16(x):
    x &= 0xffff
    return x-0x10000 if x & 0x8000 else x


def s32(x):
    x &= 0xffffffff
    return x-0x100000000 if x & 0x80000000 else x


def metric_stable(getter, input_word):
    if input_word & 0xffffffff == 0:
        return 0
    n = s32(s16(getter) * s16(input_word) + 80)
    if n < 320:
        return 1
    high = (n * 0x66666667) >> 32
    return s16((high >> 6) - (high >> 31))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[5])
    parser.add_argument('--out', type=Path, default=Path(__file__).with_name('static-audit.json'))
    args = parser.parse_args()
    manifest = json.loads((args.repo/'original-firmware/manifest.json').read_bytes())
    images, versions = {}, []
    for entry in manifest['images']:
        raw = (args.repo/entry['path']).read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        assert digest == entry['sha256'] and len(raw) == entry['size_bytes']
        images[entry['version']] = digest
        instructions = []
        for lo, hi in RANGES:
            decoded = list(Cs(CS_ARCH_ARM, CS_MODE_ARM).disasm(raw[lo-BASE:hi-BASE], lo))
            assert len(decoded) == (hi-lo)//4 and all(i.size == 4 for i in decoded)
            instructions.extend({'address': hex(i.address), 'bytes': i.bytes.hex(),
                                 'mnemonic': i.mnemonic, 'operands': i.op_str} for i in decoded)
        assert struct.unpack_from('<I', raw, 0x800259b0-BASE)[0] == 0x66666667
        words = {r['address']: r['bytes'] for r in instructions}
        assert words['0x800590b0'] == 'ea02000a'  # BEQ 59c60
        assert words['0x80059c64'] == '0e10a0e3'  # metric argument14
        assert words['0x8003dddc'] == '1010a0e3'  # tag10
        assert words['0x8003dda0'] == '1110a0e3'  # tag11
        assert words['0x8003ddac'] == '1510a0e3'  # next wrapper tag15
        versions.append(instructions)
    assert versions[0] == versions[1]
    assert [metric_stable(130, x) for x in (14,12,10,5)] == [11,10,8,4]
    assert metric_stable(130, 0) == 0 and metric_stable(130, 0x10000) == 1
    assert metric_stable(130, 0xffff) == 1
    report = {
        'schema': 'ys4470.cold-state-metric14-pair-static-audit.v1',
        'images': images, 'firmware_executed': False,
        'instruction_word_count': len(versions[0]), 'original_disassembly_equal': True,
        'disassembly': versions[0],
        'state_selector': {'load': '0x800590a8: LDRB R0,[R4,#1]',
                           'register_binding': 'R4=STATE from coordinator prefix; not reexecuted in this static review',
                           'value1': {'branch': '0x800590b0 -> 0x80059c60', 'metric_argument': 14},
                           'value2': {'path': '0x800590b4..0x800590c4', 'metric_argument': 12},
                           'other_values': {'path': '0x800590b4..0x800590c4', 'metric_argument': 10}},
        'pair': {'style_pointer': '[R4+0xc]+0x20, cached in R8',
                 'metric_result_cache': 'R9 at 0x800590c8',
                 'first': {'callsite': '0x800590d4', 'wrapper': '0x8003ddd8', 'tag': '0x10', 'payload': 'R2=R1 unchanged; fallthrough to0x8003dde4'},
                 'second': {'callsite': '0x800590e0', 'wrapper': '0x8003dd9c', 'tag': '0x11', 'payload': 'R2=R1 unchanged; branch to0x8003dde4'},
                 'stop': '0x800590e4'},
        'conditional_arithmetic': {'stable_getter_result': 130,
                                   'cold_state1_metric14_numerator': 1900, 'pair_raw_values': [11,11],
                                   'state2_metric12_numerator': 1640, 'state2_pair_raw_values': [10,10],
                                   'other_metric10_numerator': 1380, 'other_pair_raw_values': [8,8]},
        'next_metric5': {'input_callsite': '0x800590ec', 'input_argument': 5,
                         'wrapper_callsite': '0x800590fc', 'wrapper': '0x8003dda8', 'tag': '0x15',
                         'stable_getter130_numerator': 730, 'conditional_raw_value': 4,
                         'outside_pair_stop': True},
        'continuation_expectations': {'coordinator_supplied_initial_count': 10,
                                      'new_tags': ['0x10','0x11'],
                                      'all_success_realloc_bytes': [66,72],
                                      'all_success_final_count': 12,
                                      'prior_summary': '0x37', 'summary_after_either_or_both_insertions': '0x37',
                                      'reason': 'Both tags map to summary bit1, already present from tags12/13',
                                      'failure_does_not_increment_reference_count': True},
        'arithmetic_limits': [
            '25958 tests the full32 input word for zero before SMULBB; 0 and0x10000 are distinct paths.',
            'SMULBB multiplies SIGNED low16 halves of getter result and input. The +80 ADD wraps in32 bits.',
            'CMP against320 is signed; values below320 yield minimum1. Otherwise the getter is read again and the multiply/division repeated.',
            'SMULL with signed0x66666667, ASR highword6 and sign correction computes the observed division; final LSL16/ASR16 sign-extends the low16 result.',
            'Stable getter130 and small positive inputs yield exact numerators1900/1640/1380/730 and outputs11/10/8/4.',
            'No physical metric, dimension or timing unit is inferred. Native pair execution, R9 preservation through setters and all allocation/memory/SP effects require coordinator validation.'],
        'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    }
    args.out.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'original_instruction_words': len(versions[0]), 'pair_tags': ['0x10','0x11'], 'cold_pair_values': [11,11], 'next_tag': '0x15', 'next_value': 4, 'firmware_executed': False}))


if __name__ == '__main__':
    main()
