"""Hash-pinned, bounded ARM926 profile experiment; no USB or device operations.

The UART, task order, GUI schedule and conversion response source are explicit
models. Times are synthetic counter units, never physical probe-to-sound delay.
"""
from __future__ import annotations
import argparse,hashlib,json,struct
from collections import deque
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_HOOK_MEM_WRITE
from unicorn.arm_const import *

ROOT=Path(__file__).resolve().parents[2]; HERE=Path(__file__).resolve().parent
BASE=0x7fffffe0; E2_SHA='b04fb5bca7a052abfc5b1621bf50e03fd4f8116bf5cef849f1994e44d4b603b1'
V38_SHA='7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290'
V36_SHA='7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9'
THRESHOLD_SHA='884c39524942cf42580b52c0ce3ed8b33dab8d8fc4d3addd6266d1c9831c551e'
REPLY_SHA='9890a3c671987b0aa75a505e4f389532ca102f9dcf306394daa45a9328bc91e1'
UI=0x805abefc;SH=0x805ac714;HW=0x805ab924;FSM=0x805ac694;CTRL=0x805aae8c
PROFILE=0x80060a90; TIMER=0x81040000; END=0x81fff000;SP=0x81ff0000;OUT=0x81001000
SYMBOLS={'flag':0x80007f60,'apply':0x80058678,'step':0x800107cc,'ready':0x80007f7c,
         'auto':0x8001110c,'tail':0x8005fb78,'gui_tick':0x8001b5cc}
NAMES=['Base','Direct','Auto','Ready']
def sha(b):return hashlib.sha256(b).hexdigest()
def jsonwrite(p,o):p.write_text(json.dumps(o,indent=2)+'\n',encoding='utf8')

def restore_globals(original):
    """Execute the original scatter-copy/decompress routines, without hardware."""
    assert sha(original)==V38_SHA
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_926)
    u.mem_map(0x7fff0000,0x2100000);u.mem_write(BASE,original)
    for entry,src,dst,n in ((0x80000124,0x805aaab4,0x805ac098,0x468),
                            (0x800000c8,0x805ac098,0x805aaab4,0x15e4)):
        for r,v in ((UC_ARM_REG_R0,src),(UC_ARM_REG_R1,dst),(UC_ARM_REG_R2,n),
                    (UC_ARM_REG_SP,SP),(UC_ARM_REG_LR,END),(UC_ARM_REG_CPSR,0x13)):
            u.reg_write(r,v)
        u.emu_start(entry,END,count=500000)
        assert u.reg_read(UC_ARM_REG_PC)==END
    out=bytes(u.mem_read(0x805aaab4,0x15e4))
    assert sha(out)=='524ba48c4f8e6b7876fc1da735f82f197eb436947e65eac043f2d9f2b96f8be0'
    return out

class ProfileMachine:
    def __init__(self,image,profile,highspeed,scenario,*,gui_period=25,gui_phase=0,reply_delay=1,init=None):
        self.image_sha=sha(image);assert self.image_sha in (E2_SHA,V38_SHA,V36_SHA,THRESHOLD_SHA,REPLY_SHA)
        assert profile==0 or self.image_sha==E2_SHA
        self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.u.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.u.mem_map(0x7fff0000,0x2100000);self.u.mem_write(BASE,image)
        assert init is not None
        self.u.mem_write(0x805aaab4,init)
        self.u.mem_map(0x01c20000,0x10000)
        self.now=0;self.events=[];self.pending=[];self.queue=deque();self.tx=[];self.gui_period=gui_period
        self.next_gui=gui_phase;self.scenario=scenario;self.reply_delay=reply_delay;self.phase='init'
        self.steps=0;self.coverage={};self.profile=profile;self.sequence=0;self.queue_max=0
        self.sleep_count=0;self.last_fsm=None;self.queue_discards=0
        self.u.mem_write(UI,bytes([3,0,highspeed,0,0,0,0,14]));self.u.mem_write(UI+9,b'\2')
        if self.image_sha==E2_SHA:self.u.mem_write(PROFILE,bytes([profile,profile,255,255])+bytes(12))
        self.wr(CTRL+4,0x81050000);self.wr(CTRL+8,14);self.wr(SH+28,0x7fffff)
        self.wr(0x805ac770+16,1);self.wr(0x805ac770+12,50)
        self.wr(0x805abeb8,TIMER);self.wr(TIMER,gui_period);self.wr(TIMER+20,0)
        self.u.hook_add(UC_HOOK_CODE,self.code);self.u.hook_add(UC_HOOK_MEM_WRITE,self.memory)
    def wr(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
    def rd(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def byte(self,a):return self.u.mem_read(a,1)[0]
    def event(self,kind,**kw):self.events.append(dict(t=self.now,phase=self.phase,kind=kind,**kw))
    def ret(self,v=None):
        if v is not None:self.u.reg_write(UC_ARM_REG_R0,v)
        self.u.reg_write(UC_ARM_REG_PC,self.u.reg_read(UC_ARM_REG_LR))
    def raw(self,t):
        if self.scenario=='stable-low':return 50
        if self.scenario=='open-contact':return 50 if t>=101 else 6000
        if self.scenario=='contact-open':return 6000 if t>=101 else 50
        if self.scenario=='short-contact':return 50 if 101<=t<109 else 6000
        return 50
    def code(self,u,a,size,_):
        self.steps+=1
        if a!=END:self.coverage[a]=dict(address=hex(a),size=size,bytes=bytes(u.mem_read(a,size)).hex(),
            mode='Thumb'if u.reg_read(UC_ARM_REG_CPSR)&32 else'ARM')
        if a==END:u.emu_stop();return
        if a==0x80061f84:self.ret(self.now);return
        if a in (0x80060efc,0x80060f20,0x800031b8):self.ret();return
        if a==0x80060fbc:
            n=u.reg_read(UC_ARM_REG_R0);assert n==1
            self.sleep_count+=1
            if self.sleep_count==1:self.event('task_sleep',units=n)
            self.ret();return
        if a==0x80061acc:
            msg=bytes(u.mem_read(u.reg_read(UC_ARM_REG_R1),68));self.queue.append(msg)
            self.queue_max=max(self.queue_max,len(self.queue));self.event('enqueue',command=int.from_bytes(msg[:4],'little'))
            self.ret(1);return
        if a==0x800618dc:
            if self.queue:
                msg=self.queue.popleft();u.mem_write(u.reg_read(UC_ARM_REG_R1),msg)
                self.event('dequeue',command=int.from_bytes(msg[:4],'little'));self.ret(1)
            else:self.ret(0)
            return
        if a==0x80005e84:
            msg=bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0),u.reg_read(UC_ARM_REG_R1)))
            assert msg==b'\x60',msg.hex()
            request=len(self.tx)+1;self.tx.append(self.now);self.event('request',request=request,payload=msg.hex())
            if self.scenario!='missing':
                start=self.now+self.reply_delay
                raw=self.raw(start);header=0x61 if self.scenario=='wrong-header' else 0x60
                packet=bytes([header])+raw.to_bytes(3,'little')+b'\0'
                if self.scenario=='truncated':packet=packet[:2]
                for k,b in enumerate(packet):self.pending.append((start+k,self.sequence,b,request));self.sequence+=1
                self.pending.sort()
            self.ret();return
        if a==0x80000544:self.ret(0);return
        if a==0x8000326c:
            self.event('renderer',raw=self.rd(SH+28));self.ret();return
        if a==0x800038c4:self.event('numeric',float_bits=hex(u.reg_read(UC_ARM_REG_R0)))
        if a==0x800037c0:self.event('display_dispatch',raw=self.rd(SH+28))
        if a==0x80004490:
            state=(self.byte(FSM),self.byte(FSM+0x34),self.rd(FSM+0x20))
            if state!=self.last_fsm:self.event('fsm',state=state[0],busy=state[1],command=state[2])
            self.last_fsm=state
        if a==0x80004738:self.event('parser',discard_counter=self.byte(CTRL+1),rx_count=self.rd(0x805ab938))
        if a in (0x800047a8,0x800047b4):self.event('accepted',raw=u.reg_read(UC_ARM_REG_R0))
        if a==0x80005ca4 and self.phase=='service':self.event('queue_item_end',busy=self.byte(FSM+0x34))
        if a==0x80005bf0 and not(u.reg_read(UC_ARM_REG_CPSR)&0x40000000):
            self.queue_discards+=1;self.event('queue_poll_discard',busy=self.byte(FSM+0x34),control_pending=self.byte(CTRL))
        if a==0x800060d0:
            args=[u.reg_read(r) for r in (UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)]
            self.event('sound_control',args=args);self.ret();return
    def memory(self,u,access,a,size,v,_):
        pc=u.reg_read(UC_ARM_REG_PC)
        # The profile state is deliberately stored inside a reclaimed image page;
        # reject any guest write to other input-image bytes.
        if BASE<=a<BASE+5943296 and a<0x805aaab4:
            assert (PROFILE<=a and a+size<=PROFILE+16) or (size==4 and a%4==0 and (
                0x800600ac<=a<0x800600ec or a==0x8001076c)), (hex(pc),hex(a),size)
        if a==FSM and size==1:
            extra={}
            if v==6:
                count=self.rd(0x805ab938);required=self.rd(FSM+0x28)
                extra=dict(rx_count=count,required=required,header=self.byte(0x805b408c),
                    reason='incomplete_deadline'if count<required else'complete_header_mismatch')
            self.event('state_write',pc=hex(pc),old=self.byte(FSM),new=v,**extra)
        if a==PROFILE and size==1:self.event('active_profile',pc=hex(pc),old=self.byte(PROFILE),new=v,busy=self.byte(FSM+0x34))
        if a==CTRL+1 and size==1 and pc==0x8000477c:
            self.event('discard_counter_write',pc=hex(pc),value=v)
        if a==SH+28 and size==4:self.event('stored_result',pc=hex(pc),raw=v)
    def call(self,a,phase):
        self.phase=phase;u=self.u;u.reg_write(UC_ARM_REG_CPSR,0x13)
        u.reg_write(UC_ARM_REG_SP,SP);u.reg_write(UC_ARM_REG_LR,END);u.reg_write(UC_ARM_REG_R0,OUT)
        for r in (UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R6,UC_ARM_REG_R7,UC_ARM_REG_R8,UC_ARM_REG_R9,UC_ARM_REG_R10,UC_ARM_REG_R11):u.reg_write(r,0)
        u.emu_start(a,0,count=100000)
        assert u.reg_read(UC_ARM_REG_PC)==END,(hex(a),hex(u.reg_read(UC_ARM_REG_PC)))
        assert u.reg_read(UC_ARM_REG_SP)==SP
    def keycycle(self):
        self.phase='key';u=self.u;u.reg_write(UC_ARM_REG_CPSR,0x13);u.reg_write(UC_ARM_REG_SP,SP)
        u.reg_write(UC_ARM_REG_R4,SH);u.reg_write(UC_ARM_REG_R6,HW)
        u.emu_start(0x8000553c,0x80005570,count=10000)
        assert u.reg_read(UC_ARM_REG_PC)==0x80005570 and u.reg_read(UC_ARM_REG_SP)==SP
    def run(self,duration=250,switch=None):
        for t in range(duration):
            self.now=t;self.wr(0x805abbc8,t)
            if switch and t==switch[0]:
                self.u.mem_write(PROFILE+1,bytes([switch[1]]));self.event('requested_profile',new=switch[1],active=self.byte(PROFILE),busy=self.byte(FSM+0x34))
            while self.pending and self.pending[0][0]<=t:
                _,_,b,request=self.pending.pop(0);self.event('rx_byte',request=request,value=b)
                self.wr(0x01c25808,4);self.wr(0x01c25800,b);self.call(0x800073bc,'uart_isr')
            if t>=self.next_gui:
                self.call(0x8005d048,'gui');self.next_gui=t+self.rd(TIMER)
            self.call(0x80005b6c,'service')
            if t%50==0:self.keycycle()
        return self.summary()
    def summary(self):
        kinds=['request','accepted','parser','display_dispatch','renderer','sound_control','enqueue']
        counts={k:sum(e['kind']==k for e in self.events)for k in kinds}
        counts['incomplete_timeout']=sum(e.get('reason')=='incomplete_deadline'for e in self.events)
        counts['header_reject']=sum(e.get('reason')=='complete_header_mismatch'for e in self.events)
        counts['state6_total']=sum(e['kind']=='state_write'and e['new']==6 for e in self.events)
        counts['holdoff_discard']=sum(e['kind']=='discard_counter_write'for e in self.events)
        counts['busy_poll_discard']=self.queue_discards;counts['sleep_calls']=self.sleep_count
        return dict(profile=NAMES[self.profile],requested=self.byte(PROFILE+1)if self.image_sha==E2_SHA else None,
                    active=self.byte(PROFILE)if self.image_sha==E2_SHA else None,
                    highspeed=self.byte(UI+2),scenario=self.scenario,counts=counts,queue_max=self.queue_max,
                    instructions=self.steps,events=self.events)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--image',type=Path,required=True)
    ap.add_argument('--out',type=Path,default=HERE/'profile-traces.json');ap.add_argument('--smoke',action='store_true')
    a=ap.parse_args();image=a.image.read_bytes();assert sha(image)==E2_SHA
    init=restore_globals((ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes())
    scenarios=['stable-low','open-contact','contact-open','short-contact','late','wrong-header','truncated','missing']
    rows=[]
    for hs in ([1]if a.smoke else[0,1]):
        for s in (scenarios[:1]if a.smoke else scenarios):
            for profile in range(4):
                m=ProfileMachine(image,profile,hs,s,reply_delay=35 if s=='late'else 1,init=init)
                rows.append(m.run());print(NAMES[profile],hs,s,rows[-1]['counts'],flush=True)
    jsonwrite(a.out,dict(schema='ys4470.profile-traces.v1',image_sha256=sha(image),rows=rows,
        restored_globals_sha256=sha(init),models=['RTOS clock/critical/queues/sleep','task order and GUI schedule',
                'UART TX plus synthetic byte delivery through original ISR','formatter/renderer/PWM endpoints'],
        physical_device_operations=0,physical_time_units_established=False))
if __name__=='__main__':main()
