"""Validate generated reference evidence and actual PyGhidra exports."""
import argparse
import gzip
import hashlib
import io
import json
import unittest
from pathlib import Path

from analyze_f1c100s_references import KNOWN_HASHES


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--analysis-dir', type=Path, required=True)
    ap.add_argument('--ghidra-dir', type=Path, required=True)
    args = ap.parse_args()
    path = args.analysis_dir / 'reference-analysis.json'
    analysis = json.loads(path.read_text())
    versions, graphs = [], []
    for v in analysis['versions']:
        assert v['input_sha256'] == KNOWN_HASHES[v['version']]
        p = args.ghidra_dir / (v['version'].replace('.', '_') + '_inventory.json')
        inventory = json.loads(p.read_text())
        assert inventory['input']['sha256'] == v['input_sha256']
        assert len(inventory['functions']) == 13
        assert all(f['status'] == 'exported' for f in inventory['functions'])
        labels = inventory['reference_labels']
        assert len(labels) == 6
        gate = next(l for l in labels if l['address'] == '0x80006e4c')
        assert gate['status'] == 'preserved_existing_name' and gate['ghidra_name'] == 'SoundControlGate'
        assert sum(l['status'] == 'named_from_independent_proof' for l in labels) == 5
        exports = inventory['reference_function_exports']
        assert len(exports) == 6 and all(f['decompiled_c'] and f['assembly'] for f in exports)
        assert all('YS4470 reference proof:' in f['comment'] for f in exports)
        assert sum(w['passed'] for w in v['watchdog_experiments']) == 16
        graph = gzip.decompress((args.analysis_dir / v['call_graph']['file']).read_bytes())
        assert hashlib.sha256(graph).hexdigest() == v['call_graph']['uncompressed_sha256']
        edges = json.loads(graph)['edges']
        assert len(edges) == v['direct_bl_candidate_count']
        graphs.append(edges)
        versions.append({'version': v['version'], 'input_sha256': v['input_sha256'],
                         'inventory_sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                         'original_seed_exports_passed': 13, 'reference_labels': labels,
                         'reference_function_exports': exports, 'watchdog_cases_passed': 16})
    assert graphs[0] == graphs[1]
    for field in ('mmio_literal_candidates', 'cp15_candidates', 'watchdog_experiments'):
        assert analysis['versions'][0][field] == analysis['versions'][1][field]
    suite = unittest.defaultTestLoader.discover(str(Path(__file__).parent), pattern='test_reference_pipeline.py')
    capture = io.StringIO()
    result = unittest.TextTestRunner(stream=capture, verbosity=2).run(suite)
    assert result.wasSuccessful(), capture.getvalue()
    report = {'schema': 'ys4470.f1c100s.reference-validation.v1',
              'reference_analysis_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'unit_tests_passed': result.testsRun, 'unit_test_log': capture.getvalue(),
              'call_candidate_graphs_equal': True, 'mmio_cp15_watchdog_results_equal': True,
              'versions': versions,
              'limits': ['Local disposable Ghidra projects; exports are the durable artifact.',
                         'Mock-based name/comment preservation tests supplement real name-preservation exports.',
                         'Raw BL/MMIO candidates are not proven function relationships or live hardware observations.']}
    dest = args.analysis_dir / 'pyghidra-reference-validation.json'
    dest.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'unit_tests': result.testsRun, 'ghidra_reference_exports': 12,
                      'watchdog_cases': 32, 'graphs_equal': True, 'output': str(dest)}))


if __name__ == '__main__':
    main()
