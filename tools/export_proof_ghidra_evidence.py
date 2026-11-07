"""Verify proof-labelled Ghidra runs and export their durable evidence."""
import argparse
import hashlib
import io
import json
import unittest
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--proof', type=Path, required=True)
    ap.add_argument('--ghidra-dir', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--run-label-tests', action='store_true')
    args = ap.parse_args()
    proof = json.loads(args.proof.read_text())
    versions = []
    for v in proof['versions']:
        p = args.ghidra_dir / (v['version'].replace('.', '_') + '_inventory.json')
        inv = json.loads(p.read_text())
        assert inv['input']['sha256'] == v['input_sha256']
        assert len(inv['reference_labels']) == len(v['approved_labels'])
        for expected, actual in zip(v['approved_labels'], inv['reference_labels']):
            assert all(actual[k] == val for k, val in expected.items())
            assert actual['status'] in ('named_from_independent_proof', 'already_named', 'preserved_existing_name')
        exports = inv['reference_function_exports']
        assert len(exports) == len(v['approved_labels'])
        assert all(x['assembly'] and x['decompiled_c'] for x in exports)
        assert all('YS4470 reference proof:' in x['comment'] for x in exports)
        versions.append({'version':v['version'],'input_sha256':v['input_sha256'],
                         'analysis_mode':inv['import']['analysis_mode'],
                         'inventory_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),
                         'reference_labels':inv['reference_labels'],'functions':exports})
    if len(versions) == 2:
        for first, second in zip(versions[0]['functions'], versions[1]['functions']):
            assert first['address'] == second['address'] and first['assembly'] == second['assembly']
    report = {'schema':'ys4470.proof-ghidra-evidence.v1', 'date':'2026-11-07',
              'proof_sha256':hashlib.sha256(args.proof.read_bytes()).hexdigest(),
              'versions':versions, 'assembly_equal_between_originals':True,
              'limits':['Fresh disposable projects; exports are the durable artifact.',
                        'Existing analyst names/comments are preserved, not replaced.',
                        'Inferred Ghidra bodies are separate from stated original-code execution scopes.']}
    if args.run_label_tests:
        suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_reference_pipeline.py')
        capture = io.StringIO(); result = unittest.TextTestRunner(stream=capture, verbosity=2).run(suite)
        assert result.wasSuccessful(), capture.getvalue()
        report['label_pipeline_tests_passed'] = result.testsRun
        report['test_log'] = capture.getvalue()
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'output':str(args.out),'exports':sum(len(v['functions']) for v in versions),
                      'label_tests':report.get('label_pipeline_tests_passed')}))


if __name__=='__main__': main()
