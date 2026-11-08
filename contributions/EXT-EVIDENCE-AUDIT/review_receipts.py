from pathlib import Path
import hashlib,json
root=Path('contributions/EXT-EVIDENCE-AUDIT');job=root/'jobs/2026-11-08-v3'
manifest=json.loads((job/'manifest.json').read_text(encoding='utf-8'))
assert json.loads((job/'status.json').read_text(encoding='utf-8'))['completed']==6
sources={s['id']:(job/s['file']).read_text(encoding='utf-8').splitlines() for s in manifest['sources']}
for s in manifest['sources']:assert hashlib.sha256((job/s['file']).read_bytes()).hexdigest()==s['sha256']
verdicts={
 'legacy-triage':[
 ('rejected','An unverified draft does not establish which binary or ISA generated an old export.'),
 ('rejected','A repeated prior-model profile claim is not primary build evidence.'),
 ('confirmed_scope_limit','No controlled physical profile latency evidence is supplied in this source package.'),
 ('confirmed_scope_limit','The candidate delay/caller semantics remain assigned to the next coordinator task.')],
 'deadline-precedence':[
 ('confirmed_existing','The original CMP immediate is present; this is an existing code fact.'),
 ('confirmed_existing','CMPNE follows the prior command comparison, as in the original ARM.'),
 ('rejected','This comparison is the state2 expected-header comparison, not an expiry comparison.'),
 ('rejected','Unsigned elapsed >= duration is not an explicit wrap-detection branch.')],
 'c-contract':[
 ('confirmed_existing','The C receive-count/header guard matches the already executed original branch.'),
 ('confirmed_existing','The adjacent BLE path establishes positive signed receive-count admission.'),
 ('confirmed_existing','The C signed required-length guard matches the already verified contract.'),
 ('confirmed_existing','CMP plus the adjacent BGT establishes the signed required-length test.')],
 'harness-guards':[
 ('rejected','Tick-prefix probes deliberately do not claim getter critical-entry semantics.'),
 ('rejected','Changing the harness assertion is not a counterexample under the fixed harness.'),
 ('rejected','Getter writes allow only stack/nesting; the emulated injected-store negative control is rejected.'),
 ('rejected','Changing an expected input is not evidence that the original fixed-input test escapes validation.')],
 'coverage-accounting':[
 ('rejected','Unsigned modulo32 arithmetic is intentional and 0x80000000 is an executed boundary fixture.'),
 ('rejected','The full test matrix completed in seconds; no excessive-runtime defect is demonstrated.'),
 ('rejected','The condition selects saved examples after every case was executed and checked.'),
 ('confirmed_scope_limit','UART send is an explicitly modeled leaf; full UART behavior is outside this proof.')],
 'database-scope':[
 ('confirmed_scope_limit','Historical Beta3 annotation is explicitly separate from the new original-only proof.'),
 ('confirmed_scope_limit','Only the UART-send leaf is modeled; the surrounding original setup instructions execute.'),
 ('confirmed_scope_limit','The duration40 fixture is not actual Beta3 image execution.'),
 ('confirmed_scope_limit','Physical clock frequency and milliseconds remain unassigned.')]}
rows=[];tokens=0;elapsed=0;response_errors=0
for task in manifest['tasks']:
 d=json.loads((job/(task['id']+'.json')).read_text(encoding='utf-8'))
 assert d['source_manifest_sha256']==hashlib.sha256((job/'manifest.json').read_bytes()).hexdigest()
 tokens+=d['metrics']['eval_count'];elapsed+=d['elapsed_seconds']
 response_errors+=len(d['response_errors'])
 findings=d['parsed']['findings'];assert len(findings)==len(verdicts[task['id']])
 for i,f in enumerate(findings):
  status='rejected';resolved=None;quote=f['quote']
  allowed=next((s for s in task['sources']if s['id']==f['source']),None)
  if allowed:
   lines=sources[f['source']];lo,hi=allowed['start'],allowed['end']
   if lo<=f['line_start']<=f['line_end']<=hi and quote in '\n'.join(lines[f['line_start']-1:f['line_end']]):
    status='exact';resolved=[f['line_start'],f['line_end']]
   else:
    text='\n'.join(lines[lo-1:hi]);positions=[];start=0
    while True:
     pos=text.find(quote,start)
     if pos<0:break
     positions.append(pos);start=pos+1
    if len(positions)==1:
     start_line=lo+text[:positions[0]].count('\n')
     resolved=[start_line,start_line+quote.count('\n')];status='unique_quote_relocated'
  verdict,reason=verdicts[task['id']][i]
  rows.append({'task':task['id'],'finding_index':i,'statement':f['statement'],'source':f['source'],
   'original_lines':[f['line_start'],f['line_end']],'quote_status':status,'tool_resolved_lines':resolved,
   'coordinator_verdict':verdict,'reason':reason})
result={'schema':'ys4470.local-review-receipt.v1','date':'2026-11-08','model':'qwen2.5-coder:14b',
 'reviews_completed':6,'generated_review_tokens':tokens,'model_request_seconds':round(elapsed,3),
 'incomplete_or_invalid_response_errors':response_errors,'claim_count':len(rows),
 'new_firmware_claims_accepted':0,'automatic_integration':False,
 'citation_counts':{s:sum(r['quote_status']==s for r in rows)for s in ('exact','unique_quote_relocated','rejected')},
 'verdict_counts':{s:sum(r['coordinator_verdict']==s for r in rows)for s in ('confirmed_existing','confirmed_scope_limit','rejected')},
 'lessons_check':'lessons-evaluation.json','claims':rows}
(root/'coordinator-review.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items()if k!='claims'},indent=2))
