"""Replace refresh queue/renderer stubs with bounded original-code execution.

Executes original renderer state helpers, event builder, queue send/copy and
critical sections. Graphics/text/logging leaves remain explicit API models.
Queue scope: available send-to-back and full zero-wait rejection, no waiters.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import itertools
import json
import struct
from pathlib import Path

from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from unicorn import UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC,UC_MEM_WRITE
from unicorn.arm_const import (UC_ARM_REG_CPSR,UC_ARM_REG_R0,UC_ARM_REG_R1,
                               UC_ARM_REG_R2,UC_ARM_REG_SP,UC_ARM_REG_PC)
from trace_result_freshness import (FreshMachine,QUEUE,RENDER,UI,CONTROL,RESULT,
                                   ACTIVE,HISTORY,RX,TOP,RETURN,BASE,EXPECTED_INPUTS)
from trace_fast_cont_filter import Original

QSEND,CRITICAL_ENTER,CRITICAL_EXIT=0x80061acc,0x80060efc,0x80060f20
QUEUE_OBJECT,QUEUE_DATA,RECORD=0x10002000,0x10002050,0x10001800
CRITICAL_COUNT=0x805abbf8
AUX_FIRST,AUX_END=0x80d46fb8,0x80d47068
LEAVES={0x80003c5c:'record_text',0x80032038:'widget_text',
        0x80045184:'display_format',0x80000578:'bounded_string_copy',0x800616e4:'log_enqueue',
        0x80042aa0:'heap_allocate'}
PROTECTED=((UI+9,1),(CONTROL+1,1),(RESULT+0x1c,8),(ACTIVE,16),(HISTORY,12),(RX,200))


def sha(b):return hashlib.sha256(b).hexdigest()
def overlap(a,n,b,m):return a<b+m and b<a+n


class SideEffectMachine(FreshMachine):
    def __init__(self,raw):
        super().__init__(raw)
        for page in (0x80002000,0x80060000,0x80061000,0x80032000,0x80045000):
            self.mu.mem_map(page,0x1000,UC_PROT_READ|UC_PROT_EXEC)
            self.mu.mem_write(page,raw[page-BASE:page-BASE+0x1000]);self.code_pages+=(page,)
        for page in (QUEUE_OBJECT,0x80d46000,0x80d47000):
            self.mu.mem_map(page,0x1000,UC_PROT_READ|UC_PROT_WRITE)
        self.in_renderer=False;self.in_queue=False;self.leaves=[];self.queue_calls=[]
        self.renderer_coverage=set();self.helper_coverage=set();self.queue_coverage=set()

    def initialize_case(self,*args,**kwargs):
        super().initialize_case(*args,**kwargs)
        self.mu.mem_write(AUX_FIRST,bytes(AUX_END-AUX_FIRST))
        self.mu.mem_write(QUEUE_OBJECT,bytes(0x1000));self.mu.mem_write(QUEUE_DATA,b'\xdd'*(10*0x44))
        self.put(CRITICAL_COUNT,0);self.put(CONTROL+4,QUEUE_OBJECT)
        self.configure_queue(10,0,0)
        self.in_renderer=False;self.in_queue=False;self.leaves=[];self.queue_calls=[]

    def configure_queue(self,capacity,used,position):
        assert 1<=capacity<=10 and 0<=used<=capacity and 0<=position<capacity
        for offset,val in ((0,QUEUE_DATA),(4,QUEUE_DATA+capacity*0x44),
                           (8,QUEUE_DATA+position*0x44),(12,QUEUE_DATA+(capacity-1)*0x44),
                           (0x10,0),(0x24,0),(0x38,used),(0x3c,capacity),(0x40,0x44)):
            self.put(QUEUE_OBJECT+offset,val)
        self.byte(QUEUE_OBJECT+0x44,255);self.byte(QUEUE_OBJECT+0x45,255)

    def protected_snapshot(self):return [bytes(self.mu.mem_read(a,n)).hex()for a,n in PROTECTED]

    def c_string(self,a,maximum=64):
        data=bytearray()
        for i in range(maximum):
            b=self.mu.mem_read(a+i,1)[0]
            if b==0:break
            data.append(b)
        return bytes(data)

    def on_code(self,mu,address,size,data):
        if address in self.stops:
            self.in_renderer=False;self.in_queue=False;mu.emu_stop();return
        if address==QUEUE:
            self.in_queue=True
            self.queue_initial=self.protected_snapshot()
            Original.on_code(self,mu,address,size,data);return
        if address==RENDER:
            self.in_renderer=True;self.renderer_initial=self.protected_snapshot()
            Original.on_code(self,mu,address,size,data);return
        if address==0x8005d134:
            assert self.protected_snapshot()==self.queue_initial
            self.in_queue=False
        if address==0x8005d1ac:
            assert self.protected_snapshot()==self.renderer_initial
            self.in_renderer=False
        if self.in_renderer:
            if RENDER<=address<0x8000378c:self.renderer_coverage.add(address)
            elif any(a<=address<b for a,b in ((0x80002e44,0x8000301c),(0x8000406c,0x80004388))):self.helper_coverage.add(address)
        if self.in_queue and 0x80061acc<=address<0x80061cd4:self.queue_coverage.add(address)
        if address==QSEND:
            q,record,wait,position=self.args();assert q==QUEUE_OBJECT and position==0
            used,capacity=self.word(q+0x38),self.word(q+0x3c)
            assert used<capacity or wait==0,'blocking send intentionally outside scope'
            self.queue_calls.append({'used_before':used,'capacity':capacity,'wait_argument':wait,
                'write_pointer_before':self.word(q+8),'payload':bytes(mu.mem_read(record,0x44)).hex()})
        if address==0x800067bc:
            call=self.queue_calls[-1];success=call['used_before']<call['capacity']
            assert mu.reg_read(UC_ARM_REG_R0)==int(success)
            assert self.word(CRITICAL_COUNT)==0
            assert not mu.reg_read(UC_ARM_REG_CPSR)&0x80
            if success:
                ptr=call['write_pointer_before']
                assert bytes(mu.mem_read(ptr,0x44)).hex()==call['payload']
                expected=ptr+0x44
                if expected>=QUEUE_DATA+call['capacity']*0x44:expected=QUEUE_DATA
                assert self.word(QUEUE_OBJECT+8)==expected
                assert self.word(QUEUE_OBJECT+0x38)==call['used_before']+1
            else:assert self.word(QUEUE_OBJECT+0x38)==call['used_before']
            call['returned']=int(success)
        if address in LEAVES:
            args=self.args();self.leaves.append({'address':hex(address),'role':LEAVES[address]})
            if address==0x80042aa0:
                assert args[0]==0x50+10*68
                mu.reg_write(UC_ARM_REG_R0,self.creation_return)
            elif address==0x80003c5c:
                # A formatting contract, not a full libc/display reconstruction.
                text=b'5.000';dest,limit=args[1],args[2]
                assert limit==0x40
                mu.mem_write(dest,text[:limit-1]+b'\0');mu.reg_write(UC_ARM_REG_R0,0)
            elif address==0x80000578:
                dest,limit,fmt,src=args
                assert 1<=limit<=0x40
                text=self.c_string(src,limit-1)
                mu.mem_write(dest,text+b'\0');mu.reg_write(UC_ARM_REG_R0,len(text))
            else:mu.reg_write(UC_ARM_REG_R0,0)
            self.back_from_stub();return
        super().on_code(mu,address,size,data)

    def on_memory(self,mu,access,address,size,value,data):
        protected=any(overlap(address,size,a,n)for a,n in PROTECTED)
        if access==UC_MEM_WRITE and (self.in_renderer or self.in_queue) and protected:
            raise AssertionError(f'protected state write at{address:#x},PC={mu.reg_read(UC_ARM_REG_PC):#x}')
        allowed=(UI<=address and address+size<=UI+0x38 or AUX_FIRST<=address and address+size<=AUX_END or
                 QUEUE_OBJECT<=address and address+size<=QUEUE_OBJECT+0x50 or
                 QUEUE_DATA<=address and address+size<=QUEUE_DATA+10*0x44 or address==CRITICAL_COUNT or
                 self.phase=='queue_init' and address==CONTROL+4 and size==4)
        if access==UC_MEM_WRITE and allowed:
            self.writes.append([self.phase,hex(address),size,value&((1<<(size*8))-1)]);return
        super().on_memory(mu,access,address,size,value,data)

    def queue_probe(self,capacity,used,position,event,null=False):
        self.initialize_case();self.configure_queue(capacity,used,position)
        if null:self.put(CONTROL+4,0)
        before=self.protected_snapshot();self.setup_regs();self.phase='queue_probe'
        for reg,val in ((UC_ARM_REG_R0,event),(UC_ARM_REG_R1,0x123),(UC_ARM_REG_R2,0x456)):self.mu.reg_write(reg,val)
        self.run(QUEUE)
        assert self.mu.reg_read(UC_ARM_REG_SP)==TOP and self.protected_snapshot()==before
        expected=not null and used<capacity
        assert self.mu.reg_read(UC_ARM_REG_R0)==int(expected)
        if not null:
            assert len(self.queue_calls)==1
            prefix=bytes.fromhex(self.queue_calls[0]['payload'])[:6]
            assert prefix==struct.pack('<I',event)+b'\x23\x56'
        else:assert not self.queue_calls
        return {'capacity':capacity,'used':used,'position':position,'event':event,'null':null,
                'returned':int(expected),'protected_unchanged':True}

    def renderer_probe(self,mode,display_flag,error,mismatch,latch,delay,warmup,history_ready):
        self.initialize_case(counter=warmup)
        self.byte(UI,mode);self.byte(UI+3,display_flag)
        self.byte(UI+0x11,mode if not mismatch else (mode+1)%6)
        self.byte(UI+0xf,34);self.byte(UI+0x10,0)
        self.byte(UI+0xe,latch);self.byte(UI+0x12,delay);self.byte(UI+0x14,1)
        if history_ready:
            self.mu.mem_write(AUX_FIRST,b'5.000\0')
            self.byte(UI+0xb,2);self.byte(UI+0xd,4)
            self.mu.mem_write(0x80d47038,struct.pack('<4I',*([0x40a00000]*4)))
            self.mu.mem_write(0x80d47048,struct.pack('<8I',*([0x40a00000]*8)))
            self.put(UI+0x20,8);self.put(UI+0x28,1)
        self.mu.mem_write(RECORD,bytes(0x44));self.mu.mem_write(RECORD,b'5.000\0')
        self.mu.mem_write(RECORD+0x32,b'm\0');self.put(RECORD+0x3c,0x40a00000);self.byte(RECORD+0x40,error)
        before=self.protected_snapshot();self.setup_regs();self.phase='renderer_probe'
        self.mu.reg_write(UC_ARM_REG_R0,RECORD);self.run(RENDER)
        assert self.mu.reg_read(UC_ARM_REG_SP)==TOP and self.protected_snapshot()==before
        return {'mode':mode,'display_flag':display_flag,'record_flag40':error,'mismatch':mismatch,'latch':latch,'countdown12':delay,
                'warmup':warmup,'history_ready':history_ready,'ui_after':bytes(self.mu.mem_read(UI,0x30)).hex(),
                'leaf_roles':sorted(set(x['role']for x in self.leaves)),'protected_unchanged':True}

    def critical_probe(self,nesting):
        self.initialize_case();self.put(CRITICAL_COUNT,nesting)
        self.setup_regs();self.phase='critical_probe'
        self.mu.reg_write(UC_ARM_REG_CPSR,0x13|(0x80 if nesting else 0))
        self.run(CRITICAL_ENTER)
        assert self.word(CRITICAL_COUNT)==nesting+1 and self.mu.reg_read(UC_ARM_REG_CPSR)&0x80
        # Preserve the guest CPSR/flags when invoking the matching exit.
        self.run(CRITICAL_EXIT)
        assert self.word(CRITICAL_COUNT)==nesting
        assert bool(self.mu.reg_read(UC_ARM_REG_CPSR)&0x80)==bool(nesting)
        return {'initial_nesting':nesting,'final_nesting':self.word(CRITICAL_COUNT),
                'final_irq_masked':bool(nesting)}

    def queue_init_probe(self,returned):
        self.initialize_case();self.put(CONTROL+4,0xaabbccdd)
        self.creation_return=returned;before=self.protected_snapshot()
        self.setup_regs();self.phase='queue_init';self.run(0x800029dc)
        assert self.word(CONTROL+4)==returned and self.protected_snapshot()==before
        assert self.mu.reg_read(UC_ARM_REG_SP)==TOP
        assert self.leaves==[{'address':'0x80042aa0','role':'heap_allocate'}]
        if returned:
            assert self.word(returned+0x3c)==10 and self.word(returned+0x40)==68
            assert self.word(returned)==returned+0x50 and self.word(returned+4)==returned+0x50+10*68
            assert self.word(returned+8)==returned+0x50 and self.word(returned+0xc)==returned+0x50+9*68
            assert self.word(returned+0x10)==0 and self.word(returned+0x24)==0
        return {'requested_capacity':10,'item_bytes':68,'type_argument':0,'returned':hex(returned),
                'allocation_bytes':760,'handle_address':hex(CONTROL+4),
                'original_constructor_executed':True}


def collect(version,path):
    raw=path.read_bytes();assert sha(raw)==EXPECTED_INPUTS[version]
    m=SideEffectMachine(raw);qresults=[];rresults=[]
    for capacity in (1,2,3):
        for used in range(capacity):
            for position in range(capacity):
                for event in (3,4):qresults.append(m.queue_probe(capacity,used,position,event))
        for position in range(capacity):qresults.append(m.queue_probe(capacity,capacity,position,3))
    for event in (3,4):qresults.append(m.queue_probe(1,0,0,event,True))
    for case in itertools.product((0,1,3,4),(0,1),(0,1),(0,1),(0,1),(0,1,8),(0,2,255),(False,True)):
        rresults.append(m.renderer_probe(*case))
    critical_results=[m.critical_probe(n)for n in (0,1,2)]
    init_results=[m.queue_init_probe(handle)for handle in (0,QUEUE_OBJECT)]
    m.queue_init_probe(QUEUE_OBJECT);steps=[]
    for _ in range(5):steps.append(m.callback())
    assert [s['filter_state']['count']for s in steps]==[0,0,1,2,3]
    assert all(s['discard_count']==2 and s['parser_entries']==0 for s in steps)
    assert steps[-1]['sound_active']==1 and steps[-1]['filter_state']['last_median']==5
    assert m.word(QUEUE_OBJECT+0x38)==5
    callback={'steps':steps,'queue_count':m.word(QUEUE_OBJECT+0x38),
              'queue_payload_prefixes':[q['payload'][:12]for q in m.queue_calls],
              'renderer_leaves':sorted(set(x['role']for x in m.leaves))}
    fingerprint=sha(json.dumps([qresults,rresults,critical_results,init_results,callback],sort_keys=True).encode())
    md=Cs(CS_ARCH_ARM,CS_MODE_ARM);windows={}
    for start,end in ((0x800029dc,0x800029fc),(0x80061838,0x800618dc),(RENDER,0x8000378c),(QUEUE,0x800067c4),(QSEND,0x80061cd4),
                      (CRITICAL_ENTER,0x80060f1c),(CRITICAL_EXIT,0x80060f58)):
        data=raw[start-BASE:end-BASE];windows[hex(start)]={'end_exclusive':hex(end),'sha256':sha(data),
            'assembly':[f'{i.address:08x} {i.mnemonic} {i.op_str}'for i in md.disasm(data,start)]}
    labels=[]
    for addr,name in ((0x800029dc,'RE_MeasurementQueueInit'),(0x80061838,'RE_QueueCreate'),
                      (RENDER,'RE_ResultRendererCore'),(QUEUE,'RE_MeasurementEventEnqueue'),
                      (QSEND,'RE_QueueSend'),(CRITICAL_ENTER,'RE_CriticalEnter'),(CRITICAL_EXIT,'RE_CriticalExit')):
        labels.append({'address':hex(addr),'name':name,'confidence':1.0,'proof':'bounded_original_ARM926_execution',
                       'evidence':'evidence/2026-11-07-refresh-side-effects.json','guard_bytes':64,
                       'guard_sha256':sha(raw[addr-BASE:addr-BASE+64])})
    return {'version':version,'input_sha256':sha(raw),'failed':0,'queue_cases':len(qresults),
            'renderer_cases':len(rresults),'critical_cases':len(critical_results),'queue_init_cases':len(init_results),
            'linked_callbacks':5,'results_sha256':fingerprint,
            'critical_examples':critical_results,'queue_init_examples':init_results,
            'queue_examples':qresults,'renderer_state_classes':len(rresults),
            'renderer_instruction_addresses_visited':len(m.renderer_coverage),
            'helper_instruction_addresses_visited':len(m.helper_coverage),
            'queue_instruction_addresses_visited':len(m.queue_coverage),
            'coverage':{'renderer':[hex(a)for a in sorted(m.renderer_coverage)],
                        'state_helpers':[hex(a)for a in sorted(m.helper_coverage)],
                        'queue_send':[hex(a)for a in sorted(m.queue_coverage)]},
            'renderer_examples':[rresults[0],next(r for r in rresults if r['mode']==1 and r['display_flag']==1 and
                not r['record_flag40'] and not r['mismatch'] and not r['latch'] and r['countdown12']==0 and r['history_ready'])],
            'linked_example':callback,'raw_windows':windows,'approved_labels':labels}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',action='append',required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();versions=[]
    for inp in args.input:
        version,path=inp.split('=',1);v=collect(version,Path(path));versions.append(v)
        print(version,v['queue_cases'],'queue;',v['renderer_cases'],'renderer;',v['linked_callbacks'],'linked callbacks')
    if len(versions)==2:assert versions[0]['results_sha256']==versions[1]['results_sha256']
    report={'schema':'ys4470.refresh-side-effects.v1','date':'2026-11-07','cpu':'UC_CPU_ARM_926','versions':versions,
            'remaining_leaf_models':{**{hex(k):v for k,v in LEAVES.items()},'0x80000544':'printf'},
            'executed_original':['queue init caller','queue constructor/list initialization','event record builder','queue available-send/full-zero-wait path','memcpy','critical enter/exit',
                'renderer control','renderer state helpers406c/4114/425c/4290/4314/2e44','numeric helpers',
                'existing callback/result/filter/sound/PIO/PWM path'],
            'limits':['Factory init requests10 slots of68 bytes; original constructor/list init execute, heap allocator is modeled.',
                'Linked queue is constructed by original code; generic ring probes use controlled fields. No waiting tasks, blocking waits/context switches excluded.',
                'Renderer/widget-format/logging leaves remain models; no full GUI or asynchronous log consumer.',
                'Renderer tests check protected-state preservation, not full visual correctness or exact display text.',
                'Synthetic initialization and interleaving; no physical UART/device/timing/acoustic measurement.']}
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
