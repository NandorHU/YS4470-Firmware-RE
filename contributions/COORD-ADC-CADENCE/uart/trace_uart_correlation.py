"""Original ARM926 transport and late-reply attribution, without device I/O.

TX, RX ISR, builder, FSM and critical/tick helpers execute. Only UART status,
byte arrival, counter advance and explicit ISR interleavings are host models.
"""
from __future__ import annotations
import hashlib,json,struct
from pathlib import Path
from unicorn import (Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_PROT_READ,UC_PROT_WRITE,UC_PROT_EXEC,
    UC_HOOK_CODE,UC_HOOK_MEM_READ,UC_HOOK_MEM_WRITE,UC_MEM_WRITE)
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
BASE=0x7fffffe0;FSM=0x805ac694;CTRL=0x805aae8c;RESULT=0x805ac714
RX=0x805b408c;COUNT=0x805ab938;TXBUF=0x805b4154;UART=0x01c25800
COUNTER=0x805abbc8;NEST=0x805abbf8;RET=0x10000000;TOP=0x10014000;ARGS=0x10018000
WINDOWS=((0x80004490,0x80004808),(0x8000482c,0x80004930),
    (0x80005e84,0x80005f10),(0x80006dc8,0x80006e1c),(0x800073bc,0x80007418),
    (0x800009c4,0x80000afc),(0x80000b4c,0x80000ba8),(0x800031b8,0x800031e0),
    (0x80060efc,0x80060f58),(0x80061f84,0x80061fa0))
def sha(b):return hashlib.sha256(b).hexdigest()
def write(p,o):p.write_text(json.dumps(o,indent=2)+'\n',encoding='utf8')

class OriginalUART:
    def __init__(self,raw):
        self.raw=raw;self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.u.ctl_set_cpu_model(UC_CPU_ARM_926)
        high=(BASE+len(raw)+0xfff)&~0xfff
        self.u.mem_map(BASE&~0xfff,high-(BASE&~0xfff),UC_PROT_READ|UC_PROT_EXEC);self.u.mem_write(BASE,raw)
        self.u.mem_protect(0x805aa000,0x1000,UC_PROT_READ|UC_PROT_WRITE)
        for p,n in ((0x805ab000,0x2000),(0x805b4000,0x1000),(0x01c20000,0x10000),
                    (0x10010000,0x10000),(RET,0x1000)):
            self.u.mem_map(p,n,UC_PROT_READ|UC_PROT_WRITE)
        self.u.mem_protect(RET,0x1000,UC_PROT_READ|UC_PROT_EXEC)
        self.coverage={};self.u.hook_add(UC_HOOK_CODE,self.code)
        self.u.hook_add(UC_HOOK_MEM_READ|UC_HOOK_MEM_WRITE,self.memory)
        self.reset()
    def put(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def rd(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def byte(self,a):return self.u.mem_read(a,1)[0]
    def event(self,kind,**kw):self.events.append(dict(t=self.now,kind=kind,**kw))
    def reset(self):
        for a,n in ((0x805aa000,0x3000),(0x805b4000,0x1000)):
            self.u.mem_write(a,bytes(n))
        self.now=0;self.events=[];self.wire=[];self.accesses=[];self.ready_reads=0;self.total_ready_reads=0;self.busy_reads_per_byte=0
        self.injection=None;self.pause=False;self.in_isr=False;self.phase='idle';self.instruction_count=0
        self.critical_clear_checks=0
        self.put(CTRL+8,14);self.put(RESULT+28,0x7fffff);self.put(UART+0x7c,2)
        self.u.mem_write(RX,b'\xa5'*200);self.u.mem_write(TXBUF,b'\x5a'*200)
    def code(self,u,a,n,_):
        if a==RET:u.emu_stop();return
        assert n==4 and any(lo<=a<hi for lo,hi in WINDOWS),hex(a)
        self.coverage[a]=bytes(u.mem_read(a,n)).hex();self.instruction_count+=1
        if self.injection and not self.in_isr and a==self.injection['site'] and not self.injection['done']:
            assert not(u.reg_read(UC_ARM_REG_CPSR)&0x80),'Do not inject a maskable ISR while IRQ-masked'
            self.pause=True;u.emu_stop();return
        if a==0x80005e84:self.event('send_descriptor',pointer=hex(u.reg_read(UC_ARM_REG_R0)),count=u.reg_read(UC_ARM_REG_R1))
        if a==0x80004738:self.event('parse',rx_count=self.rd(COUNT),frame=bytes(u.mem_read(RX,5)).hex(),holdoff=self.byte(CTRL+1))
        if a==0x8000482c:self.event('finalize',status=u.reg_read(UC_ARM_REG_R0))
    def memory(self,u,access,a,n,v,_):
        pc=u.reg_read(UC_ARM_REG_PC)
        if 0x01c20000<=a<0x01c30000:
            assert a in (UART,UART+8,UART+0x7c,0x01c208c4),(hex(pc),hex(a),n)
            self.accesses.append((hex(pc),'write'if access==UC_MEM_WRITE else'read',hex(a),n))
            if access!=UC_MEM_WRITE and a==UART+0x7c:
                self.ready_reads+=1;self.total_ready_reads+=1;ready=self.ready_reads>self.busy_reads_per_byte
                self.put(a,2 if ready else 0)
            if access==UC_MEM_WRITE and a==UART:
                assert pc==0x80006e10 and n==4
                self.wire.append(v&255);self.ready_reads=0;self.event('uart_tx',value=v&255)
        if access!=UC_MEM_WRITE:return
        allowed=(0x10010000<=a and a+n<=0x10020000)or(a==0x01c208c4 and n==4)or(a==UART and n==4)
        allowed|=RX<=a and a+n<=RX+200 or TXBUF<=a and a+n<=TXBUF+200
        allowed|=FSM<=a and a+n<=FSM+0x3c
        allowed|=(a==COUNT and n==4)or(a==NEST and n==4)or(a==CTRL+1 and n==1)
        allowed|=(a in (RESULT+28,RESULT+32)and n==4)
        # Builder/finalizer reset a second transport bookkeeping word too.
        allowed|=(a in (0x805ab920,0x805ab91c)and n==4)
        assert allowed,(hex(pc),hex(a),n,hex(v))
        if a==COUNT:self.event('rx_count',pc=hex(pc),old=self.rd(COUNT),new=v)
        if a==COUNT and pc==0x80004558:
            assert u.reg_read(UC_ARM_REG_CPSR)&0x80 and self.rd(NEST)>0
            self.critical_clear_checks+=1
        if a==FSM and n==1:self.event('state',pc=hex(pc),old=self.byte(FSM),new=v)
        if a==RESULT+28:self.event('publish',pc=hex(pc),raw=v)
    def invoke(self,entry,args=(),*,nested=False):
        u=self.u;u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_SP,TOP-0x1000 if nested else TOP)
        u.reg_write(UC_ARM_REG_LR,RET)
        saved_regs=(UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11)
        before=[u.reg_read(r)for r in saved_regs]
        for reg,value in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(reg,value)
        start=entry
        while True:
            self.pause=False;u.emu_start(start,0,count=50000)
            if not self.pause:break
            saved=u.context_save();self.injection['done']=True
            self.event('interleave',site=hex(self.injection['site']),irq_masked=False)
            for b in self.injection['packet']:self.receive(b,nested=True)
            u.context_restore(saved);start=u.reg_read(UC_ARM_REG_PC)
        assert u.reg_read(UC_ARM_REG_PC)==RET,(hex(entry),hex(u.reg_read(UC_ARM_REG_PC)))
        assert u.reg_read(UC_ARM_REG_SP)==(TOP-0x1000 if nested else TOP)
        assert self.rd(NEST)==0
        assert [u.reg_read(r)for r in saved_regs]==before
        return u.reg_read(UC_ARM_REG_R0)
    def receive(self,value,status=4,*,nested=False):
        self.event('fixture_rx',value=value&255,source='explicit host fixture, not hardware')
        self.put(UART+8,status);self.put(UART,value)
        self.in_isr=True
        try:self.invoke(0x800073bc,nested=nested)
        finally:self.in_isr=False
    def build(self,command=0x1d):
        self.put(ARGS,command);self.invoke(0x8000489c,(1,ARGS,1))
    def step(self,now):
        self.now=now&0xffffffff;self.put(COUNTER,self.now);self.invoke(0x80004490)
        return self.byte(FSM)
    def send(self,payload,busy=0,alignment=0):
        self.u.mem_write(ARGS+alignment,bytes(payload));self.busy_reads_per_byte=busy
        return self.invoke(0x80005e84,(ARGS+alignment,len(payload)))

def replay_late(m,command,arrival):
    m.reset();m.build(command);header=0x60 if command==0x1d else 0x5e
    packet=bytes([header,50,0,0,0]);history=[]
    for t in range(75):
        if arrival<=t<arrival+len(packet):m.now=t;m.receive(packet[t-arrival])
        history.append(m.step(t))
    published=[e for e in m.events if e['kind']=='publish']
    return dict(command=hex(command),first_old_frame_byte_at=arrival,published=published,
        tx_bytes=bytes(m.wire).hex(),states=history,events=m.events,
        fixture='Only the first request is assigned this delayed frame; the retry has no fresh reply.')

def main():
    inputs=json.loads((ROOT/'original-firmware/manifest.json').read_text())['images'];versions=[]
    for item in inputs:
        raw=(ROOT/item['path']).read_bytes();assert sha(raw)==item['sha256'];m=OriginalUART(raw)
        m.build();m.step(0);print(item['version'],'wire',bytes(m.wire).hex(),'state',m.byte(FSM),flush=True)
        row=replay_late(m,0x1d,33)
        print('late33 publish',row['published'],'wire',row['tx_bytes'],flush=True)
        for site in (0x8000456c,0x80005efc,0x800045e4):
            m.reset();m.build();m.injection=dict(site=site,packet=b'\x60\x32\0\0\0',done=False)
            for t in range(4):m.step(t)
            print('interleave',hex(site),'published',[e for e in m.events if e['kind']=='publish'],flush=True)
        versions.append(dict(version=item['version'],sha256=sha(raw),example=row))
    write(HERE/'scout.json',dict(versions=versions))
if __name__=='__main__':main()
