"""Triangulate original Fast CONT ARM, independent Python, and compiled own C.

Original code runs through the already validated gate/arithmetic/PIO/PWM path.
The C reconstruction runs separately on ARM926 without any mapped peripheral.
Both machines are synthetic; calls are not assumed to be fresh UART responses.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import io
import json
import random
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from elftools.elf.elffile import ELFFile
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_READ, UC_PROT_WRITE,
                     UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from trace_sound_pwm_path import SoundMachine, oracle, ACTIVE, GATE, RESULT, PIO, PWM, TOP, RETURN
from emulate_state5_parser import BASE, EXPECTED_INPUTS

HELPER, HISTORY, RANGES = 0x80007c88, 0x805ac7b8, 0x8006397c
TABLE = ((0,10,10),(10,20,10),(20,30,8),(30,40,8),(40,50,6),(50,60,6),
         (60,70,4),(70,80,4),(80,90,2),(90,100,2),(100,1000,0))


def sha(b): return hashlib.sha256(b).hexdigest()
def signed(x): return (x & 0xffffffff) - (0x100000000 if x & 0x80000000 else 0)


def model_step(s, value):
    value = signed(value)
    if value > 1000:
        s['history'] = [1000] * 3; s['count'] = 0; s['last_median'] = -1
    s['history'][s['next']] = value
    s['next'] = (s['next'] + 1) % 3
    if s['count'] < 3: s['count'] += 1
    if s['count'] == 3:
        lo, mid, hi = sorted(s['history'])
        if (120 * lo) % (1 << 64) >= (100 * hi) % (1 << 64):
            s['last_median'] = mid
    median = s['last_median']
    return next((tone for low, high, tone in TABLE if low <= median < high), 0)


class Original(SoundMachine):
    def __init__(self, raw):
        super().__init__(raw)
        self.mu.mem_map(0x80007000, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
        self.mu.mem_write(0x80007000, raw[0x80007000-BASE:0x80008000-BASE])
        self.code_pages += (0x80007000,)
        self.gate_calls = []

    def on_code(self, mu, address, size, data):
        if address == GATE: self.gate_calls.append(self.args()[:2])
        super().on_code(mu, address, size, data)

    def on_memory(self, mu, access, address, size, value, data):
        from unicorn import UC_MEM_WRITE
        if access == UC_MEM_WRITE and size == 4 and (
                address in (HISTORY, HISTORY+4, HISTORY+8, ACTIVE+4, ACTIVE+8, ACTIVE+12)):
            return
        super().on_memory(mu, access, address, size, value, data)

    def initialize(self, state, enabled, active):
        self.reset(enabled=enabled, active=active, duty_setting=90, pwm_seed=0xabcdef00)
        self.mu.mem_write(HISTORY, struct.pack('<3i', *state['history']))
        self.mu.mem_write(ACTIVE+4, struct.pack('<IIi', state['next'], state['count'], state['last_median']))

    def step(self, value):
        self.trace.clear(); self.lower_calls.clear(); self.config_calls.clear(); self.pio_calls.clear(); self.gate_calls.clear()
        self.mu.reg_write(UC_ARM_REG_CPSR, 0x13)
        self.mu.reg_write(UC_ARM_REG_SP, TOP); self.mu.reg_write(UC_ARM_REG_LR, RETURN)
        self.mu.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        self.run(HELPER)
        assert self.mu.reg_read(UC_ARM_REG_SP) == TOP
        state = dict(zip(('next','count','last_median'), struct.unpack('<IIi', self.mu.mem_read(ACTIVE+4, 12))))
        state['history'] = list(struct.unpack('<3i', self.mu.mem_read(HISTORY, 12)))
        return state


class Reconstructed:
    def __init__(self, obj):
        elf = ELFFile(io.BytesIO(obj.read_bytes()))
        assert elf.header.e_machine == 'EM_ARM' and elf.little_endian
        sym = next(s for s in elf.get_section_by_name('.symtab').iter_symbols() if s.name == 'ys_fast_cont_update')
        section_id = sym['st_shndx']; section = elf.get_section(section_id)
        for s in elf.iter_sections():
            assert not (s['sh_type'] in ('SHT_REL','SHT_RELA') and s['sh_info'] == section_id and s.num_relocations())
        code = section.data(); assert len(code) < 0xf00
        self.entry, self.return_to, self.state_address, self.stack = 0x20000000 + sym['st_value'], 0x20000ff0, 0x30000100, 0x30000f00
        self.mu = Uc(UC_ARCH_ARM, UC_MODE_ARM); self.mu.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.mu.mem_map(0x20000000, 0x1000, UC_PROT_READ | UC_PROT_EXEC); self.mu.mem_write(0x20000000, code)
        self.mu.mem_map(0x30000000, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
        self.mu.hook_add(UC_HOOK_CODE, self.code)
        self.mu.hook_add(UC_HOOK_MEM_WRITE, self.memory)
        self.code_size, self.visited = len(code), set()

    def code(self, mu, address, size, data):
        if address == self.return_to: mu.emu_stop(); return
        assert 0x20000000 <= address < 0x20000000 + self.code_size
        self.visited.add(address)

    def memory(self, mu, access, address, size, value, data):
        assert self.state_address <= address and address+size <= self.state_address+24 or self.stack-256 <= address and address+size <= self.stack

    def initialize(self, state):
        self.mu.mem_write(self.state_address, struct.pack('<3iIIi', *state['history'], state['next'], state['count'], state['last_median']))

    def step(self, value):
        mu = self.mu; mu.reg_write(UC_ARM_REG_CPSR, 0x13)
        mu.reg_write(UC_ARM_REG_SP, self.stack); mu.reg_write(UC_ARM_REG_LR, self.return_to)
        mu.reg_write(UC_ARM_REG_R0, self.state_address); mu.reg_write(UC_ARM_REG_R1, value & 0xffffffff)
        mu.emu_start(self.entry, 0x20001000, count=1000)
        assert mu.reg_read(UC_ARM_REG_PC) == self.return_to and mu.reg_read(UC_ARM_REG_SP) == self.stack
        vals = struct.unpack('<3iIIi', mu.mem_read(self.state_address, 24))
        state = {'history': list(vals[:3]), 'next': vals[3], 'count': vals[4], 'last_median': vals[5]}
        return mu.reg_read(UC_ARM_REG_R0), state


def scenarios():
    values = (-1,0,9,10,19,20,29,30,39,40,49,50,59,60,69,70,79,80,89,90,99,100,999,1000,1001,-2147483648,2147483647)
    for value in values:
        for index in range(3):
            for enabled in (0,1,2):
                yield 'boundary', {'history':[1000]*3,'next':index,'count':0,'last_median':-1}, enabled, 0, [value]*3
    for name, seq in (
        ('stable_to_unstable_then_stable', [5,5,5,500,500,500,5,5,5]),
        ('unstable_keeps_previous_tone', [5,5,5] + [500,5]*8),
        ('open_resets_immediately', [5,5,5,1001,5,5,5]),
        ('exact_1000_does_not_reset', [5,5,5,1000,1000,1000]),
        ('mixed_sign_unsigned_comparison', [-5,5,6]),
        ('stability_equal', [100,100,120]),
        ('stability_fails', [100,100,121])):
        yield name, {'history':[1000]*3,'next':0,'count':0,'last_median':-1}, 1, 0, seq
    rng = random.Random(4470)
    pool = list(values) + [5,10,100,120,121,500]
    for i in range(100):
        state = {'history':[rng.choice(pool) for _ in range(3)],'next':rng.randrange(3),
                 'count':rng.randrange(4),'last_median':rng.choice(pool)}
        yield 'seeded_persistent', state, rng.choice((0,1,2)), rng.randrange(2), [rng.choice(pool) for _ in range(12)]


def collect(version, path, obj):
    raw = path.read_bytes(); assert sha(raw) == EXPECTED_INPUTS[version]
    assert tuple(struct.unpack_from('<iiI', raw, RANGES-BASE+12*i) for i in range(11)) == TABLE
    original, c = Original(raw), Reconstructed(obj)
    fingerprint = hashlib.sha256(); count = 0; cases = 0; examples = []
    for name, initial, enabled, active, seq in scenarios():
        state = copy.deepcopy(initial); original.initialize(state, enabled, active); c.initialize(state)
        sound = {'active':active, 'result_control':0x11223344, 'pwm_ctrl':0xabcdef00,'pwm_period':0x55667788,
                 'pio_cfg':0xa5a5a5a5,'pio_pull':0xa5a5a5a5}
        steps = []
        for value in seq:
            selector = model_step(state, value)
            actual = original.step(value); c_selector, c_state = c.step(value)
            assert actual == state == c_state, (name,value,actual,state,c_state)
            assert c_selector == selector
            action = 1 if selector else 0
            assert original.gate_calls == [[selector,action]]
            expected = oracle(selector, action, enabled, sound['active'], 90, sound['pwm_ctrl'])
            called = bool(expected['lower_calls'])
            for key in ('lower_calls','pwm_config_calls','pio_calls'):
                observed = original.config_calls if key == 'pwm_config_calls' else getattr(original,key)
                assert observed == expected[key], (name,value,key,observed,expected[key])
            if called:
                sound = {k:expected[k] for k in sound}
                assert original.trace
            else:
                assert not original.trace
            observed_sound = {'active':original.word(ACTIVE),'result_control':original.word(RESULT+0x50),
                              'pwm_ctrl':original.word(PWM),'pwm_period':original.word(PWM+4),
                              'pio_cfg':original.word(PIO),'pio_pull':original.word(PIO+0x1c)}
            assert observed_sound == sound
            fingerprint.update(json.dumps([value,state,selector,sound],sort_keys=True).encode()); count += 1
            if name not in ('boundary','seeded_persistent'):
                steps.append({'input':value,'state':copy.deepcopy(state),'selector':selector,'gate_action':action,
                              'sound_active':sound['active'],'shadow_mmio_called':called})
        if steps: examples.append({'name':name,'steps':steps})
        cases += 1
    md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    return {'version':version,'input_sha256':sha(raw),'scenarios_passed':cases,'steps_passed':count,
            'failed':0,'results_sha256':fingerprint.hexdigest(),'examples':examples,
            'original_helper_sha256':sha(raw[HELPER-BASE:0x80007dd0-BASE]),
            'assembly':[f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(raw[HELPER-BASE:0x80007dd0-BASE],HELPER)],
            'c_instruction_addresses_visited':len(c.visited),
            'approved_labels':[{'address':hex(GATE),'name':'RE_SoundControlGate','confidence':1.0,
                'proof':'bounded_original_ARM926_execution','evidence':'evidence/2026-11-07-fast-cont-filter.json',
                'guard_bytes':64,'guard_sha256':sha(raw[GATE-BASE:GATE-BASE+64])},
                {'address':hex(HELPER),'name':'RE_FastContHistoryFilter','confidence':1.0,
                'proof':'bounded_original_ARM926_execution','evidence':'evidence/2026-11-07-fast-cont-filter.json',
                'guard_bytes':64,'guard_sha256':sha(raw[HELPER-BASE:HELPER-BASE+64])}]}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',action='append',required=True,metavar='VERSION=PATH')
    ap.add_argument('--reconstruction-object',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True); args=ap.parse_args()
    versions=[]
    for item in args.input:
        version,path=item.split('=',1); v=collect(version,Path(path),args.reconstruction_object);versions.append(v)
        print(version,v['scenarios_passed'],'scenarios;',v['steps_passed'],'linked original/Python/C steps')
    if len(versions)==2: assert versions[0]['results_sha256']==versions[1]['results_sha256']
    repo=Path(__file__).resolve().parent.parent
    report={'schema':'ys4470.fast-cont-filter.v1','date':'2026-11-07','cpu':'UC_CPU_ARM_926',
        'range_table_address':hex(RANGES),'range_table':TABLE,'versions':versions,
        'reconstruction':{'source':'reconstruction/fast_cont.c','source_sha256':sha((repo/'reconstruction/fast_cont.c').read_bytes()),
                          'header_sha256':sha((repo/'reconstruction/fast_cont.h').read_bytes()),
                          'object_sha256':sha(args.reconstruction_object.read_bytes()),
                          'build':'Zig0.13.0 cc -target arm-freestanding-eabi -mcpu=arm926ej_s -marm -O2 -ffreestanding -fno-builtin -ffunction-sections -std=c11 -Wall -Wextra -Werror -c reconstruction/fast_cont.c'},
        'limits':['Valid ring index0..2/count0..3 only; signed32 scalar inputs tested, physical unit unassigned.',
                  'Original helper executes into real gate/arithmetic/pinmux/PWM code using inert RAM MMIO shadows.',
                  'C reconstruction executes separately on ARM926 with no mapped peripheral; not a complete firmware.',
                  'Helper call cadence and relation to fresh UART responses remain open; no acoustic latency measurement.']}
    args.out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':main()
