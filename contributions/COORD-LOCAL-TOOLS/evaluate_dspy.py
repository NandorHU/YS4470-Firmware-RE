"""Isolated local DSPy calibration; examples change, model weights do not."""
from pathlib import Path
import json,os,time
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
os.environ['DSPY_CACHEDIR']=str(ROOT/'work/local-llm-tools/dspy-cache')
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='true'
os.environ['NO_PROXY']='127.0.0.1,localhost'
import dspy
from typing import Literal
class ARMCondition(dspy.Signature):
    """Classify the conditional ARM branch following CMP left,right.
    relation describes left compared with right. branch_when_equal means:
    is this conditional branch taken when the two compared operands are EQUAL?
    Use signedness from the branch mnemonic. Return both fields."""
    asm:str=dspy.InputField()
    relation:Literal['equal','not_equal','unsigned_ge','unsigned_lt','unsigned_gt','unsigned_le','signed_ge','signed_lt','signed_gt','signed_le']=dspy.OutputField()
    branch_when_equal:bool=dspy.OutputField()
def local_lm():
    return dspy.LM('ollama_chat/qwen2.5-coder:14b',api_base='http://127.0.0.1:11435/v1',
      api_key='local-only',temperature=0,max_tokens=256,cache=False,num_retries=0,timeout=30,engine='auto')
def main():
    destination=HERE/'dspy-results.json';assert not destination.exists(),'Do not repeat a completed calibration'
    dataset=json.loads((HERE/'condition-fixtures.json').read_text(encoding='utf-8'))
    train=[dspy.Example(asm=r['asm'],relation=r['relation'],branch_when_equal=r['branch_when_equal']).with_inputs('asm') for r in dataset['cases'] if r['split']=='train']
    dspy.configure_cache(enable_disk_cache=False,enable_memory_cache=False)
    lm=local_lm();dspy.configure(lm=lm,adapter=dspy.JSONAdapter(use_native_function_calling=False))
    baseline=dspy.Predict(ARMCondition)
    optimized=dspy.LabeledFewShot(k=4).compile(baseline,trainset=train,sample=False)
    optimized.save(HERE/'dspy-program.json')
    results=[];started=time.monotonic()
    for name,program in (('baseline',baseline),('labeled_fewshot',optimized)):
      for row in dataset['cases']:
        if row['split']!='held_out':continue
        if time.monotonic()-started>120:
          (HERE/'dspy-partial.json').write_text(json.dumps({'complete':False,'reason':'120s budget','results':results},indent=2)+'\n',encoding='utf-8')
          raise TimeoutError('Local calibration wall budget exceeded; partial results preserved')
        t=time.monotonic()
        try:
          p=program(asm=row['asm']);actual={'relation':p.relation,'branch_when_equal':p.branch_when_equal}
          ok=actual=={k:row[k]for k in ('relation','branch_when_equal')}
          results.append({'program':name,'case':row['id'],'actual':actual,'passed':ok,'seconds':round(time.monotonic()-t,3)})
        except Exception as error:results.append({'program':name,'case':row['id'],'passed':False,'error':str(error)})
        (HERE/'dspy-partial.json').write_text(json.dumps({'complete':False,'results':results},indent=2)+'\n',encoding='utf-8')
    report={'schema':'ys4470.local-tools.dspy.v1','model':'qwen2.5-coder:14b','endpoint':'loopback:11435',
      'optimizer':'LabeledFewShot(k=4)','weights_changed':False,'train_groups':4,'held_out_groups':6,'complete':True,
      'total_seconds':round(time.monotonic()-started,3),'provider_calls':len(lm.history),'results':results,
      'scores':{n:sum(r['passed']for r in results if r['program']==n)for n in ('baseline','labeled_fewshot')},
      'limits':['Single small synthetic condition test; no general firmware accuracy or productivity claim.',
                'Dataset split is by branch mnemonic; this is not a broad held-out firmware corpus.']}
    destination.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:report[k]for k in ('scores','provider_calls','total_seconds')}))
if __name__=='__main__':main()
