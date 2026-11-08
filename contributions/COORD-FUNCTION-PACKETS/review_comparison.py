"""Coordinator's original-byte review of the frozen comparison; no inference."""
import json
from pathlib import Path
from completion_gate import sha,atomic_json,classify,grounding_errors
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;job=HERE/'comparison'
assert not (HERE/'comparison-review.json').exists(),'Completed review exists; retain it without rewriting'
mraw=(job/'manifest.json').read_bytes();m=json.loads(mraw);rows=[];states={}
for task in m['tasks']:
    dest=job/(task['id']+'.json');raw=dest.read_bytes();d=json.loads(raw);assert d['manifest_sha256']==sha(mraw)
    ppath=ROOT/task['packet'];praw=ppath.read_bytes();assert sha(praw)==task['packet_sha256'];p=json.loads(praw)
    original=(ROOT/p['binary']['path']).read_bytes();assert sha(original)==task['binary_sha256']
    r=d['attempts'][-1];g=classify(r['response']);obj=g['parsed'];provided=p['assembly']if task['context']=='full_packet'else p['assembly'][:8]
    formal=g['state']=='draft'and not grounding_errors(obj,p,provided)
    expected=next(i for i in p['assembly']if i['address']==task['review_expected_address'])
    offset=int(expected['address'],16)-0x7fffffe0
    assert bytes.fromhex(expected['bytes'])==original[offset:offset+4]
    # This bounded review checks the exact requested instruction, not arbitrary prose.
    correct=formal and obj['evidence_address']==expected['address']and obj['quote']in(expected['assembly'],expected['address']+' '+expected['assembly'])
    state='verified'if correct else'needs_split';states[task['id']]=state
    row={'task':task['id'],'context':task['context'],'raw_result_sha256_before_review':sha(raw),
      'formal_grounding_passed':formal,'requested_original_instruction_verified':correct,'expected':expected,
      'attempts':len(d['attempts']),'seconds':round(sum(a['seconds']for a in d['attempts']),3),
      'generated_tokens':sum(a['response'].get('eval_count',0)for a in d['attempts']),
      'scope':'Exact requested instruction and identity only; other model prose is not promoted.'}
    rows.append(row)
    d['coordinator_review']={'state':state,'response_sha256':sha(json.dumps(r['response'],sort_keys=True).encode()),'scope':row['scope'],'original_binary_sha256':sha(original)}
    atomic_json(dest,d)
summary={mode:{'verified':sum(r['requested_original_instruction_verified']for r in rows if r['context']==mode),
  'tasks':3,'seconds_including_retries':round(sum(r['seconds']for r in rows if r['context']==mode),3)}for mode in('legacy_window','full_packet')}
atomic_json(HERE/'comparison-review.json',{'schema':'ys4470.packet-comparison.v1','summary':summary,'rows':rows,
 'initial_gate_bug':'The model quoted exact address+assembly lines. Initial validator accepted assembly-only; revalidated saved replies without new model calls.',
 'limits':['Three controlled questions, not a general model quality or productivity benchmark.',
   'Two requested instructions were absent from the legacy eight-instruction windows by design.',
   'Twelve calls include retries due to the original quote-format gate bug; timing is not a fair steady-state speed comparison.',
   'Original attempts and original gate records were retained. Only bounded coordinator reviews were appended.']})
atomic_json(job/'status-reviewed.json',{'state':'needs_split_for_two_missing_context_tasks','states':states,'verified_count':sum(s=='verified'for s in states.values()),'new_model_calls':0})
print(json.dumps(summary))
