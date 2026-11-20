"""Bind the independent reference to actual captured ARM wrapper inputs, without rerunning ARM."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / 'reference-audit'))
from style_reference import simulate, vector_bytes


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native', type=Path, default=Path(__file__).parent.parent / 'synchronous/native-cold-palette-tail-validation.json')
    p.add_argument('--out', type=Path)
    a = p.parse_args()
    native = json.loads(a.native.read_bytes())
    assert native['total_cases'] == 32 and len(native['cases']) == 16 and not native['probe_only']
    for row in native['cases']:
        captured = []
        for step in row['steps']:
            _, style, value, retained = (int(v, 16) for v in step['wrapper_input'])
            captured.append((retained & 0xFFFF0000) | (value & 0xFFFF) if step['tag'] == '0x44' else value)
        expected = simulate(row['allocation_success_fixtures'], captured)
        assert row['final_style_hex'] == expected['final_style'].hex()
        assert tuple(row['final_values']) == expected['final_values'] and tuple(row['final_tags']) == expected['final_tags']
        assert row['final_vector_hex'] == vector_bytes(row['final_values'], row['final_tags']).hex()
        for actual, ref in zip(row['steps'], expected['steps']):
            assert actual['actual_realloc_arguments'] == [hex(ref.input_pointer), ref.requested_bytes, '0x8003de90']
            assert actual['style_hex'] == ref.style_after.hex()
            assert actual['vector_hex'] == vector_bytes(ref.values_after, ref.tags_after).hex()
    receipt = dict(native_report_sha256=hashlib.sha256(a.native.read_bytes()).hexdigest(),
                   independent_reference_sha256=hashlib.sha256((Path(__file__).parent / 'reference-audit/style_reference.py').read_bytes()).hexdigest(),
                   review_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   distinct_schedules_checked=16, original_runs_already_in_report=32, native_runs_repeated=0,
                   captured_inputs_bound=True, all_stage_arguments_headers_vectors_match=True,
                   caller_frame_preserved_in_native_report=all(c['saved_caller_frame_preserved'] for c in native['cases']))
    if a.out:
        a.out.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
