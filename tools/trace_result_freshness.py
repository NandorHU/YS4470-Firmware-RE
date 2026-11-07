"""Test refresh callback -> ResultDispatch -> original Fast CONT/gate/PWM.

The queue, renderer, printf and timer-creation APIs are explicit stubs. Original
memclr, numeric conversion, filter, gate, PWM and period-store code execute.
Parser entries are separately admitted synthetic steps, not live UART traffic.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from unicorn import UC_PROT_READ, UC_PROT_WRITE, UC_PROT_EXEC, UC_MEM_WRITE
from unicorn.arm_const import (UC_ARM_REG_CPSR, UC_ARM_REG_R0, UC_ARM_REG_R1,
                               UC_ARM_REG_R4, UC_ARM_REG_R7, UC_ARM_REG_R12,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from trace_fast_cont_filter import Original, model_step, signed, HELPER, HISTORY
from trace_sound_pwm_path import (GATE, RESULT, UI, ACTIVE, SETTINGS, TOP, RETURN,
                                  PIO, PWM, oracle, f32)
from emulate_state5_parser import BASE, EXPECTED_INPUTS, CONTROL, RX

CALLBACK, DISPATCH, PERIOD = 0x8005d048, 0x800037c0, 0x80040b84
QUEUE, RENDER, FORMAT, CREATE = 0x80006778, 0x8000326c, 0x80000544, 0x80040894
HANDLE_ROOT, TIMER_OBJECT, PARSER_STOP = 0x805abeb8, 0x10001000, 0x80004518


def sha(b): return hashlib.sha256(b).hexdigest()
def bits(f): return struct.unpack('<I',struct.pack('<f',f))[0]


def conversion(raw):
    if raw & 0xffffffff == 0x7fffff: return None
    val = f32(f32(float(signed(raw))) / struct.unpack('<f',struct.pack('<I',0x452f499a))[0])
    if bits(val) >= 0x80800000: val = 0.0
    return None if bits(val) >= 0x447a0000 else int(val)


class FreshMachine(Original):
    def __init__(self, raw):
        super().__init__(raw)
        for p in (0x80004000,0x80040000,0x80051000,0x8005d000):
            self.mu.mem_map(p,0x1000,UC_PROT_READ|UC_PROT_EXEC)
            self.mu.mem_write(p,raw[p-BASE:p-BASE+0x1000])
            self.code_pages += (p,)
        for p in (0x805aa000,0x805b4000,TIMER_OBJECT):
            self.mu.mem_map(p,0x1000,UC_PROT_READ|UC_PROT_WRITE)
        self.phase='idle'; self.stubs=[]; self.events=[]; self.reads=[]; self.writes=[]; self.parser_entries=0

    def put(self,a,v): self.mu.mem_write(a,struct.pack('<I',v&0xffffffff))
    def byte(self,a,v): self.mu.mem_write(a,bytes([v&255]))

    def back_from_stub(self):
        target=self.mu.reg_read(UC_ARM_REG_LR)
        cpsr=self.mu.reg_read(UC_ARM_REG_CPSR)
        self.mu.reg_write(UC_ARM_REG_CPSR,(cpsr&~32)|((target&1)<<5))
        self.mu.reg_write(UC_ARM_REG_PC,target&~1)

    def on_code(self,mu,address,size,data):
        if address in self.stops:
            mu.emu_stop(); return
        if self.phase=='parser':
            assert 0x80004738 <= address <= 0x800047bc and size==4
            return
        if address in (QUEUE,RENDER,FORMAT,CREATE):
            args=self.args()
            self.stubs.append({'address':hex(address),'arguments':args})
            if address==QUEUE:
                assert args[:3]==[4,0,0], args
                mu.reg_write(UC_ARM_REG_R0,0)
            elif address==CREATE:
                assert args[:3]==[CALLBACK,100,0]
                mu.reg_write(UC_ARM_REG_R0,TIMER_OBJECT)
            elif address==FORMAT:
                # printf result/side effects are excluded; return is not used
                # by the tested numeric/filter branch.
                mu.reg_write(UC_ARM_REG_R0,0)
            self.back_from_stub(); return
        if address==DISPATCH: self.events.append('result_dispatch')
        if address==HELPER: self.events.append(['filter',signed(mu.reg_read(UC_ARM_REG_R0))])
        super().on_code(mu,address,size,data)

    def on_memory(self,mu,access,address,size,value,data):
        if access!=UC_MEM_WRITE and (RESULT <= address < RESULT+0x60 or RX <= address < RX+200 or CONTROL <= address < CONTROL+16):
            self.reads.append([self.phase,hex(mu.reg_read(UC_ARM_REG_PC)),hex(address),size])
            if self.phase in ('callback','period','binding') and RX <= address < RX+200:
                raise AssertionError('refresh path unexpectedly read UART RX data')
        if access==UC_MEM_WRITE:
            self.writes.append([self.phase,hex(address),size,value & ((1<<(8*size))-1)])
            extra={(UI+7,1),(UI+9,1),(UI+10,1),(RESULT+0x20,4),(HANDLE_ROOT,4),(TIMER_OBJECT,4)}
            if self.phase=='parser':
                assert (address,size) in ((CONTROL+1,1),(RESULT+0x1c,4),(RESULT+0x20,4))
                return
            if (address,size) in extra: return
        super().on_memory(mu,access,address,size,value,data)

    def initialize_case(self,counter=0,raw=14023,holdoff=2):
        self.initialize({'history':[1000]*3,'next':0,'count':0,'last_median':-1},1,0)
        self.mu.mem_write(CONTROL,bytes(16));self.byte(CONTROL+1,holdoff);self.put(CONTROL+8,34)
        self.mu.mem_write(RX,b'\x5e\x01\x02\x03\x04'+bytes(195))
        self.mu.mem_write(UI,bytes(0x38));self.byte(UI,4);self.byte(UI+7,34);self.byte(UI+9,counter)
        self.put(RESULT+0x1c,raw);self.put(RESULT+0x20,0)
        self.put(0x805ab918,0)  # unrelated notification state branch excluded
        self.put(HANDLE_ROOT,TIMER_OBJECT);self.put(TIMER_OBJECT,0xfeedface)
        self.put(SETTINGS+0x18,1)
        self.expected_state={'history':[1000]*3,'next':0,'count':0,'last_median':-1}
        self.expected_sound={'active':0,'result_control':0x11223344,'pwm_ctrl':0xabcdef00,
                             'pwm_period':0x55667788,'pio_cfg':0xa5a5a5a5,'pio_pull':0xa5a5a5a5}
        self.parser_entries=0; self.clear_trace()

    def clear_trace(self):
        self.trace.clear();self.lower_calls.clear();self.config_calls.clear();self.pio_calls.clear();self.gate_calls.clear()
        self.events.clear();self.stubs.clear();self.reads.clear();self.writes.clear()

    def setup_regs(self):
        self.mu.reg_write(UC_ARM_REG_CPSR,0x13);self.mu.reg_write(UC_ARM_REG_SP,TOP)
        self.mu.reg_write(UC_ARM_REG_LR,RETURN)

    def callback(self):
        before=bytes(self.mu.mem_read(RESULT+0x1c,8));before_rx=bytes(self.mu.mem_read(RX,200))
        holdoff=self.mu.mem_read(CONTROL+1,1)[0];counter=self.mu.mem_read(UI+9,1)[0]
        raw=struct.unpack('<I',before[:4])[0];expected_events=[]; expected_gate=[]
        if counter>=2:
            expected_events=['result_dispatch'];value=conversion(raw)
            if value is not None:
                selector=model_step(self.expected_state,value);expected_gate=[[selector,1 if selector else 0]]
                expected_events.append(['filter',value])
            else: expected_gate=[[0,0]]
        self.clear_trace();self.setup_regs();self.phase='callback'
        self.run(CALLBACK)
        assert self.mu.reg_read(UC_ARM_REG_SP)==TOP
        assert bytes(self.mu.mem_read(RESULT+0x1c,8))==before
        assert bytes(self.mu.mem_read(RX,200))==before_rx and self.mu.mem_read(CONTROL+1,1)[0]==holdoff
        assert self.mu.mem_read(UI+9,1)[0]==(counter+1 if counter<2 else counter)
        assert self.events==expected_events and self.gate_calls==expected_gate,(raw,self.events,expected_events,self.gate_calls,expected_gate)
        actual_state={'history':list(struct.unpack('<3i',self.mu.mem_read(HISTORY,12))),
                      **dict(zip(('next','count','last_median'),struct.unpack('<IIi',self.mu.mem_read(ACTIVE+4,12))))}
        assert actual_state==self.expected_state
        if expected_gate:
            selector,action=expected_gate[0]
            expected=oracle(selector,action,1,self.expected_sound['active'],90,self.expected_sound['pwm_ctrl'])
            for key,actual in (('lower_calls',self.lower_calls),('pwm_config_calls',self.config_calls),('pio_calls',self.pio_calls)):
                assert actual==expected[key]
            if expected['lower_calls']: self.expected_sound={k:expected[k] for k in self.expected_sound}
        observed={'active':self.word(ACTIVE),'result_control':self.word(RESULT+0x50),
                  'pwm_ctrl':self.word(PWM),'pwm_period':self.word(PWM+4),
                  'pio_cfg':self.word(PIO),'pio_pull':self.word(PIO+0x1c)}
        assert observed==self.expected_sound
        assert self.word(TIMER_OBJECT)==(0xfeedface if counter<2 else 25)
        assert not any(w[1]==hex(RESULT+0x1c) for w in self.writes)
        return {'raw_result':signed(raw),'parser_entries':self.parser_entries,'discard_count':holdoff,
                'warmup_counter':self.mu.mem_read(UI+9,1)[0],'events':copy.deepcopy(self.events),
                'filter_state':copy.deepcopy(actual_state),'gate_calls':copy.deepcopy(self.gate_calls),
                'sound_active':observed['active'],'period_field':self.word(TIMER_OBJECT),
                'result_and_rx_unchanged':True,'data_read_trace':copy.deepcopy(self.reads),
                'stub_addresses':[s['address'] for s in self.stubs]}

    def parser(self,raw24,selector=0,command=0x1b):
        count=self.mu.mem_read(CONTROL+1,1)[0];old=bytes(self.mu.mem_read(RESULT+0x1c,8))
        assert command in (0x1b,0x1d)
        self.mu.mem_write(RX,bytes([0x5e if command==0x1b else 0x60])+(raw24&0xffffff).to_bytes(3,'little')+bytes([selector]))
        self.clear_trace();self.setup_regs();self.phase='parser'
        self.mu.reg_write(UC_ARM_REG_R1,command);self.mu.reg_write(UC_ARM_REG_R7,0);self.mu.reg_write(UC_ARM_REG_R12,RX)
        self.run(0x80004738,(PARSER_STOP,));self.parser_entries+=1
        if count:
            assert bytes(self.mu.mem_read(RESULT+0x1c,8))==old
            assert self.mu.mem_read(CONTROL+1,1)[0]==count-1
        else:
            val=raw24 if raw24<0x800000 else raw24-0x1000000
            assert self.word(RESULT+0x1c)==val&0xffffffff and self.word(RESULT+0x20)==(0 if command==0x1b else min(selector,6))
        return {'raw24':raw24,'command':hex(command),'published':not bool(count),'count_before':count,
                'count_after':self.mu.mem_read(CONTROL+1,1)[0],'write_trace':copy.deepcopy(self.writes)}

    def period_probe(self,mode,highspeed,secondary):
        self.initialize_case(counter=2);self.byte(UI,mode);self.byte(UI+2,highspeed);self.byte(UI+8,secondary)
        self.setup_regs();self.mu.reg_write(UC_ARM_REG_R4,UI);self.phase='period'
        self.run(0x8005d1e0,(PERIOD,));actual=self.args()[:2]
        expected=25 if mode==4 or mode==1 and highspeed==1 and secondary==21 else (100 if highspeed==1 else 200)
        assert actual==[TIMER_OBJECT,expected]
        return actual[1]

    def binding(self):
        self.initialize_case();self.phase='binding';self.setup_regs();self.run(0x800518bc,(0x800518d8,))
        assert self.stubs==[{'address':hex(CREATE),'arguments':[CALLBACK,100,0,self.stubs[0]['arguments'][3]]}]
        assert self.word(HANDLE_ROOT)==TIMER_OBJECT
        return {'entry':'0x800518bc','stop':'0x800518d8','create_api':hex(CREATE),
                'callback':hex(CALLBACK),'period_argument':100,'user_data':0,'stored_handle_root':hex(HANDLE_ROOT)}


def collect(version,path):
    raw=path.read_bytes();assert sha(raw)==EXPECTED_INPUTS[version]
    assert struct.unpack_from('<3I',raw,0x80003af8-BASE)==(0x452f499a,0x80800000,0x447a0000)
    m=FreshMachine(raw);fingerprint=hashlib.sha256();cases=0
    def record(obj):fingerprint.update(json.dumps(obj,sort_keys=True).encode())
    for counter in range(256):
        m.initialize_case(counter=counter);record(m.callback());cases+=1
    for counter in (0,1,2):
        for value in (-2147483648,-1,0,1,14023,280460,2804599,2804600,2804601,8388606,8388607,22436800,2147483647):
            m.initialize_case(counter=counter,raw=value);record(m.callback());cases+=1
    m.initialize_case();repeated=[m.callback() for _ in range(5)]
    assert [x['filter_state']['count'] for x in repeated]==[0,0,1,2,3]
    assert repeated[-1]['filter_state']['last_median']==5 and repeated[-1]['sound_active']==1
    assert all(x['parser_entries']==0 and x['discard_count']==2 for x in repeated)
    record(repeated)
    m.initialize_case(counter=2);interleaved=[]
    for _ in range(3): interleaved.append({'callback':m.callback()})
    for _ in range(3): interleaved.append({'parser':m.parser(1402300),'callback':m.callback()})
    for _ in range(2): interleaved.append({'callback':m.callback()})
    assert [x['parser']['published'] for x in interleaved if 'parser'in x]==[False,False,True]
    assert [x['callback']['sound_active'] for x in interleaved]==[1 if i>=2 and i<7 else 0 for i in range(8)]
    record(interleaved)
    bypass_examples=[]
    for rejected in (0x7fffff,2804601):
        m.initialize_case(counter=2)
        for _ in range(3):m.callback()
        before=copy.deepcopy(m.expected_state)
        m.put(RESULT+0x1c,rejected);off=m.callback()
        assert off['filter_state']==before and off['events']==['result_dispatch'] and off['sound_active']==0
        m.put(RESULT+0x1c,14023);resume=m.callback()
        assert resume['filter_state']['last_median']==5 and resume['sound_active']==1
        bypass_examples.append({'rejected_raw':rejected,'off':off,'resume':resume})
    record(bypass_examples)
    periods=[]
    for mode in range(6):
        for highspeed in (0,1,2):
            for secondary in (20,21,22):periods.append([mode,highspeed,secondary,m.period_probe(mode,highspeed,secondary)])
    record(periods);binding=m.binding();record(binding)
    uses=[]
    for address in range(0x8000326c,0x800037c0,4):
        w=struct.unpack_from('<I',raw,address-BASE)[0]
        if w&0x0f7f0000==0x051f0000:
            lit=address+8+((w&0xfff)if w&0x800000 else -(w&0xfff))
            if lit==0x800037bc:uses.append(hex(address))
    assert struct.unpack_from('<I',raw,0x800037bc-BASE)[0]==0x805abf10 and uses
    windows={};md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    for start,end in ((CALLBACK,0x8005d254),(DISPATCH,0x800039a0),(0x800518bc,0x800518d8),(PERIOD,PERIOD+8)):
        data=raw[start-BASE:end-BASE];windows[hex(start)]={'end_exclusive':hex(end),'sha256':sha(data),
            'assembly':[f'{i.address:08x} {i.mnemonic} {i.op_str}'for i in md.disasm(data,start)]}
    labels=[]
    for addr,name in ((GATE,'RE_SoundControlGate'),(HELPER,'RE_FastContHistoryFilter'),
                      (DISPATCH,'RE_ResultDispatch'),(CALLBACK,'RE_MeasurementRefreshCallback'),
                      (PERIOD,'RE_CallbackPeriodStore')):
        labels.append({'address':hex(addr),'name':name,'confidence':1.0,'proof':'bounded_original_ARM926_execution',
                       'evidence':'evidence/2026-11-07-result-freshness.json','guard_bytes':64,
                       'guard_sha256':sha(raw[addr-BASE:addr-BASE+64])})
    return {'version':version,'input_sha256':sha(raw),'failed':0,'callback_matrix_cases':cases,
            'persistent_callback_steps':23,'admitted_parser_steps':3,'period_branch_cases':len(periods),'binding_cases':1,
            'results_sha256':fingerprint.hexdigest(),'unchanged_result_example':repeated,'interleaved_example':interleaved,
            'invalid_bypass_examples':bypass_examples,'period_branches':periods,'callback_binding':binding,
            'caller_conversion':{'divisor_bits':'0x452f499a','divisor_f32':2804.60009765625,
                'negative_clamp_bits':'0x80800000','reject_at_f32':1000.0,
                'helper_argument_domain_this_path':'0..999 inclusive after truncation; sentinel and >=1000 bypass filter'},
            'raw_windows':windows,'approved_labels':labels,
            'entry_correction':{'old_seed':'0x800037bc','word':'0x805abf10','literal_load_sites':uses,
                                'confirmed_entry':hex(DISPATCH),'real_call_site':'0x8005d1a0'}}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',action='append',required=True)
    ap.add_argument('--out',type=Path,required=True);args=ap.parse_args();versions=[]
    for inp in args.input:
        version,path=inp.split('=',1);v=collect(version,Path(path));versions.append(v)
        print(version,v['callback_matrix_cases'],'matrix;',v['persistent_callback_steps'],'persistent callback;',v['admitted_parser_steps'],'parser steps')
    if len(versions)==2:assert versions[0]['results_sha256']==versions[1]['results_sha256']
    report={'schema':'ys4470.result-freshness.v1','date':'2026-11-07','cpu':'UC_CPU_ARM_926','versions':versions,
        'followup_static_observation':{'executed_this_run':False,'reader':'0x800044a8',
            'word':'0xe5915030','base_alias':'0x8000449c: add r1,sb,#0',
            'meaning':'Loads FSM+0x30 into r5; bound its tick-comparison consumers next. Older MOV-only literal tracing missed this ADD-zero alias.'},
        'executed_original_paths':['callback control','memclr','result conversion','history filter','sound gate/arithmetic/PIO/PWM','period store','admitted state5 parser slice'],
        'stubbed_apis':{'queue':hex(QUEUE),'renderer':hex(RENDER),'printf':hex(FORMAT),'callback_create':hex(CREATE)},
        'limits':['Synthetic interleaving with explicit stable UI/notification state; not a complete GUI/queue/scheduler/UART model.',
                  'No physical device, new UART ISR input, live timing or acoustic measurements.',
                  'Three filter calls are not proven to represent three distinct published UART samples.',
                  'Period arguments25/100/200 are unassigned time units here; original power-on history initialization remains open.']}
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
