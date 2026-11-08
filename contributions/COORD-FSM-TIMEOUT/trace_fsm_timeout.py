"""Bounded original ARM926 FSM deadlines + real tick getter + independent C.

No device access. States 2/3/4 execute from the real FSM entry; command-send
setup executes state 1 with a single explicit UART-send leaf model. Tick advance
is a prefix experiment stopped before ready-list/wrap-list handling.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import io
import itertools
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_READ, UC_PROT_WRITE,
                     UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_R0, UC_ARM_REG_R1,
    UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6, UC_ARM_REG_R7, UC_ARM_REG_R8,
    UC_ARM_REG_R9, UC_ARM_REG_R10, UC_ARM_REG_R11, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from emulate_state5_parser import BASE, EXPECTED_INPUTS

FSM, GETTER, TICK = 0x80004490, 0x80061f84, 0x80061fa4
ENTER, EXIT, UART_SEND = 0x80060efc, 0x80060f20, 0x80005e84
STATE, ROOT, NEST, RXCOUNT, RX, PORT = 0x805ac694, 0x805abbbc, 0x805abbf8, 0x805ab938, 0x805b408c, 0x01c208c4
RET, STACK, TOP = 0x10000000, 0x10010000, 0x10014000
U32 = 0xffffffff
KEYS = ('state','command','start','timeout','index','retry','required','expected_header')
SAVED = (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,
         UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
WINDOWS = ((FSM,0x80004808),(GETTER,0x80061fa0),(TICK,0x80061fe8),
           (ENTER,0x80060f1c),(EXIT,0x80060f58),(0x800031b8,0x800031e0),(0x80000b4c,0x80000ba8))
def sha(b): return hashlib.sha256(b).hexdigest()
def signed(x): return (x & U32) - (0x100000000 if x & 0x80000000 else 0)
def default(state=2, **kwargs):
    return dict(state=state,command=0x1b,start=0,timeout=30,index=2,retry=1,
                required=5,expected_header=0x5e,**kwargs) if not kwargs else {
        **dict(state=state,command=0x1b,start=0,timeout=30,index=2,retry=1,
               required=5,expected_header=0x5e),**kwargs}

def oracle(s, count, header, now):
    """Independent transition specification; no assembly/code-address parsing."""
    out=copy.deepcopy(s); effects=0
    # Mathematical modulo, independent of the guest carry condition.
    elapsed=(int(now)-int(s['start'])) % (1 << 32)
    due=elapsed >= int(s['timeout'])
    if s['state']==2:
        if signed(count)>0 and header==s['expected_header']:
            if s['command'] in range(9,16):
                out.update(state=4,start=now,timeout=100 if s['command'] in (13,14) else 50)
                effects=1
            else:
                out.update(state=1,index=(s['index']+1) % (1 << 32),retry=0); effects=2
        else:
            effects=1
            if due: out['state']=6
    elif s['state']==3:
        if signed(s['required'])>signed(count):
            effects=1
            if due: out['state']=6
        else:
            valid={0x1b:0x5e,0x1d:0x60}
            out['state']=5 if s['command'] not in valid or header==valid[s['command']] else 6
    elif s['state']==4:
        effects=1
        if due:
            out.update(state=1,index=(s['index']+1) % (1 << 32),retry=0); effects|=2
    else: raise ValueError('oracle only specifies states 2, 3 and 4')
    return out,effects

class Machine:
    def __init__(self, raw):
        self.mu=Uc(UC_ARCH_ARM,UC_MODE_ARM); self.mu.ctl_set_cpu_model(UC_CPU_ARM_926)
        low=BASE & ~0xfff; high=(BASE+len(raw)+0xfff)&~0xfff
        self.mu.mem_map(low,high-low,UC_PROT_READ|UC_PROT_EXEC);self.mu.mem_write(BASE,raw)
        for page,size in ((0x805ab000,0x2000),(0x805b4000,0x1000),
                          (0x01c20000,0x1000),(RET,0x1000),(STACK,0x4000)):
            self.mu.mem_map(page,size,UC_PROT_READ|UC_PROT_WRITE)
        self.mu.mem_protect(RET,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        self.coverage=set();self.mu.hook_add(UC_HOOK_CODE,self.code)
        self.mu.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,self.memory)
        self.reset()

    def put(self,a,v): self.mu.mem_write(a,struct.pack('<I',v & U32))
    def word(self,a): return struct.unpack('<I',self.mu.mem_read(a,4))[0]
    def byte(self,a,v): self.mu.mem_write(a,bytes([v & 255]))
    def clear_trace(self):
        self.visited=[];self.writes=[];self.tick_reads=[];self.getter_calls=0
        self.uart=[];self.intervention=None;self.intervened=False
    def reset(self,nesting=0):
        self.nesting=nesting;self.kind='fsm';self.stop=RET
        self.mu.mem_write(0x805ab000,bytes(0x2000));self.mu.mem_write(0x805b4000,bytes(0x1000))
        self.put(NEST,nesting);self.put(PORT,0xa5a5a5af);self.clear_trace()
    def regs(self):
        self.mu.reg_write(UC_ARM_REG_CPSR,0x13|(0x80 if self.nesting else 0))
        self.mu.reg_write(UC_ARM_REG_SP,TOP);self.mu.reg_write(UC_ARM_REG_LR,RET)
        for i,reg in enumerate(SAVED):self.mu.reg_write(reg,0x11110000+i)
    def load_state(self,s,count,header,now):
        self.byte(STATE,s['state']);self.put(STATE+0x20,s['command'])
        for off,key in ((0x2c,'start'),(0x30,'timeout'),(0x18,'index'),(0x1c,'retry'),(0x28,'required')):
            self.put(STATE+off,s[key])
        self.byte(STATE+0x24,s['expected_header']);self.put(RXCOUNT,count);self.byte(RX,header);self.put(ROOT+0xc,now)
    def state(self):
        return dict(state=self.mu.mem_read(STATE,1)[0],command=self.word(STATE+0x20),
            start=self.word(STATE+0x2c),timeout=self.word(STATE+0x30),index=self.word(STATE+0x18),
            retry=self.word(STATE+0x1c),required=self.word(STATE+0x28),
            expected_header=self.mu.mem_read(STATE+0x24,1)[0])
    def code(self,mu,address,size,_):
        if address==self.stop:mu.emu_stop();return
        if address==UART_SEND:
            assert self.kind=='send_setup'
            ptr,n=mu.reg_read(UC_ARM_REG_R0),mu.reg_read(UC_ARM_REG_R1)
            assert 0<n<=16
            self.uart.append({'pointer':hex(ptr),'length':n,'payload':bytes(mu.mem_read(ptr,n)).hex()})
            mu.reg_write(UC_ARM_REG_R0,0);mu.reg_write(UC_ARM_REG_PC,mu.reg_read(UC_ARM_REG_LR));return
        assert size==4 and any(a<=address<b for a,b in WINDOWS),hex(address)
        self.coverage.add(address);self.visited.append(address)
        if address==GETTER:
            self.getter_calls+=1
            if self.intervention is not None and not self.intervened:
                self.cached=(mu.reg_read(UC_ARM_REG_R4),mu.reg_read(UC_ARM_REG_R5))
                for off,value in self.intervention.items():self.put(STATE+off,value)
                self.intervened=True
    def memory(self,mu,access,address,size,value,_):
        if access!=UC_MEM_WRITE:
            if address==ROOT+0xc and self.kind!='tick_prefix':
                assert mu.reg_read(UC_ARM_REG_CPSR)&0x80 and self.word(NEST)==self.nesting+1
                self.tick_reads.append({'pc':hex(mu.reg_read(UC_ARM_REG_PC)),
                    'irq_masked':True,'nesting':self.word(NEST),'value':self.word(ROOT+0xc)})
            return
        allowed=(STACK<=address and address+size<=TOP) or (address==NEST and size==4)
        if self.kind in ('fsm','send_setup'):
            allowed |= (address==STATE and size==1) or (address==PORT and size==4)
            allowed |= size==4 and address in (STATE+0x18,STATE+0x1c,STATE+0x2c,STATE+0x30)
        if self.kind=='send_setup':
            allowed |= (RX<=address and address+size<=RX+200) or (address==RXCOUNT and size==4)
            allowed |= (address==STATE+0x24 and size==1) or (size==4 and address in (STATE+0x20,STATE+0x28))
        if self.kind=='tick_prefix':allowed |= size==4 and address in (ROOT+0xc,ROOT+0x18)
        assert allowed,(self.kind,hex(mu.reg_read(UC_ARM_REG_PC)),hex(address),size)
        self.writes.append((hex(address),size,value & ((1<<(8*size))-1)))
    def run(self,entry=FSM,stop=RET,preserve=True):
        self.stop=stop;self.regs()
        self.mu.emu_start(entry,0,count=2000)
        assert self.mu.reg_read(UC_ARM_REG_PC)==stop
        if preserve:
            assert self.mu.reg_read(UC_ARM_REG_SP)==TOP
            assert [self.mu.reg_read(r)for r in SAVED]==[0x11110000+i for i in range(8)]
        assert self.word(NEST)==self.nesting
        assert bool(self.mu.reg_read(UC_ARM_REG_CPSR)&0x80)==bool(self.nesting)
    def step(self,s,count,header,now,nesting=0,intervention=None):
        self.reset(nesting);self.load_state(s,count,header,now);self.intervention=intervention
        expected,effects=oracle(s,count,header,now)
        if intervention:
            assert effects&1
            for off,key in ((0x2c,'start'),(0x30,'timeout')):
                if off in intervention:expected[key]=intervention[off]
        self.run()
        actual=self.state()
        assert actual==expected,(s,count,header,now,actual,expected)
        assert self.getter_calls==int(bool(effects&1)) and len(self.tick_reads)==self.getter_calls
        assert self.word(ROOT+0xc)==now and self.word(RXCOUNT)==(count & U32)
        assert self.mu.mem_read(RX,1)[0]==header
        assert self.word(PORT)==(0xa5a5a5af & ~12 if effects&2 else 0xa5a5a5af)
        assert sum(a==hex(PORT)for a,_,_ in self.writes)==(2 if effects&2 else 0)
        if intervention:assert self.intervened and self.cached==(s['start'],s['timeout'])
        return {'before':s,'rx_count':count,'first_byte':header,'now':now,'nesting':nesting,
                'after':actual,'effects':effects,'tick_reads':copy.deepcopy(self.tick_reads),
                'cache_intervention':{hex(k):v for k,v in (intervention or {}).items()},
                'writes':copy.deepcopy(self.writes)}
    def getter_probe(self,now,nesting):
        self.reset(nesting);self.kind='getter';self.put(ROOT+0xc,now);self.run(GETTER)
        assert self.mu.reg_read(UC_ARM_REG_R0)==now and len(self.tick_reads)==1
        assert all(a==hex(NEST)or STACK<=int(a,16)<TOP for a,_,_ in self.writes)
        return {'now':now,'nesting':nesting,'read':self.tick_reads[0],'nesting_restored':True}
    def tick_probe(self,now,suspended):
        self.reset();self.kind='tick_prefix';self.put(ROOT+0xc,now);self.put(ROOT+0x30,suspended)
        self.put(ROOT+0x18,U32);self.put(ROOT+0x1c,0)
        stop=RET if suspended else 0x80061fe8
        self.run(TICK,stop,preserve=bool(suspended))
        assert self.word(ROOT+0xc)==(now if suspended else (now+1)&U32)
        assert self.word(ROOT+0x18)==(0 if suspended else U32)
        return {'tick_before':now,'suspended':suspended,'tick_after':self.word(ROOT+0xc),
                'deferred_after':self.word(ROOT+0x18),'stop':hex(stop),
                'complete_rtos_tick_executed':False}
    def setup_probe(self,command,now,nesting):
        s=default(1,command=command,index=0,start=0x11223344,timeout=0x55667788)
        self.reset(nesting);self.kind='send_setup';self.load_state(s,123,0xa5,now)
        self.put(STATE+4,command);self.put(STATE+0x14,1)
        self.mu.mem_write(RX,b'\xa5'*200)
        self.run()
        actual=self.state()
        assert len(self.uart)==1 and self.getter_calls==1
        assert self.word(RXCOUNT)==0 and bytes(self.mu.mem_read(RX,200))==bytes(200)
        assert actual['start']==now and actual['command']==command
        if command in (0x1b,0x1d):
            assert actual['state']==3 and actual['timeout']==30 and actual['required']==5
        else:
            assert actual['state']==2 and actual['timeout']==80
            assert actual['expected_header']==int(self.uart[0]['payload'][:2],16)
        return {'command':command,'now':now,'nesting':nesting,'after':actual,
                'uart_send_model':self.uart[0],'tick_reads':copy.deepcopy(self.tick_reads)}

class Compiled:
    def __init__(self,path):
        elf=ELFFile(io.BytesIO(path.read_bytes()))
        assert elf.header.e_machine=='EM_ARM' and elf.little_endian
        sym=next(s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name=='ys4470_fsm_timed_step')
        section_id=sym['st_shndx'];section=elf.get_section(section_id)
        for s in elf.iter_sections():
            assert not(s['sh_type']in('SHT_REL','SHT_RELA') and s['sh_info']==section_id and s.num_relocations())
        code=section.data();assert len(code)<0xf00
        self.mu=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.mu.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.mu.mem_map(0x20000000,0x1000,UC_PROT_READ|UC_PROT_EXEC);self.mu.mem_write(0x20000000,code)
        self.mu.mem_map(0x30000000,0x1000,UC_PROT_READ|UC_PROT_WRITE)
        self.entry=0x20000000+sym['st_value'];self.visited=set();self.code_size=len(code)
        self.mu.hook_add(UC_HOOK_CODE,self.code);self.mu.hook_add(UC_HOOK_MEM_WRITE,self.memory)
    def code(self,mu,address,size,_):
        if address==0x20000ff0:mu.emu_stop();return
        assert size==4 and 0x20000000<=address<0x20000000+self.code_size
        self.visited.add(address)
    def memory(self,mu,access,address,size,value,_):
        assert 0x30000100<=address and address+size<=0x30000120 or 0x30000d00<=address and address+size<=0x30000f00
    def step(self,s,count,header,now):
        mu=self.mu
        mu.mem_write(0x30000100,struct.pack('<8I',*(s[k]&U32 for k in KEYS)))
        mu.mem_write(0x30000200,struct.pack('<3I',count&U32,header,now))
        for r,v in ((UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_SP,0x30000f00),(UC_ARM_REG_LR,0x20000ff0),
                    (UC_ARM_REG_R0,0x30000100),(UC_ARM_REG_R1,0x30000200)):mu.reg_write(r,v)
        mu.emu_start(self.entry,0,count=1000)
        assert mu.reg_read(UC_ARM_REG_PC)==0x20000ff0 and mu.reg_read(UC_ARM_REG_SP)==0x30000f00
        return dict(zip(KEYS,struct.unpack('<8I',mu.mem_read(0x30000100,32)))),mu.reg_read(UC_ARM_REG_R0)

def scenarios():
    budgets=(0,1,5,25,30,40,50,80,100,0x7fffffff,0x80000000,U32)
    starts=(0,1,0x7ffffffe,0xfffffff0,U32)
    for state,budget,start,nest in itertools.product((2,3,4),budgets,starts,(0,1,2)):
        deltas=sorted({0,1,(budget-1)&U32,budget,(budget+1)&U32,0x7fffffff,0x80000000,U32})
        for delta in deltas:
            yield 'timeout_boundary',default(state,start=start,timeout=budget),0,0x5e,(start+delta)&U32,nest
    # Real data/header guards and completion precedence, including signed length.
    for state,cmd,count,header,delta in itertools.product((2,3),(8,9,12,13,14,15,16,0x1b,0x1d,U32),
                    (0,1,4,5,6,0x7fffffff,0x80000000,U32),(0x58,0x5e,0x60,0xff),(0,29,30,31)):
        yield 'admission',default(state,command=cmd,expected_header=0x58),count,header,delta,0
    for state,index,required,count in itertools.product((2,3,4),(0,U32),(0,5,0x80000000,U32),(0,5,U32)):
        yield 'signed_length_index_wrap',default(state,index=index,required=required),count,0x5e,30,1

def collect(version,path,obj):
    raw=path.read_bytes();assert sha(raw)==EXPECTED_INPUTS[version]
    m=Machine(raw);compiled=Compiled(obj);digest=hashlib.sha256();counts={};examples=[]
    for category,s,n,h,now,nest in scenarios():
        result=m.step(s,n,h,now,nest)
        cstate,effects=compiled.step(s,n,h,now)
        assert (cstate,effects)==(result['after'],result['effects'])
        counts[category]=counts.get(category,0)+1
        digest.update(json.dumps(result,sort_keys=True).encode())
        if category=='timeout_boundary' and s['timeout']==30 and s['start']==0xfffffff0 and nest==0 and now in (13,14,15):
            examples.append(result)
    getter=[m.getter_probe(now,n)for now,n in itertools.product((0,1,0x7fffffff,0xfffffffe,U32),(0,1,2,7))]
    ticks=[m.tick_probe(now,s)for now,s in itertools.product((0,1,0x7fffffff,0xfffffffe,U32),(0,1))]
    setups=[m.setup_probe(cmd,now,n)for cmd,now,n in itertools.product((9,10,11,12,13,14,15,0x1b,0x1d),(0,1,0xfffffffe,U32),(0,1,2))]
    # Deliberate host mutation while getter is entered: not a real IRQ/schedule.
    cache=[]
    for state,start,now,budget,replacement in itertools.product((2,3,4),(0,0xfffffff0),(10,30),(30,40),(0,U32)):
        s=default(state,start=start,timeout=budget)
        change={0x30:replacement,0x2c:now}
        cache.append(m.step(s,0,0x5e,now,0,change))
    # Independent transitions at the original 30 and hypothetical 40 thresholds.
    counterfactual=[]
    for now in (29,30,39,40):
        counterfactual.append({'elapsed':now,'budget30':m.step(default(3),1,0x5e,now)['after']['state'],
            'budget40_fixture':m.step(default(3,timeout=40),1,0x5e,now)['after']['state'],
            'actual_beta3_image_executed':False})
    for data in (getter,ticks,setups,cache,counterfactual):digest.update(json.dumps(data,sort_keys=True).encode())
    md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    windows={hex(a):{'end_exclusive':hex(b),'sha256':sha(raw[a-BASE:b-BASE]),
        'assembly':[f'{i.address:08x} {i.mnemonic} {i.op_str}'for i in md.disasm(raw[a-BASE:b-BASE],a)]}for a,b in WINDOWS}
    labels=[{'address':hex(a),'name':name,'confidence':1.0,'proof':'bounded_original_ARM926_execution',
        'evidence':'contributions/COORD-FSM-TIMEOUT/fsm-timeout.json','guard_bytes':32,
        'guard_sha256':sha(raw[a-BASE:a-BASE+32])}for a,name in ((FSM,'RE_MeasurementFSM'),(GETTER,'RE_RtosTickSnapshot'))]
    return {'version':version,'input_sha256':sha(raw),'failed':0,'differential_cases':counts,
        'getter_cases':len(getter),'tick_prefix_cases':len(ticks),'send_setup_cases':len(setups),
        'cache_intervention_cases':len(cache),'counterfactual_comparison_cases':8,
        'checks':sum(counts.values())+len(getter)+len(ticks)+len(setups)+len(cache)+8,
        'results_sha256':digest.hexdigest(),'boundary_examples':examples,'getter_examples':getter[:4],
        'tick_prefix_examples':ticks,'send_setup_examples':setups,'cache_examples':cache[:6],
        'counterfactual_examples':counterfactual,'raw_windows':windows,'approved_labels':labels,
        'instruction_addresses_visited':[hex(a)for a in sorted(m.coverage)],
        'compiled_instruction_addresses_visited':len(compiled.visited)}

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',action='append',required=True)
    ap.add_argument('--reconstruction-object',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();versions=[]
    for item in args.input:
        version,path=item.split('=',1);v=collect(version,Path(path),args.reconstruction_object);versions.append(v)
        print(version,v['checks'],'checks;',v['failed'],'failures;',v['results_sha256'])
    if len(versions)==2:assert versions[0]['results_sha256']==versions[1]['results_sha256']
    repo=Path(__file__).resolve().parents[2]
    report={'schema':'ys4470.fsm-timeout.v1','date':'2026-11-08','cpu':'UC_CPU_ARM_926','versions':versions,
        'reconstruction':{'source':'reconstruction/fsm_timeout.c','source_sha256':sha((repo/'reconstruction/fsm_timeout.c').read_bytes()),
        'header_sha256':sha((repo/'reconstruction/fsm_timeout.h').read_bytes()),'object_sha256':sha(args.reconstruction_object.read_bytes()),
        'build':'Zig0.13.0 cc -target arm-freestanding-eabi -mcpu=arm926ej_s -marm -O2 -ffreestanding -fno-builtin -ffunction-sections -std=c11 -Wall -Wextra -Werror'},
        'limits':['Only states2/3/4 have the original/Python/compiled-C differential specification.',
        'State1 send setup executes original clear/GPIO/getter; UART send0x80005e84 is a leaf model.',
        'Tick prefix stops at0x80061fe8 before wrap-list/ready-list handling; no complete RTOS scheduler proof.',
        'Cache mutation is an explicit host intervention, not an observed concurrent writer or hardware IRQ.',
        'Budget40 is a fixture comparison; no actual Beta3 image executed by this runner.',
        'Counter ticks are not assigned milliseconds; no device, UART waveform or acoustic measurement.']}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
if __name__=='__main__':main()
