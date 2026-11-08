"""Freeze new comparison inputs; do not modify any previous model batch."""
import json
from pathlib import Path
from completion_gate import sha,atomic_json
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
job=HERE/'comparison';assert not (job/'manifest.json').exists();job.mkdir(exist_ok=True)
targets={'0x80003dbc':'0x80003dd4','0x80006e4c':'0x80006ecc','0x8005d048':'0x8005d1a0'}
tasks=[]
for item in json.loads((HERE/'packet-index.json').read_text())['packets']:
 p=ROOT/item['path'];data=json.loads(p.read_text())
 if data['binary']['version']!='V3.8':continue
 expected=targets[data['entry']];assert any(i['address']==expected for i in data['assembly'])
 for mode in ('legacy_window','full_packet'):
  tasks.append({'id':mode.replace('_','-')+'-'+data['entry'][2:],'context':mode,'packet':item['path'],
   'packet_sha256':sha(p.read_bytes()),'binary_sha256':data['binary']['sha256'],
   'question':'Report the instruction at '+expected+'. Keep the entry separate from that instruction address. State one limitation.',
   'review_expected_address':expected})
atomic_json(job/'manifest.json',{'schema':'ys4470.packet-worker.v1','endpoint':'http://127.0.0.1:11435','model':'qwen2.5-coder:14b',
 'lessons_sha256':sha((HERE/'LESSONS.md').read_bytes()),'tasks':tasks,
 'limits':['New controlled context comparison, not a replay of the old 31-task job or a general benchmark.',
   'Same version/hash/questions/model; legacy view is first eight instructions. Two questions are intentionally outside that window.']})
print(json.dumps({'new_tasks':len(tasks),'job':str(job.relative_to(ROOT))}))
