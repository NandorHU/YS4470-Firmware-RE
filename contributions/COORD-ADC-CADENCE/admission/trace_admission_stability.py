"""Bound original state3->state5 byte stability and known synchronous-call gates.

No physical I/O. Requires the previous UART harness and original hash-pinned
images. Output may be isolated with --out-dir; no repository write is required.
"""
from __future__ import annotations
import argparse,hashlib,itertools,json,struct,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
ap.add_argument('--out-dir',type=Path,default=Path(__file__).resolve().parent);args=ap.parse_args()
ROOT=args.repo.resolve();OUT=args.out_dir.resolve();assert(ROOT/'original-firmware/manifest.json').is_file()
sys.path[:0]=[str(ROOT/'contributions/COORD-ADC-CADENCE/uart'),str(ROOT/'contributions/COORD-FUNCTION-PACKETS'),str(ROOT/'tools')]
from trace_uart_correlation import OriginalUART,BASE,FSM,CTRL,RESULT,RX,COUNT,COUNTER,NEST,RET,TOP,sha
from export_packets import cfg,raw_call_candidates
from emulate_state5_parser import reference
from unicorn import UC_MEM_WRITE
from unicorn.arm_const import *
DEFERRED=0x805ac6d0;HANDLER=0x80003dd8;SERVICE=0x80005b6c
def write(path,obj):path.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf8')

class ServiceGate(OriginalUART):
    def reset(self):
        super().reset();self.handler_seen=False;self.model_leaves=[]
    def code(self,u,a,n,data):
        if a==HANDLER:
            self.handler_seen=True;self.event('stop_before_control_handler',pc=hex(a),busy=self.byte(FSM+0x34),
                record=bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0),68)).hex());u.emu_stop();return
        if a in (0x800618dc,0x80060fbc):
            self.model_leaves.append(dict(entry=hex(a),r0=u.reg_read(UC_ARM_REG_R0)))
            if a==0x800618dc:u.reg_write(UC_ARM_REG_R0,0)
            else:assert u.reg_read(UC_ARM_REG_R0)==1
            u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR));return
        if SERVICE<=a<0x80005d18 or 0x80004390<=a<0x80004490:
            assert n==4;self.coverage[a]=bytes(u.mem_read(a,n)).hex();self.instruction_count+=1;return
        super().code(u,a,n,data)
    def memory(self,u,access,a,n,v,data):
        if access==UC_MEM_WRITE and((a==CTRL and n==1)or(a==CTRL+8 and n==4)):
            self.event('control_write',pc=hex(u.reg_read(UC_ARM_REG_PC)),address=hex(a),value=v);return
        super().memory(u,access,a,n,v,data)
    def run_service(self,busy,record_case):
        self.reset()
        if busy:self.build();self.step(0)
        self.u.mem_write(DEFERRED,struct.pack('<I',record_case)+bytes([14,19])+bytes(62))
        self.put(CTRL+4,0x1001f000);self.u.mem_write(CTRL,b'\1');self.put(COUNTER,1);self.now=1
        for r,v in ((UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_SP,TOP),(UC_ARM_REG_LR,RET)):self.u.reg_write(r,v)
        self.u.emu_start(SERVICE,0,count=5000);pc=self.u.reg_read(UC_ARM_REG_PC)
        assert pc==(HANDLER if self.handler_seen else RET)
        if not self.handler_seen:assert self.u.reg_read(UC_ARM_REG_SP)==TOP
        assert self.handler_seen==(not busy and record_case not in(2,5))
        assert self.byte(CTRL)==(1 if busy else 0)
        if self.handler_seen:
            record=self.events[-1];assert record['busy']==0 and int.from_bytes(bytes.fromhex(record['record'])[:4],'little')==record_case
        assert self.rd(NEST)==0
        return dict(initial_busy=busy,record_case=record_case,handler_reached=self.handler_seen,
            stopped_pc=hex(pc),pending_after=self.byte(CTRL),busy_after=self.byte(FSM+0x34),
            model_leaves=self.model_leaves,events=self.events,
            scope='Original service/copy/input dispatcher execute; empty nonblocking queue and sleep(1) are models. Stop before fallback handler body.')

def collect(item):
    raw=(ROOT/item['path']).read_bytes();assert sha(raw)==item['sha256'];m=OriginalUART(raw)
    digest=hashlib.sha256();cases=0;examples=[]
    sites=(None,0x80004738,0x8000473c,0x80004740,0x8000476c)
    for command,value,selector,n,site in itertools.product((0x1b,0x1d),(0,50,699,5000,5001,0xffffff),(0,255),(0,1,5,195,196),sites):
        m.reset();m.build(command);assert m.step(0)==3;m.now=1
        packet=bytes([0x5e if command==0x1b else 0x60])+value.to_bytes(3,'little')+bytes([selector])
        for b in packet:m.receive(b)
        assert m.step(1)==5
        # Deliberately conflicting tail, including another valid-looking frame.
        tail=(b'\x60\x58\x02\0\xff'*40)[:n]
        if site is None:
            m.now=2
            for b in tail:m.receive(b)
        else:m.injection=dict(site=site,packet=tail,done=False)
        assert m.step(2)==7
        if site is not None:assert m.injection['done']
        expected=reference(value,command,selector,14,0)
        assert bytes(m.u.mem_read(RX,5))==packet and m.rd(COUNT)==min(200,5+n)
        assert m.rd(RESULT+28)==expected['value_u32']and m.rd(RESULT+32)==expected['selector']
        state=dict(command=hex(command),raw24=value,selector=selector,tail_bytes=n,
            injection_site='before_parse'if site is None else hex(site),rx_count=m.rd(COUNT),
            published=m.rd(RESULT+28),published_selector=m.rd(RESULT+32),prefix_preserved=True)
        digest.update(json.dumps(state,sort_keys=True).encode());cases+=1
        if value==50 and selector==255 and n in(195,196)and site in(None,0x8000473c):
            examples.append(dict(case=state,events=[e for e in m.events if e['kind']in('interleave','parse','publish','state')]))
    service=ServiceGate(raw);gates=[service.run_service(b,c)for b,c in itertools.product((False,True),(0,1,2,5,6,7))]
    ownership=[];observed_sites=[]
    for entry,label in((0x80003dbc,'GaugeCmdTask startup/loop wrapper'),(HANDLER,'deferred control handler candidate')):
        ins,edges,calls,unknown=cfg(raw,entry);assert not unknown
        direct=[c for c in calls if c['target']=='0x80005f14'];observed_sites.extend(direct)
        ownership.append(dict(entry=hex(entry),label=label,name_status='Prior vendor name binding for GaugeCmdTask; handler name is a role label.',
            body_sha256=sha(b''.join(i.bytes for _,i in sorted(ins.items()))),
            assembly=[dict(address=hex(a),bytes=i.bytes.hex(),assembly=i.mnemonic+' '+i.op_str)for a,i in sorted(ins.items())],
            local_cfg_edges=edges,synchronous_edges=direct))
    raw_calls=raw_call_candidates(raw,{0x80005f14})['0x80005f14']
    validated_bl={c['site']for c in observed_sites if c['kind']=='call'}
    assert {c['site']for c in raw_calls}==validated_bl and len(validated_bl)==9
    tails=[c for c in observed_sites if c['kind']=='external_branch_boundary']
    assert tails==[dict(site='0x8000404c',target='0x80005f14',resolved=True,kind='external_branch_boundary')]
    # The deferred-copy pointer in the original service is resolved, not guessed.
    assert struct.unpack_from('<I',raw,0x80005d20-BASE)[0]==DEFERRED
    return dict(version=item['version'],input_sha256=sha(raw),admission_cases=cases,
        admission_fingerprint=digest.hexdigest(),examples=examples,service_gate_cases=len(gates),service_gates=gates,
        synchronous_ownership=ownership,validated_direct_bl_sites=sorted(validated_bl),extra_tail_branch=tails,
        observed_admission_instructions=[dict(address=hex(a),bytes=b)for a,b in sorted(m.coverage.items())],
        observed_service_instructions=[dict(address=hex(a),bytes=b)for a,b in sorted(service.coverage.items())])

versions=[collect(i)for i in json.loads((ROOT/'original-firmware/manifest.json').read_text())['images']]
assert versions[0]['admission_fingerprint']==versions[1]['admission_fingerprint']
for key in('examples','service_gates','validated_direct_bl_sites','extra_tail_branch','synchronous_ownership'):
    assert versions[0][key]==versions[1][key],key
OUT.mkdir(parents=True,exist_ok=True)
write(OUT/'validation.json',dict(schema='ys4470.admission-stability.v1',source_sha256=sha(Path(__file__).read_bytes()),
    reused_uart_harness_sha256=sha((ROOT/'contributions/COORD-ADC-CADENCE/uart/trace_uart_correlation.py').read_bytes()),
    reused_python_parser_sha256=sha((ROOT/'tools/emulate_state5_parser.py').read_bytes()),versions=versions,
    admission_cases=sum(v['admission_cases']for v in versions),service_gate_cases=sum(v['service_gate_cases']for v in versions),
    physical_device_operations=0,limits=[
        'Explicit ISR interleaves save/restore CPU context; real IRQ entry, scheduler and UART arrivals are not modeled.',
        'The ISR append stability proof assumes a valid nonnegative RX count and no other writer resetting/replacing the prefix.',
        'Nine whole-image raw ARM BL candidates plus one locally validated tail branch are classified; indirect and Thumb caller completeness is not claimed.',
        'Deferred-handler admission stops before its body; it proves the tested idle gate, not every handler command or system-wide mutual exclusion.',
        'Known GaugeCmdTask startup calls precede its service loop. Serialized known callers do not establish absence of other tasks/aliases.',
        'No physical time unit, external ADC command semantics, speed improvement or deployable patch is inferred.']))
print(json.dumps(dict(admission_cases=sum(v['admission_cases']for v in versions),service_gate_cases=sum(v['service_gate_cases']for v in versions),
    validated_bl_sites=9,additional_tail_branch='0x8000404c -> 0x80005f14')))
