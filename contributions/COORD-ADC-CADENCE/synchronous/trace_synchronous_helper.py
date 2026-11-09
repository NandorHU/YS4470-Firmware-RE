"""Original synchronous command helper for the two proven startup command IDs.

The sender, UART byte-output, ISR, GPIO clear/set, copy and clear routines
execute on ARM926. Only sleep delivery/UART register status are explicit models.
No device, flash, normal-firmware debugger or physical timing is involved.
"""
import argparse,hashlib,json,struct,sys
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3]);ap.add_argument('--out-dir',type=Path,default=Path(__file__).resolve().parent);a=ap.parse_args()
ROOT=a.repo.resolve();OUT=a.out_dir.resolve();sys.path.insert(0,str(ROOT/'contributions/COORD-ADC-CADENCE/uart'))
from trace_uart_correlation import OriginalUART,BASE,COUNT,RX,TXBUF,FSM,COUNTER,NEST,RET,TOP,sha
from unicorn.arm_const import *

SCENARIOS=[
 dict(name='missing',at=None,point=None,attempt=1,packet='none',result=0,attempts=2,sleeps=1000,count=0),
 dict(name='one-byte-first-check',at=0,point='check',attempt=1,packet='one',result=1,attempts=1,sleeps=0,count=1),
 dict(name='five-bytes-first-check',at=0,point='check',attempt=1,packet='five',result=1,attempts=1,sleeps=0,count=5),
 dict(name='wrong-header',at=0,point='check',attempt=1,packet='wrong',result=0,attempts=2,sleeps=1000,count=0),
 dict(name='first-after499-sleeps',at=499,point='sleep',attempt=1,packet='one',result=1,attempts=1,sleeps=499,count=1),
 dict(name='first-after500-sleeps',at=500,point='sleep',attempt=1,packet='one',result=0,attempts=2,sleeps=1000,count=0),
 dict(name='second-first-check',at=0,point='check',attempt=2,packet='one',result=1,attempts=2,sleeps=500,count=1),
 dict(name='second-after499-sleeps',at=499,point='sleep',attempt=2,packet='one',result=1,attempts=2,sleeps=999,count=1),
 dict(name='second-after500-sleeps',at=500,point='sleep',attempt=2,packet='one',result=0,attempts=2,sleeps=1000,count=1),
 dict(name='old-header-during-tx',at=0,point='tx',attempt=1,packet='one',result=1,attempts=1,sleeps=0,count=1),
]

class Synchronous(OriginalUART):
    def reset(self):
        super().reset();self.attempt=0;self.sleeps=[];self.per_attempt={};self.fired=False;self.scenario=None
    def packet(self):
        h=self.payload[0]
        return {'one':bytes([h]),'five':bytes([h,0x32,0xff,0x12,0xff]),'wrong':bytes([h^1])}[self.scenario['packet']]
    def pause_for_reply(self,u,site):
        assert not(u.reg_read(UC_ARM_REG_CPSR)&0x80)
        self.fired=True;self.injection=dict(site=site,packet=self.packet(),done=False);self.pause=True;u.emu_stop()
    def code(self,u,pc,n,data):
        if self.scenario is not None and not self.in_isr:
            s=self.scenario
            if pc==0x80005e84:
                self.attempt+=1;self.per_attempt[self.attempt]=0
            if pc==0x80060fbc:
                units=u.reg_read(UC_ARM_REG_R0);assert units==1
                self.sleeps.append(units);self.per_attempt[self.attempt]+=1;self.now+=1;self.put(COUNTER,self.now)
                u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
                if not self.fired and s['point']=='sleep'and s['attempt']==self.attempt and self.per_attempt[self.attempt]==s['at']:
                    self.pause_for_reply(u,pc)
                return
            if pc in(0x80005fcc,0x80006024)and not self.fired and s['point']=='check'and s['attempt']==self.attempt:
                self.pause_for_reply(u,pc);return
            if pc==0x80005efc and not self.fired and s['point']=='tx'and s['attempt']==self.attempt:
                self.pause_for_reply(u,pc);return
        if 0x80005f14<=pc<0x80006090:
            assert n==4;self.coverage[pc]=bytes(u.mem_read(pc,n)).hex();self.instruction_count+=1;return
        super().code(u,pc,n,data)
    def run(self,command,scenario):
        self.reset();self.command=command;self.scenario=scenario
        assert command in(9,19)and self.byte(FSM+0x34)==0
        p,n=struct.unpack_from('<IB',self.raw,0x8006367c-BASE+command*8)
        assert BASE<=p and p+n<=BASE+len(self.raw)and 0<n<=199
        self.payload=self.raw[p-BASE:p-BASE+n];frame=self.payload+bytes([sum(self.payload)&255])
        result=self.invoke(0x80005f14,(command,))
        assert result==scenario['result']and self.attempt==scenario['attempts']
        assert len(self.sleeps)==scenario['sleeps']and self.rd(COUNT)==scenario['count']
        assert bytes(self.wire)==frame*self.attempt
        assert self.rd(0x01c208c4)&0xc==0 and self.rd(NEST)==0
        if scenario['at']is not None:assert self.fired
        # This helper acknowledges a header, not a five-byte measurement frame.
        return dict(command=command,caller_scope='GaugeCmdTask startup command argument proven in earlier packet execution',
            scenario=scenario['name'],return_value=result,send_attempts=self.attempt,
            requested_sleep_calls=len(self.sleeps),requested_sleep_units=sum(self.sleeps),
            source_hex=self.payload.hex(),wire_hex=bytes(self.wire).hex(),rx_count_at_return=self.rd(COUNT),
            rx_prefix_at_return=bytes(self.u.mem_read(RX,5)).hex(),gpio_bits2_3_cleared=True,
            events=self.events,instruction_hook_count=self.instruction_count)

versions=[]
for item in json.loads((ROOT/'original-firmware/manifest.json').read_text())['images']:
    raw=(ROOT/item['path']).read_bytes();assert sha(raw)==item['sha256'];m=Synchronous(raw)
    rows=[m.run(cmd,s)for cmd in(9,19)for s in SCENARIOS]
    versions.append(dict(version=item['version'],input_sha256=sha(raw),cases=rows,
        observed_instructions=[dict(address=hex(pc),bytes=b)for pc,b in sorted(m.coverage.items())]))
    print(item['version'],'PASS',len(rows),'synchronous helper cases',flush=True)
assert versions[0]['cases']==versions[1]['cases']and versions[0]['observed_instructions']==versions[1]['observed_instructions']
OUT.mkdir(parents=True,exist_ok=True)
(OUT/'synchronous-validation.json').write_text(json.dumps(dict(schema='ys4470.synchronous-execution.v1',
    source_sha256=sha(Path(__file__).read_bytes()),reused_uart_harness_sha256=sha((ROOT/'contributions/COORD-ADC-CADENCE/uart/trace_uart_correlation.py').read_bytes()),
    cases=sum(len(v['cases'])for v in versions),versions=versions,physical_device_operations=0,
    limits=['Original helper tested only for startup descriptor IDs9/19 with valid buffers and initial FSM idle.',
        'Sleep is a return-only scheduling model with explicit byte-delivery interleaves. Counts/units are not milliseconds or physical delay.',
        'UART readiness/receive status and reply source are synthetic; exception entry, task order and external device semantics are unproven.',
        'Matching one-byte header sufficiency is a helper ACK observation, not the measurement FSM\'s five-byte admission rule.',
        'A reply delivered after the final modeled sleep can miss its final check; this establishes code order, not a warranted firmware timing change.',
        'No source generator, firmware patch, full-device emulation or device operation occurs.']),indent=2)+'\n',encoding='utf8')
print('PASS',sum(len(v['cases'])for v in versions),'original startup-helper cases')
