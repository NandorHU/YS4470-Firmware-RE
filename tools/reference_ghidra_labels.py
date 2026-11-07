"""Proof-gated reference labels. Candidate scores never authorize renaming."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE = 0x7fffffe0
PROOF = 'prior_bounded_original_ARM926_execution'


def validated_labels(report_path: Path, version: str, raw: bytes):
    report = json.loads(report_path.read_text(encoding='utf-8'))
    if report['schema'] not in ('ys4470.f1c100s.reference-analysis.v1', 'ys4470.intc-timer-path.v1',
                               'ys4470.fast-cont-filter.v1', 'ys4470.result-freshness.v1'):
        raise ValueError('unsupported reference report')
    matches = [v for v in report['versions'] if v['version'] == version]
    if len(matches) != 1:
        raise ValueError('version must occur exactly once')
    item = matches[0]
    if item['input_sha256'] != hashlib.sha256(raw).hexdigest():
        raise ValueError('reference report firmware hash mismatch')
    result, seen = [], set()
    for label in item.get('approved_labels', []):
        if label.get('proof') not in (PROOF, 'bounded_original_ARM926_execution') or label.get('confidence') != 1.0 or not label.get('evidence'):
            raise ValueError('label has no independent execution proof')
        address = int(label['address'], 16)
        offset, count = address - BASE, label['guard_bytes']
        if address in seen or address % 4 or count < 32 or not 0 <= offset <= len(raw) - count:
            raise ValueError('invalid/duplicate label address or guard')
        seen.add(address)
        if hashlib.sha256(raw[offset:offset + count]).hexdigest() != label['guard_sha256']:
            raise ValueError('label byte guard mismatch')
        name = label['name']
        if not name.startswith('RE_') or not name.replace('_', '').isalnum():
            raise ValueError('invalid analysis label')
        result.append(label)
    return result


def apply_labels(program, flat, labels):
    from ghidra.program.model.symbol import SourceType
    records = []
    for item in labels:
        addr = flat.toAddr(item['address'].removeprefix('0x'))
        function = program.getFunctionManager().getFunctionAt(addr)
        if function is None:
            containing = program.getFunctionManager().getFunctionContaining(addr)
            if containing is not None:
                records.append({**item, 'status': 'preserved_existing_containing_function'})
                continue
            flat.disassemble(addr)
            function = flat.createFunction(addr, None)
        if function is None:
            records.append({**item, 'status': 'function_not_created'})
            continue
        source = function.getSymbol().getSource()
        old_name = str(function.getName())
        if source == SourceType.DEFAULT:
            function.setName(item['name'], SourceType.ANALYSIS)
            status = 'named_from_independent_proof'
        elif old_name == item['name']:
            status = 'already_named'
        else:
            status = 'preserved_existing_name'
        marker = f"YS4470 reference proof: {item['proof']}; {item['evidence']}; proposed {item['name']}"
        comment = function.getComment() or ''
        if marker not in comment:
            function.setComment(comment + ('\n' if comment else '') + marker)
        records.append({**item, 'status': status, 'ghidra_name': str(function.getName()),
                        'previous_name': old_name})
    return records
