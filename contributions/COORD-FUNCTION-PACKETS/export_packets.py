"""Read originals and existing projects; export complete local CFGs, rollback edits."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM,CS_GRP_CALL
from capstone.arm import ARM_INS_B,ARM_INS_BX,ARM_OP_IMM,ARM_OP_MEM,ARM_OP_REG,ARM_REG_PC,ARM_REG_LR,ARM_CC_AL
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
BASE=0x7fffffe0;REV='ys4470.function-packet.v1'
SEEDS=[(0x80003dbc,'GaugeCmdTask','static_task_name_binding'),
       (0x80006e4c,'SoundControlGate','prior_bounded_original_execution'),
       (0x8005d048,'MeasurementRefreshCallback','prior_bounded_original_execution')]
def sha(raw):return hashlib.sha256(raw).hexdigest()
def hx(n):return hex(int(n)&0xffffffff)
def cfg(raw,entry):
    md=Cs(CS_ARCH_ARM,CS_MODE_ARM);md.detail=True
    pending=[entry];instructions={};edges=[];calls=[];unresolved=[]
    while pending:
        a=pending.pop()
        if a in instructions:continue
        if not entry<=a<entry+0x1000 or a%4:raise ValueError('Escaped local body '+hx(a))
        ins=next(md.disasm(raw[a-BASE:a-BASE+4],a,count=1),None)
        if ins is None or ins.size!=4:raise ValueError('Invalid ARM instruction '+hx(a))
        instructions[a]=ins;fall=a+4;targets=[];conditional=ins.cc!=ARM_CC_AL
        if ins.group(CS_GRP_CALL):
            target=(ins.operands[0].imm&0xffffffff) if ins.operands[0].type==ARM_OP_IMM else None
            calls.append({'site':hx(a),'target':None if target is None else hx(target),'resolved':target is not None,'kind':'call'})
            targets=[fall]
        elif ins.id==ARM_INS_B:
            target=ins.operands[0].imm&0xffffffff
            if entry<=target<entry+0x1000:targets=[target]
            else:calls.append({'site':hx(a),'target':hx(target),'resolved':True,'kind':'external_branch_boundary'})
            if conditional:targets.append(fall)
        elif ins.id==ARM_INS_BX:
            if ins.operands[0].reg!=ARM_REG_LR:unresolved.append({'site':hx(a),'assembly':ins.mnemonic+' '+ins.op_str})
            edges.append({'from':hx(a),'to':None,'kind':'return'if ins.operands[0].reg==ARM_REG_LR else'indirect'})
            if conditional:targets=[fall]
        elif ARM_REG_PC in ins.regs_access()[1]:
            # Explicit stack restore of PC is a return; other PC stores are unresolved.
            is_return=ins.mnemonic.startswith(('pop','ldm')) or (ins.mnemonic.startswith('ldr')and '[sp' in ins.op_str)
            if not is_return:unresolved.append({'site':hx(a),'assembly':ins.mnemonic+' '+ins.op_str})
            edges.append({'from':hx(a),'to':None,'kind':'return'if is_return else'indirect'})
            if conditional:targets=[fall]
        else:targets=[fall]
        for t in targets:edges.append({'from':hx(a),'to':hx(t),'kind':'local'});pending.append(t)
        if len(instructions)>1024:raise ValueError('CFG budget exceeded')
    return instructions,edges,calls,unresolved

def blocks(ins,edges):
    addresses=set(ins);pred={a:[]for a in addresses};succ={a:[]for a in addresses}
    for e in edges:
        if e['to'] is not None:
            a,b=int(e['from'],16),int(e['to'],16)
            if b in pred:pred[b].append(a);succ[a].append(b)
    starts={min(addresses)}
    for a in addresses:
        if len(pred[a])!=1 or pred[a][0]!=a-4 or len(succ[pred[a][0]])!=1:starts.add(a)
        if len(succ[a])!=1 or (succ[a]and succ[a][0]!=a+4):starts.update(succ[a])
    result=[];used=set()
    for a in sorted(starts):
        if a in used:continue
        body=[a];used.add(a)
        while len(succ[body[-1]])==1:
            b=succ[body[-1]][0]
            if b!=body[-1]+4 or b in starts or b in used:break
            body.append(b);used.add(b)
        result.append({'entry':hx(a),'instructions':[hx(x)for x in body],
          'outgoing':[e for e in edges if int(e['from'],16)==body[-1]]})
    assert used==addresses
    return result

def data_refs(raw,instructions,basic_blocks):
    refs=[];accesses=[]
    for block in basic_blocks:
        constants={}
        for text in block['instructions']:
            ins=instructions[int(text,16)];ops=ins.operands;new={}
            for op in ops:
                if op.type!=ARM_OP_MEM:continue
                mem=op.mem;record={'site':text,'assembly':ins.mnemonic+' '+ins.op_str,
                  'base_register':ins.reg_name(mem.base),'structure_offset':mem.disp,
                  'indexed':bool(mem.index),'writeback':ins.writeback,'effective_address':None,
                  'operation':'read'if ins.mnemonic.startswith('ldr')else('write'if ins.mnemonic.startswith('str')else'unknown')}
                if mem.base==ARM_REG_PC and not mem.index and ins.mnemonic=='ldr':
                    pool=ins.address+8+mem.disp;value=struct.unpack_from('<I',raw,pool-BASE)[0]
                    refs.append({'site':text,'literal_address':hx(pool),'value':hx(value),'bytes':raw[pool-BASE:pool-BASE+4].hex()})
                    new[ops[0].reg]=value;record['effective_address']=hx(pool)
                elif mem.base in constants and not mem.index and not ins.writeback:
                    record['effective_address']=hx(constants[mem.base]+mem.disp)
                    record['confidence']='straight_line_static_candidate'
                accesses.append(record)
            if ins.mnemonic in ('mov','add','sub')and len(ops)>=2 and ops[0].type==ARM_OP_REG:
                if ins.mnemonic=='mov'and ops[1].type==ARM_OP_IMM:new[ops[0].reg]=ops[1].imm
                elif len(ops)==3 and ops[1].type==ARM_OP_REG and ops[1].reg in constants and ops[2].type==ARM_OP_IMM:
                    new[ops[0].reg]=constants[ops[1].reg]+(ops[2].imm if ins.mnemonic=='add'else-ops[2].imm)
            for reg in ins.regs_access()[1]:constants.pop(reg,None)
            if ins.group(CS_GRP_CALL):
                for r in ('r0','r1','r2','r3','ip','lr'):
                    for reg in list(constants):
                        if ins.reg_name(reg)==r:constants.pop(reg,None)
            if ins.cc==ARM_CC_AL:constants.update(new)
    return refs,accesses

def raw_call_candidates(raw,targets):
    out={hx(a):[]for a in targets}
    for off in range(32,len(raw)-3,4):
        w=struct.unpack_from('<I',raw,off)[0]
        if w&0x0f000000!=0x0b000000 or w>>28==15:continue
        disp=w&0xffffff;disp=disp-(1<<24)if disp&(1<<23)else disp
        target=(BASE+off+8+disp*4)&0xffffffff
        if target in targets:out[hx(target)].append({'site':hx(BASE+off),'status':'raw_ARM_BL_candidate_not_validated_code_region'})
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ghidra',type=Path,required=True);a=ap.parse_args()
    import pyghidra
    pyghidra.start(install_dir=a.ghidra)
    from ghidra.program.model.address import AddressSet
    from ghidra.app.decompiler import DecompInterface
    import ghidra.framework.Application as Application
    manifest=json.loads((ROOT/'original-firmware/manifest.json').read_text())
    index=[];outdir=HERE/'packets';outdir.mkdir(exist_ok=True)
    script_sha=sha(Path(__file__).read_bytes())
    for image in manifest['images']:
        version=image['version'];rawpath=ROOT/image['path'];raw=rawpath.read_bytes();assert sha(raw)==image['sha256']
        project_name='ys4470_'+version.replace('.','_');project_root=ROOT/'work/fsm-timeout/ghidra/ghidra-projects'
        project_files=sorted((project_root/(project_name+'.rep')).rglob('*.gbf'))
        project_sha=sha(json.dumps([(p.relative_to(project_root).as_posix(),sha(p.read_bytes()))for p in project_files]).encode())
        cache_key=sha((script_sha+image['sha256']+project_sha).encode())
        cached=[outdir/(image['sha256']+'-'+hx(e)+'.json')for e,_,_ in SEEDS]
        if all(p.exists()and json.loads(p.read_text())['cache_key']==cache_key for p in cached):
            index.extend({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p.read_bytes()),'cache_hit':True}for p in cached);continue
        callers=raw_call_candidates(raw,{e for e,_,_ in SEEDS})
        with pyghidra.open_program(rawpath,project_location=project_root,project_name=project_name,
              program_name=rawpath.name,analyze=False,language='ARM:LE:32:v5t',loader='ghidra.app.util.opinion.BinaryLoader')as flat:
            program=flat.getCurrentProgram();assert str(program.getLanguageID())=='ARM:LE:32:v5t'
            # Existing program memory must match the ORIGINAL, not a patched mapped project.
            memory=program.getMemory()
            from jpype import JArray,JByte
            mapped=JArray(JByte)(len(raw));assert memory.getBytes(flat.toAddr(hx(BASE)),mapped)==len(raw)
            assert bytes(mapped)==raw,'Existing project memory differs from original image'
            tx=program.startTransaction('temporary whole-function packet export')
            try:
              for entry,name,status in SEEDS:
                instructions,edges,calls,unresolved=cfg(raw,entry);assert not unresolved,'Do not advertise an incomplete CFG as complete'
                body=AddressSet()
                for pc in instructions:body.addRange(flat.toAddr(hx(pc)),flat.toAddr(hx(pc+3)))
                f=program.getFunctionManager().getFunctionAt(flat.toAddr(hx(entry)))
                old={'name':str(f.getName()),'comment':f.getComment(),'source':str(f.getSymbol().getSource())}if f else None
                for pc in sorted(instructions):
                    addr=flat.toAddr(hx(pc));assert bytes((memory.getByte(addr.add(i))&255)for i in range(4))==raw[pc-BASE:pc-BASE+4]
                    if flat.getInstructionAt(addr)is None:flat.disassemble(addr)
                if f is None:f=flat.createFunction(flat.toAddr(hx(entry)),None)
                assert f is not None;f.setBody(body)
                assembly=[]
                for pc,ins in sorted(instructions.items()):
                    gi=flat.getInstructionAt(flat.toAddr(hx(pc)));assert gi is not None and gi.getLength()==4
                    assert bytes(gi.getBytes())==raw[pc-BASE:pc-BASE+4]
                    assembly.append({'address':hx(pc),'bytes':ins.bytes.hex(),'assembly':str(gi),'capstone':ins.mnemonic+' '+ins.op_str})
                decompiler=DecompInterface()
                try:
                    decompiler.openProgram(program);r=decompiler.decompileFunction(f,30,flat.getMonitor())
                    c=str(r.getDecompiledFunction().getC())if r.decompileCompleted()else None
                finally:decompiler.dispose()
                bb=blocks(instructions,edges);literals,accesses=data_refs(raw,instructions,bb)
                packet={'schema':REV,'exporter_sha256':script_sha,'cache_key':cache_key,'source_project_manifest_sha256':project_sha,
                  'binary':image,'program':str(program.getName()),'architecture':'ARM926EJ-S','language':str(program.getLanguageID()),
                  'instruction_mode':'ARM','ghidra_version':str(Application.getApplicationVersion()),'pyghidra_version':pyghidra.__version__,
                  'entry':hx(entry),'name':name,'name_evidence_status':status,'preserved_analyst_metadata':old,
                  'range':{'min':hx(min(instructions)),'max_inclusive':hx(max(instructions)+3)},
                  'body_instruction_count':len(assembly),'body_sha256':sha(b''.join(bytes.fromhex(i['bytes'])for i in assembly)),
                  'complete_local_cfg':True,'assembly':assembly,'decompiled_c':c,'basic_blocks':bb,'edges':edges,
                  'direct_callees':calls,'indirect_calls':[x for x in calls if not x['resolved']],
                  'direct_caller_candidates':callers[hx(entry)],'literal_refs':literals,'memory_accesses':accesses,
                  'global_readers_writers_scope':'Indexed exported packets only; dynamic bases and whole-program consumers remain unresolved.',
                  'limits':['Complete reachable local CFG under explicit ARM return/direct-branch rules; not complete transitive callees or all feasible paths.',
                    'Raw BL matches may be data. Caller completeness is not claimed. Dynamic memory bases and indirect calls remain explicit.',
                    'Decompiler output is an aid, not independent semantic proof. Names are analyst labels, not vendor symbols.',
                    'Constant tracking resets at block joins and clobbers; memory accesses are candidates, not execution observations.']}
                p=outdir/(image['sha256']+'-'+hx(entry)+'.json');p.write_text(json.dumps(packet,indent=2)+'\n',encoding='utf8')
                index.append({'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p.read_bytes()),'cache_hit':False})
            finally:program.endTransaction(tx,False)
    (HERE/'packet-index.json').write_text(json.dumps({'schema':'ys4470.packet-index.v1','packets':index},indent=2)+'\n',encoding='utf8')
    print(json.dumps({'packets':len(index),'cache_hits':sum(x['cache_hit']for x in index)}))
if __name__=='__main__':main()
