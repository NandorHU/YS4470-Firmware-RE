"""Independent original-byte, execution, CFG/edge and packet identity validation."""
import json,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE,UC_PROT_READ,UC_PROT_EXEC
from unicorn.arm_const import UC_CPU_ARM_926,UC_ARM_REG_CPSR,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1
from completion_gate import sha,atomic_json
from export_packets import cfg,BASE
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def make_cpu(raw):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_926)
    u.mem_map(0x7ffff000,0x5ac000);u.mem_write(BASE,raw);u.mem_protect(0x7ffff000,0x5ac000,UC_PROT_READ|UC_PROT_EXEC)
    u.reg_write(UC_ARM_REG_CPSR,0x13)
    def reject_write(*args):raise AssertionError('Unexpected write')
    u.hook_add(UC_HOOK_MEM_WRITE,reject_write)
    return u
def execute_binding(raw):
    u=make_cpu(raw);seen=[]
    u.hook_add(UC_HOOK_CODE,lambda cpu,a,s,data:seen.append(hex(a)))
    u.emu_start(0x80005948,0x80005958,count=8)
    assert u.reg_read(UC_ARM_REG_PC)==0x80005958
    assert u.reg_read(UC_ARM_REG_R0)==0x80003dbc and u.reg_read(UC_ARM_REG_R1)==0x80005a10
    assert raw[0x80005a10-BASE:0x80005a10-BASE+13]==b'GaugeCmdTask\0'
    return {'callsite':'0x80005958','function_argument_r0':'0x80003dbc','name_argument_r1':'0x80005a10',
      'original_name':'GaugeCmdTask','executed':seen,'limit':'Task creation callee is not executed; this proves the argument binding only.'}
def execute_task(raw):
    u=make_cpu(raw);calls=[];visited=[]
    leaves={0x80005d24,0x80005f14,0x80005b6c}
    def code(cpu,a,size,data):
        if a==0x80003dd0 and len(calls)==5:cpu.emu_stop();return
        if a in leaves:
            calls.append({'site':hex(cpu.reg_read(UC_ARM_REG_LR)-4),'target':hex(a),'r0':cpu.reg_read(UC_ARM_REG_R0)})
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
        assert 0x80003dbc<=a<0x80003dd8
        visited.append(hex(a))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(0x80003dbc,0x80003dd8,count=40)
    assert u.reg_read(UC_ARM_REG_PC)==0x80003dd0 and len(calls)==5
    assert [x['target']for x in calls]==['0x80005d24','0x80005f14','0x80005f14','0x80005b6c','0x80005b6c']
    assert calls[1]['r0']==9 and calls[2]['r0']==19
    return {'entry':'0x80003dbc','calls':calls,'visited':visited,'all_original_instructions_executed':len(set(visited))==7,
      'limit':'Three callees are return-only models. No UART, RTOS task creation, task body or physical timing is measured.'}
def main():
    manifest=json.loads((ROOT/'original-firmware/manifest.json').read_text());bysha={i['sha256']:i for i in manifest['images']}
    index=json.loads((HERE/'packet-index.json').read_text());rows=[];instruction_checks=0;edges_checked=0
    for item in index['packets']:
        path=ROOT/item['path'];rawpacket=path.read_bytes();assert sha(rawpacket)==item['sha256'];p=json.loads(rawpacket)
        image=bysha[p['binary']['sha256']];raw=(ROOT/image['path']).read_bytes();assert sha(raw)==image['sha256']
        instructions,edges,calls,unknown=cfg(raw,int(p['entry'],16))
        assert not unknown and p['edges']==edges and p['direct_callees']==calls
        assert [i['address']for i in p['assembly']]==[hex(a)for a in sorted(instructions)]
        assert p['body_instruction_count']==len(instructions)and p['decompiled_c']
        for i in p['assembly']:
            a=int(i['address'],16);assert bytes.fromhex(i['bytes'])==raw[a-BASE:a-BASE+4];instruction_checks+=1
        for ref in p['literal_refs']:
            a=int(ref['literal_address'],16);assert raw[a-BASE:a-BASE+4].hex()==ref['bytes']
            assert struct.unpack_from('<I',raw,a-BASE)[0]==int(ref['value'],16)
        assert {i for b in p['basic_blocks']for i in b['instructions']}==set(i['address']for i in p['assembly'])
        edges_checked+=len(edges);rows.append({'version':image['version'],'entry':p['entry'],'instructions':len(instructions),'blocks':len(p['basic_blocks']),'body_sha256':p['body_sha256']})
    executions=[]
    for image in manifest['images']:
        raw=(ROOT/image['path']).read_bytes();executions.append({'version':image['version'],'sha256':sha(raw),
          'registration_binding':execute_binding(raw),'gauge_task':execute_task(raw)})
    for entry in {r['entry']for r in rows}:assert len({r['body_sha256']for r in rows if r['entry']==entry})==1
    report={'schema':'ys4470.packet-validation.v1','packets':rows,'instruction_byte_checks':instruction_checks,'cfg_edges_checked':edges_checked,
      'original_executions':executions,'same_function_body_bytes_across_originals':True,
      'limits':['Identical function bytes do not prove equal global data or complete firmware behavior.',
        'CFG validation reuses the exporter algorithm; independent high-address/conditional-return fixtures and original execution are reported separately.',
        'Sound/GUI semantic proof remains the previously committed bounded experiments; these packets add full local CFG context.']}
    atomic_json(HERE/'validation.json',report);print(json.dumps({'packets':len(rows),'instruction_byte_checks':instruction_checks,'cfg_edges_checked':edges_checked,'binding_and_task_runs':4}))
if __name__=='__main__':main()
