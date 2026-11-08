"""Build synthetic ARM condition fixtures from real ARM926 execution, not LLM answers."""
from pathlib import Path
import hashlib,json,operator,struct
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC
from unicorn.arm_const import UC_CPU_ARM_926,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_LR,UC_ARM_REG_CPSR
ROOT=Path(__file__).resolve().parents[2];OUT=Path(__file__).resolve().parent
def signed(x):return x-(1<<32) if x&(1<<31) else x
conditions=[('BEQ',0,'equal',lambda a,b:a==b),('BNE',1,'not_equal',lambda a,b:a!=b),
 ('BHS',2,'unsigned_ge',lambda a,b:a>=b),('BLO',3,'unsigned_lt',lambda a,b:a<b),
 ('BHI',8,'unsigned_gt',lambda a,b:a>b),('BLS',9,'unsigned_le',lambda a,b:a<=b),
 ('BGE',10,'signed_ge',lambda a,b:signed(a)>=signed(b)),('BLT',11,'signed_lt',lambda a,b:signed(a)<signed(b)),
 ('BGT',12,'signed_gt',lambda a,b:signed(a)>signed(b)),('BLE',13,'signed_le',lambda a,b:signed(a)<=signed(b))]
pairs=[(0,0),(0,1),(1,0),(0xffffffff,0),(0,0xffffffff),(0x7fffffff,0x80000000),(0x80000000,0x7fffffff)]
rows=[]
for name,cond,relation,oracle in conditions:
 code=struct.pack('<6I',0xe1500001,(cond<<28)|0x0a000001,0xe3a00000,0xe12fff1e,0xe3a00001,0xe12fff1e)
 mu=Uc(UC_ARCH_ARM,UC_MODE_ARM);mu.ctl_set_cpu_model(UC_CPU_ARM_926)
 mu.mem_map(0x20000000,0x1000,UC_PROT_READ|UC_PROT_EXEC);mu.mem_write(0x20000000,code)
 observations=[]
 for a,b in pairs:
  for reg,val in ((UC_ARM_REG_R0,a),(UC_ARM_REG_R1,b),(UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_LR,0x20000ff0)):mu.reg_write(reg,val)
  mu.emu_start(0x20000000,0x20000ff0,count=20);got=bool(mu.reg_read(UC_ARM_REG_R0));assert got==oracle(a,b)
  observations.append({'left':a,'right':b,'branch_taken':got})
 rows.append({'id':name,'split':'train'if name in ('BEQ','BNE','BLO','BLE')else'held_out',
  'asm':'ARM mode\nCMP r0, r1\n'+name+' target','relation':relation,'branch_when_equal':bool(oracle(0,0)),
  'instruction_sha256':hashlib.sha256(code).hexdigest(),'observations':observations})
dataset={'schema':'ys4470.local-tools.conditions.v1','date':'2026-11-08','cpu':'UC_CPU_ARM_926',
 'scope':'Synthetic calibration, not additional original-firmware proof','oracle_checks':70,'cases':rows}
(OUT/'condition-fixtures.json').write_text(json.dumps(dataset,indent=2)+'\n',encoding='utf-8')
schema={'type':'object','additionalProperties':False,'required':['relation','branch_when_equal'],
 'properties':{'relation':{'type':'string','enum':[r[2]for r in conditions]},'branch_when_equal':{'type':'boolean'}}}
instruction='Classify the ARM conditional branch after CMP left,right. relation describes the comparison of left with right. branch_when_equal MUST answer: is this branch taken when the compared operands are equal? Return only JSON with relation and branch_when_equal.'
demos='\n'.join('Example '+r['asm'].replace('\n','; ')+' -> '+json.dumps({'relation':r['relation'],'branch_when_equal':r['branch_when_equal']})for r in rows if r['split']=='train')
tests=[{'description':r['id'],'vars':{'asm':r['asm'],'expected_relation':r['relation'],'expected_equal':r['branch_when_equal']},
 'assert':[{'type':'javascript','value':"const r=typeof output==='string'?JSON.parse(output):output;\nreturn r.relation===context.vars.expected_relation && r.branch_when_equal===context.vars.expected_equal;"},{'type':'finish-reason','value':'stop'}]}for r in rows if r['split']=='held_out']
config={'description':'Synthetic ARM condition calibration; no firmware or physical timing claim',
 'prompts':[instruction+'\n{{asm}}',instruction+'\n'+demos+'\nTask:\n{{asm}}'],
 'providers':[{'id':'ollama:chat:qwen2.5-coder:14b','config':{'num_predict':128,'num_ctx':8192,'temperature':0,'seed':4470,'format':schema,'keep_alive':'10m'}}],
 'tests':tests}
(OUT/'promptfooconfig.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'oracle_checks':70,'train':4,'held_out':6,'promptfoo_calls':12}))
