"""Negative controls for reference matching, MMIO tracking and Ghidra labels."""
import copy
import hashlib
import json
import struct
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from analyze_f1c100s_references import BASE, follow_literal, masked_matches, survey
from reference_ghidra_labels import PROOF, apply_labels, validated_labels


def fixture(words):
    return bytes(32) + struct.pack('<' + 'I' * len(words), *words) + bytes(128)


class ReferenceTests(unittest.TestCase):
    def test_masked_full_body_and_mutation(self):
        # Seven distinct ARM instructions; a matching short prologue is not enough.
        data = struct.pack('<7I', 0xe3a00001, 0xe2801002, 0xe2812003,
                           0xe2823004, 0xe2834005, 0xe2845006, 0xe12fff1e)
        f = {'data': data, 'relocations': []}
        good = fixture(struct.unpack('<7I', data))
        self.assertEqual(masked_matches(good, f)[0]['address'], '0x80000000')
        bad = bytearray(good); bad[32 + 8] ^= 1
        self.assertEqual(masked_matches(bytes(bad), f), [])
        self.assertEqual(masked_matches(good, {'data': data[:16], 'relocations': []}), [])

    def test_relocation_only_is_candidate(self):
        data = bytes(range(64))
        raw = bytearray(bytes(32) + data)
        raw[32 + 24:32 + 28] = b'\xaa' * 4
        f = {'data': data, 'relocations': [{'offset': 24, 'type': 28}]}
        result = masked_matches(bytes(raw), f)
        self.assertEqual(len(result), 1)
        self.assertFalse(result[0]['relocation_targets_verified'])
        self.assertLess(result[0]['confidence'], 1.0)
        raw[32 + 28] ^= 1
        self.assertEqual(masked_matches(bytes(raw), f), [])

    def test_mmio_and_control_transfer(self):
        raw = fixture([0xe59f0008, 0xe5901000, 0xe5802004, 0xe12fff1e, 0x01c21000])
        refs, edges, cpu, funcs = survey(raw, [{'base': 0x01c21000, 'name': 'PWM'}])
        ref = refs[0]
        self.assertEqual(ref['literal_address'], '0x80000010')
        self.assertEqual([(x['operation'], x['address']) for x in follow_literal(raw, ref)],
                         [('read', '0x1c21000'), ('write', '0x1c21004')])
        self.assertEqual(edges, [])

    def test_loaded_value_does_not_become_pointer(self):
        raw = fixture([0xe59f0008, 0xe5900000, 0xe5801004, 0xe12fff1e, 0x01c21000])
        ref = survey(raw, [{'base': 0x01c21000, 'name': 'PWM'}])[0][0]
        self.assertEqual(len(follow_literal(raw, ref)), 1)

    def test_branch_stops_before_later_store(self):
        raw = fixture([0xe59f0008, 0xea000000, 0xe5801004, 0xe12fff1e, 0x01c21000])
        ref = survey(raw, [{'base': 0x01c21000, 'name': 'PWM'}])[0][0]
        self.assertEqual(follow_literal(raw, ref), [])

    def test_label_hash_and_proof_guards(self):
        raw = bytes(range(128))
        item = {'address': hex(BASE + 32), 'name': 'RE_Test', 'confidence': 1.0,
                'proof': PROOF, 'evidence': 'bounded-execution.json', 'guard_bytes': 64,
                'guard_sha256': hashlib.sha256(raw[32:96]).hexdigest()}
        report = {'schema': 'ys4470.f1c100s.reference-analysis.v1', 'versions': [
            {'version': 'test', 'input_sha256': hashlib.sha256(raw).hexdigest(), 'approved_labels': [item]}]}
        def validate(r, image=raw):
            with patch.object(Path, 'read_text', return_value=json.dumps(r)):
                return validated_labels(Path('fixture.json'), 'test', image)
        self.assertEqual(len(validate(report)), 1)
        for field, value in [('proof', 'high_similarity'), ('guard_sha256', '0' * 64),
                             ('confidence', 0.99), ('guard_bytes', 4), ('name', 'FUN_guess')]:
            bad = copy.deepcopy(report); bad['versions'][0]['approved_labels'][0][field] = value
            with self.assertRaises(ValueError): validate(bad)
        with self.assertRaises(ValueError): validate(report, raw[:-1] + b'\x00')
        bad = copy.deepcopy(report); bad['versions'][0]['approved_labels'].append(item)
        with self.assertRaises(ValueError): validate(bad)

    def test_preserve_existing_names_comments_and_idempotence(self):
        class Function:
            def __init__(self, source, name): self.source, self.name, self.comment = source, name, 'Analyst note'
            def getSymbol(self): return self
            def getSource(self): return self.source
            def getName(self): return self.name
            def getComment(self): return self.comment
            def setComment(self, value): self.comment = value
            def setName(self, value, source): self.name, self.source = value, source
        st = types.SimpleNamespace(DEFAULT=0, ANALYSIS=1, USER_DEFINED=2, IMPORTED=3)
        fake_module = types.ModuleType('ghidra.program.model.symbol'); fake_module.SourceType = st
        item = {'address': '0x8000302c', 'name': 'RE_Test', 'proof': PROOF, 'evidence': 'test.json'}
        for source in (st.DEFAULT, st.ANALYSIS, st.USER_DEFINED, st.IMPORTED):
            function = Function(source, 'existing_name')
            manager = types.SimpleNamespace(getFunctionAt=lambda a: function)
            program = types.SimpleNamespace(getFunctionManager=lambda: manager)
            flat = types.SimpleNamespace(toAddr=lambda a: a)
            with patch.dict('sys.modules', {'ghidra.program.model.symbol': fake_module}):
                apply_labels(program, flat, [item]); apply_labels(program, flat, [item])
            self.assertEqual(function.name, 'RE_Test' if source == st.DEFAULT else 'existing_name')
            self.assertTrue(function.comment.startswith('Analyst note\n'))
            self.assertEqual(function.comment.count('YS4470 reference proof:'), 1)

    def test_emulation_report_schemas_and_unknown_rejection(self):
        raw = bytes(range(128))
        label = {'address': hex(BASE+32), 'name':'RE_Verified', 'confidence':1.0,
                 'proof':'bounded_original_ARM926_execution', 'evidence':'test.json',
                 'guard_bytes':64, 'guard_sha256':hashlib.sha256(raw[32:96]).hexdigest()}
        for schema in ('ys4470.intc-timer-path.v1','ys4470.fast-cont-filter.v1','unknown'):
            report = {'schema':schema,'versions':[{'version':'test','input_sha256':hashlib.sha256(raw).hexdigest(),'approved_labels':[label]}]}
            with patch.object(Path, 'read_text', return_value=json.dumps(report)):
                if schema == 'unknown':
                    with self.assertRaises(ValueError): validated_labels(Path('test.json'),'test',raw)
                else:
                    self.assertEqual(validated_labels(Path('test.json'),'test',raw),[label])


if __name__ == '__main__':
    unittest.main()
