from pathlib import Path
import hashlib,importlib.util,json,struct,sys,urllib.request
ROOT=Path.cwd();TASK=ROOT/'contributions/EXT-EVIDENCE-AUDIT'
sys.path.insert(0,str(TASK))
import local_review_worker_v3 as worker
schema={'type':'object','additionalProperties':False,
 'required':['relation','at_equality','flag_source','milliseconds_proven'],
 'properties':{'relation':{'type':'string','enum':['unsigned_ge','signed_gt','unsigned_lt','signed_le']},
 'at_equality':{'type':'boolean'},'flag_source':{'type':'string','enum':['CMP','SUB']},'milliseconds_proven':{'type':'boolean'}}}
cases=[
 {'id':'unsigned-deadline','text':'Verified ARM excerpt:\nsub r0,r0,r4\ncmp r0,r5\nbhs target\nClassify the BHS relation on the compared operands, equality behavior and last flag source. No clock frequency is supplied.',
  'expected':dict(relation='unsigned_ge',at_equality=True,flag_source='CMP',milliseconds_proven=False)},
 {'id':'signed-length','text':'Verified ARM excerpt:\nldr r2,[r9,#0x28]\nldr ip,[r10]\ncmp r2,ip\nbgt wait\nClassify the BGT relation on the compared operands, equality behavior and last flag source. No physical time unit is supplied.',
  'expected':dict(relation='signed_gt',at_equality=False,flag_source='CMP',milliseconds_proven=False)}]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),worker.NoRedirect())
original_system=worker.SYSTEM;rows=[]
for taught in (False,True):
 worker.SYSTEM=original_system+('\n'+(TASK/'LESSONS.md').read_text(encoding='utf-8') if taught else '')
 for case in cases:
  r=worker.call(opener,'http://127.0.0.1:11435','qwen2.5-coder:14b',
   case['text']+'\nReturn only the four JSON fields in the schema.',[],220,schema)
  rows.append({'case':case['id'],'lessons_applied':taught,'expected':case['expected'],
   'actual':r.get('parsed'),'passed':not r['response_errors'] and r.get('parsed')==case['expected'],
   'elapsed_seconds':r['elapsed_seconds'],'metrics':r['metrics']})
# A real emulated negative control refutes the draft's claim that getter writes are unguarded.
sys.path[:0]=[str(ROOT/'tools'),str(ROOT/'work/analysis-python')]
spec=importlib.util.spec_from_file_location('fsm_deadline',ROOT/'contributions/COORD-FSM-TIMEOUT/trace_fsm_timeout.py')
fsm=importlib.util.module_from_spec(spec);spec.loader.exec_module(fsm)
raw=(ROOT/'original-firmware/V3.6/f1c100s.bin').read_bytes()
machine=fsm.Machine(raw);machine.kind='getter';machine.regs()
machine.mu.mem_write(fsm.FSM,struct.pack('<2I',0xe5801000,0xe12fff1e)) # test-only STR r1,[r0]; BX LR
machine.mu.reg_write(fsm.UC_ARM_REG_R0,fsm.ROOT+0xc);machine.mu.reg_write(fsm.UC_ARM_REG_R1,0xdeadbeef)
rejected=False
try:machine.mu.emu_start(fsm.FSM,0,count=4)
except AssertionError:rejected=True
assert rejected
result={'schema':'ys4470.local-lessons-check.v1','date':'2026-11-08','model':'qwen2.5-coder:14b',
 'training_type':'in_context_examples_only','weights_changed':False,'test_cases':2,'runs':rows,
 'without_lessons_passed':sum(r['passed'] for r in rows if not r['lessons_applied']),
 'with_lessons_passed':sum(r['passed'] for r in rows if r['lessons_applied']),
 'generalization_claim':False,'note':'Tiny sanity check only; no new firmware proof and no broad accuracy or speedup claim.',
 'negative_control':{'getter_write_guard_rejected_injected_store':rejected,'test_only_in_memory_mutation':True,'original_file_sha256':hashlib.sha256(raw).hexdigest()}}
(TASK/'lessons-evaluation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'without_lessons':result['without_lessons_passed'],'with_lessons':result['with_lessons_passed'],'cases':2,'negative_guard_rejected':rejected}))
