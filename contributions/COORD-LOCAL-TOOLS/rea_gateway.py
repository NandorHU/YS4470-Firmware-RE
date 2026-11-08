"""A narrowly scoped local DSPy -> MCP -> REA bridge; no arbitrary tools or paths."""
from __future__ import annotations
import asyncio,hashlib,json,os,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
os.environ['DSPY_CACHEDIR']=str(ROOT/'work/local-llm-tools/dspy-cache')
os.environ['LITELLM_LOCAL_MODEL_COST_MAP']='true';os.environ['NO_PROXY']='127.0.0.1,localhost'
import dspy
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
PIN='7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290'
ENTRY,BASE=0x80061f84,0x7fffffe0
def read_result(result):
    wire=result.model_dump(mode='json',by_alias=True)
    if wire.get('isError'):raise RuntimeError(str(wire['content'])[:1600])
    data=wire.get('structuredContent')
    if data is None:
        data=json.loads(next(c['text']for c in wire['content']if c['type']=='text'))
    return data
def policy(operation):
    if operation!='tick_snapshot_evidence':raise PermissionError('Only the fixed read-only getter view is delegated')
async def main():
    out=HERE/'rea-model-smoke.json';assert not out.exists(),'Do not repeat a completed smoke test'
    cfg=json.loads((ROOT/'work/local-llm-tools/machine.json').read_text(encoding='utf-8'))
    firmware=ROOT/'original-firmware/V3.8/f1c100s.bin';raw=firmware.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==PIN
    proof=json.loads((ROOT/'contributions/COORD-FSM-TIMEOUT/fsm-timeout.json').read_text(encoding='utf-8'))
    window=proof['versions'][1]['raw_windows'][hex(ENTRY)]
    assert hashlib.sha256(raw[ENTRY-BASE:0x80061fa0-BASE]).hexdigest()==window['sha256']
    word=struct.unpack_from('<I',raw,0x80061fa0-BASE)[0]+12
    assert word==0x805abbc8
    blocked=[]
    for op in ('write_bytes','execute_command','flash','rename_function'):
        try:policy(op)
        except PermissionError:blocked.append(op)
    calls=[];cached=None
    env={'GHIDRA_INSTALL_DIR':cfg['ghidra'],'JAVA_HOME':cfg['java']}
    params=StdioServerParameters(command=cfg['node'],args=[cfg['rea_script'],'mcp'],env=env)
    errpath=ROOT/'work/local-llm-tools/rea-stderr.log'
    with errpath.open('w',encoding='utf-8') as err:
      async with stdio_client(params,errlog=err) as (read,write):
        async with ClientSession(read,write,read_timeout_seconds=60) as session:
          initialized=await session.initialize()
          assert initialized.server_info.name=='rea'
          async def read_tick_snapshot_evidence()->str:
            """Read the fixed original tick-getter source and REA byte-identity evidence.
            No arguments, arbitrary addresses, commands or mutations are admitted.
            Assembly comes from the existing hash-guarded original-code export;
            REA supplies the file identity/window observation, not ARM decompilation."""
            nonlocal cached
            policy('tick_snapshot_evidence')
            if cached is not None:return cached
            result=await session.call_tool('inspect_byte_entropy',arguments={
              'path':str(firmware),'offset':ENTRY-BASE,'length':32,'block_size':256,'detail':'complete'})
            evidence=read_result(result);n=evidence['normalized_result']
            assert n['artifact']['sha256']==PIN and n['window']=={'offset':ENTRY-BASE,'length':32}
            calls.append({'operation':'inspect_byte_entropy','evidence_id':evidence['evidence_id'],
              'artifact_sha256':n['artifact']['sha256'],'window':n['window']})
            cached=json.dumps({'entry':hex(ENTRY),'returned_word_address':hex(word),
              'rea_evidence_id':evidence['evidence_id'],'rea_scope':'file identity and bounded entropy only',
              'assembly_source':'hash-guarded original ARM export; not a live REA ARM decompilation',
              'assembly':window['assembly'],'literal_pointer':hex(word-12),
              'timing_limit':'Raw counter snapshot; physical tick frequency and milliseconds are unproven.'})
            return cached
          lm=dspy.LM('ollama_chat/qwen2.5-coder:14b',api_base='http://127.0.0.1:11435/v1',
            api_key='local-only',temperature=0,max_tokens=600,cache=False,num_retries=0,timeout=30,engine='auto')
          dspy.configure_cache(enable_disk_cache=False,enable_memory_cache=False)
          dspy.configure(lm=lm,adapter=dspy.JSONAdapter(use_native_function_calling=False))
          tool=dspy.Tool(read_tick_snapshot_evidence,name='read_tick_snapshot_evidence')
          agent=dspy.ReAct('question -> answer',tools=[tool],max_iters=2)
          question=('Call read_tick_snapshot_evidence exactly once before answering. '
            'Report the original entry, returned-word address, REA evidence id and one physical-time limitation. '
            'Do not infer unsupported hardware roles or milliseconds; preserve the separate providers.')
          prediction=await agent.acall(question=question)
          answer=prediction.answer
          correct=bool(calls) and hex(word)in answer.lower() and calls[0]['evidence_id']in answer
          bundle=ROOT/'work/local-llm-tools/rea-evidence-bundle.json'
          export=await session.call_tool('export_evidence_bundle',arguments={'path':str(bundle),'overwrite':False})
          read_result(export)
          await session.call_tool('close_binary',arguments={})
          report={'schema':'ys4470.local-tools.rea-smoke.v1','server':initialized.server_info.model_dump(),
            'model':'qwen2.5-coder:14b','model_provider':'loopback:11435','delegated_tool_names':['read_tick_snapshot_evidence'],
            'blocked_operations':blocked,'rea_calls':calls,'model_calls':len(lm.history),
            'answer':answer,'passed':correct,'weights_changed':False,'device_access':False,
            'limits':['REA Windows Ghidra P0 does not admit this raw ARM firmware.',
              'REA access tested here is read-only byte identity/entropy. Assembly is the existing verified export.',
              'A successful tool smoke is not evidence of improved general model reasoning.']}
          out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
          print(json.dumps({'passed':correct,'rea_calls':len(calls),'model_calls':len(lm.history),'blocked_operations':blocked}))
if __name__=='__main__':asyncio.run(main())
