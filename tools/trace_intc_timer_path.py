"""Execute original YS-4470 INTC/timer routines with inert MMIO shadows.

Reference register definitions guide the independent oracle. No reference code
is copied into the firmware, and no physical device operation is performed.
The IRQ bridge is a control-flow slice, not a complete exception/RTOS model.
"""
from __future__ import annotations
import argparse
import hashlib
import itertools
import json
import struct
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM
from unicorn import (Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_PROT_READ, UC_PROT_WRITE,
                     UC_PROT_EXEC, UC_HOOK_CODE, UC_HOOK_MEM_READ, UC_HOOK_MEM_WRITE, UC_MEM_WRITE)
from unicorn.arm_const import (UC_CPU_ARM_926, UC_ARM_REG_CPSR, UC_ARM_REG_R0,
                               UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3,
                               UC_ARM_REG_R4, UC_ARM_REG_R5, UC_ARM_REG_R6,
                               UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC)
from emulate_state5_parser import BASE, EXPECTED_INPUTS

INTC, TIMER = 0x01c20400, 0x01c20c00
FLAG, HANDLERS, ALTERNATE = 0x805ab940, 0x805ab944, 0x805ab9e8
RAM, STACK, TOP, RETURN = 0x805ab000, 0x10000000, 0x10000f00, 0x10002ff0
REGISTER, DISPATCH, CONFIGURE, START = 0x80005274, 0x80005260, 0x800071a0, 0x8000725c
TICK, SCHEDULE = 0x80061fa4, 0x800612f8
SCOPES = ((DISPATCH, 0x80005270), (REGISTER, 0x80005328), (CONFIGURE, 0x80007250),
          (START, 0x80007284), (0x8000230c, 0x80002364), (0x800617ec, 0x80061818),
          (0x8005bf54, 0x8005bf68))
REGS = (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)
MMIO = {INTC, INTC + 4, INTC + 0x10, INTC + 0x20, INTC + 0x24,
        *(INTC + 0x60 + 4 * i for i in range(4)), TIMER, TIMER + 4,
        *(TIMER + 0x10 + 0x10 * i for i in range(3)),
        *(TIMER + 0x14 + 0x10 * i for i in range(3))}


def u32(x): return x & 0xffffffff
def sha(x): return hashlib.sha256(x).hexdigest()
def packed(x): return struct.pack('<I', u32(x))


class Machine:
    def __init__(self, raw):
        self.uc = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.uc.ctl_set_cpu_model(UC_CPU_ARM_926)
        for page in (0x80002000, 0x80005000, 0x80007000, 0x80061000, 0x8005b000):
            self.uc.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_EXEC)
            self.uc.mem_write(page, raw[page - BASE:page - BASE + 0x1000])
        for page in (RAM, STACK, 0x01c20000):
            self.uc.mem_map(page, 0x1000, UC_PROT_READ | UC_PROT_WRITE)
        self.uc.mem_map(0x10002000, 0x2000, UC_PROT_READ | UC_PROT_EXEC)
        self.uc.hook_add(UC_HOOK_CODE, self.code)
        self.uc.hook_add(UC_HOOK_MEM_READ | UC_HOOK_MEM_WRITE, self.memory)
        self.visited = set()
        self.reset()

    def reset(self, flag=0):
        self.uc.mem_write(RAM, bytes([0xa5]) * 0x1000)
        self.uc.mem_write(STACK, bytes([0xcc]) * 0x1000)
        self.uc.mem_write(0x01c20000, bytes(0x1000))
        self.uc.mem_write(FLAG, bytes([flag]))
        for i in range(41):
            self.put(HANDLERS + 4 * i, 0x10003000 + 8 * i)
            self.put(ALTERNATE + 4 * i, 0x10003800 + 8 * i)
        self.put(INTC + 4, 0x76543210)
        self.put(INTC + 0x20, 0x01234567); self.put(INTC + 0x24, 0x89abcdef)
        for i in range(4): self.put(INTC + 0x60 + 4 * i, 0xa56b1234 ^ (i * 0x11111111))
        self.uc.reg_write(UC_ARM_REG_CPSR, 0x13)
        self.uc.reg_write(UC_ARM_REG_SP, TOP); self.uc.reg_write(UC_ARM_REG_LR, RETURN)
        for i, reg in enumerate(REGS): self.uc.reg_write(reg, 0xaabb0000 + i)
        for reg, val in ((UC_ARM_REG_R4, 0x44444444), (UC_ARM_REG_R5, 0x55555555), (UC_ARM_REG_R6, 0x66666666)):
            self.uc.reg_write(reg, val)
        self.writes, self.mmio, self.calls = [], [], []
        self.stops, self.tick_result = {RETURN}, 0

    def put(self, address, val): self.uc.mem_write(address, packed(val))
    def word(self, address): return struct.unpack('<I', self.uc.mem_read(address, 4))[0]
    def args(self): return [self.uc.reg_read(r) for r in REGS]

    def code(self, uc, address, size, data):
        if address in self.stops:
            uc.emu_stop(); return
        if address in (TICK, SCHEDULE):
            self.calls.append(hex(address))
            if address == TICK: uc.reg_write(UC_ARM_REG_R0, u32(self.tick_result))
            uc.reg_write(UC_ARM_REG_PC, uc.reg_read(UC_ARM_REG_LR)); return
        if not any(a <= address < b for a, b in SCOPES):
            raise AssertionError(f'execution outside admitted slices: {address:#x}')
        self.visited.add(address)

    def memory(self, uc, access, address, size, value, data):
        if 0x01c20000 <= address < 0x01c21000:
            assert address in MMIO and size == 4, (hex(address), size)
            self.mmio.append(('write' if access == UC_MEM_WRITE else 'read', address,
                              u32(value) if access == UC_MEM_WRITE else self.word(address)))
        if access == UC_MEM_WRITE:
            if STACK <= address and address + size <= STACK + 0x1000: return
            assert (RAM <= address and address + size <= RAM + 0x1000) or address in MMIO
            self.writes.append((address, size, value & ((1 << (8 * size)) - 1)))

    def run(self, entry, args=(), stops=(RETURN,)):
        for r, val in zip(REGS, args): self.uc.reg_write(r, u32(val))
        self.stops = set(stops)
        self.uc.emu_start(entry, 0x10004000, count=1000)
        assert self.uc.reg_read(UC_ARM_REG_PC) in self.stops, 'instruction bound exceeded'
        assert self.uc.reg_read(UC_ARM_REG_SP) == TOP


def registration(m):
    count, results = 0, []
    inputs = list(itertools.product((0, 1, 7, 8, 0xffffffff), range(41), range(4), (0, 1)))
    inputs += [(1, irq, prio, 0) for irq in (0, 15, 16, 31, 32, 40) for prio in (4, 255)]
    for mode, irq, priority, flag in inputs:
        m.reset(flag)
        expected_ram = bytearray(m.uc.mem_read(RAM, 0x1000))
        handler = 0x10003400 + 8 * irq
        pr = INTC + 0x60 + 4 * (irq // 16)
        en = INTC + 0x20 + 4 * (irq // 32)
        shift = 2 * (irq % 16)
        priority_value = u32((m.word(pr) & ~(3 << shift)) | u32(priority << shift))
        enable_value = m.word(en) | (1 << (irq % 32))
        expected = []
        if flag == 0:
            expected += [(FLAG, 1, 1), (INTC + 4, 4, HANDLERS)]
            expected_ram[FLAG - RAM] = 1
        return_value = mode
        if mode < 8:
            slot = (ALTERNATE if mode == 0 else HANDLERS) + 4 * irq
            return_value = m.word(slot)
            expected.append((slot, 4, handler))
            expected_ram[slot - RAM:slot - RAM + 4] = packed(handler)
        expected += [(pr, 4, priority_value), (en, 4, enable_value)]
        m.run(REGISTER, (mode, irq, handler, priority))
        assert m.writes == expected, (mode, irq, priority, flag, m.writes, expected)
        assert m.uc.mem_read(RAM, 0x1000) == expected_ram
        assert m.uc.reg_read(UC_ARM_REG_R0) == return_value
        for reg, val in ((UC_ARM_REG_R4, 0x44444444), (UC_ARM_REG_R5, 0x55555555), (UC_ARM_REG_R6, 0x66666666)):
            assert m.uc.reg_read(reg) == val
        results.append([mode, irq, priority, flag, return_value, m.writes]); count += 1
    return count, sha(json.dumps(results).encode())


def dispatch(m):
    results = []
    for table, irq, thumb in itertools.product((HANDLERS, ALTERNATE), range(41), (0, 1)):
        m.reset()
        target = 0x10003000 + irq * 8
        m.put(INTC, table + 4 * irq)
        m.put(table + 4 * irq, target | thumb)
        m.run(DISPATCH, stops=(target,))
        assert m.uc.reg_read(UC_ARM_REG_CPSR) >> 5 & 1 == thumb
        assert m.mmio == [('read', INTC, table + 4 * irq)] and not m.writes
        results.append([table, irq, thumb, m.uc.reg_read(UC_ARM_REG_R0)])
    return len(results), sha(json.dumps(results).encode())


def timers(m):
    configure_results, start_results, status_results = [], [], []
    for ch, period, irq_flag, seed in itertools.product((0, 1, 2, 0x100, 0x101, 0x102),
            (0, 1, 1000, 10000, 0xffffffff, 0x20000000), (0, 1, 2, 0x100, 0x101), (0, 0xa5a5a5a5)):
        m.reset(); channel = ch & 255
        ctrl, interval = TIMER + 0x10 + 16 * channel, TIMER + 0x14 + 16 * channel
        m.put(ctrl, seed); m.put(TIMER, seed)
        expected = [(ctrl, 4, 0), (ctrl, 4, 0), (ctrl, 4, 0), (ctrl, 4, 4),
                    (ctrl, 4, 6), (interval, 4, u32(24 * period))]
        if irq_flag & 255 == 1: expected.append((TIMER, 4, seed | 1 << channel))
        m.run(CONFIGURE, (ch, period, irq_flag))
        assert m.writes == expected, (ch, period, irq_flag, seed, m.writes, expected)
        configure_results.append([ch, period, irq_flag, seed, m.writes])
    for ch, seed in itertools.product((0, 1, 2, 0x100, 0x101, 0x102), (0, 6, 0xffffffff, 0x12345678)):
        m.reset(); ctrl = TIMER + 0x10 + 16 * (ch & 255); m.put(ctrl, seed)
        m.run(START, (ch,))
        assert m.writes == [(ctrl, 4, seed | 1)]
        start_results.append([ch, seed, m.writes])
    for seed in (0, 1, 7, 0xffffffff):
        m.reset(); m.put(TIMER + 4, seed)
        m.run(0x8005bf54)
        assert m.writes == [(TIMER + 4, 4, seed | 1)]
        status_results.append([seed, m.writes])
    return {'configure_cases': len(configure_results), 'start_cases': len(start_results),
            'status_update_cases': len(status_results),
            'results_sha256': sha(json.dumps([configure_results, start_results, status_results]).encode())}


def irq_bridge(m):
    results = []
    for pending, tick_result in itertools.product((0, 1, 1 << 12, 1 << 13, (1 << 13) | 1, 0xffffffff), (0, 1, 0xffffffff)):
        m.reset(); m.put(INTC + 0x10, pending); m.tick_result = tick_result
        handler = 0x10003000; m.put(INTC, HANDLERS); m.put(HANDLERS, handler)
        if not pending & (1 << 13):
            # The real dispatcher executes; handler body remains a stop boundary.
            m.run(0x8000230c, stops=(handler,))
            assert not m.calls and m.uc.reg_read(UC_ARM_REG_LR) == 0x80002328
            assert not m.writes
        else:
            # Tick/scheduler bodies are explicit API stubs, not claimed executed.
            m.run(0x8000230c, stops=(0x80002364,))
            assert m.calls == ([hex(TICK), hex(SCHEDULE)] if tick_result else [hex(TICK)])
            assert m.writes == [(INTC + 0x10, 4, 0), (TIMER + 4, 4, 1)]
        results.append([pending, tick_result, m.calls, m.writes])
    return len(results), sha(json.dumps(results).encode())


def startup_slice(m, raw):
    m.reset()
    tick_handler = struct.unpack_from('<I', raw, 0x80061834 - BASE)[0]
    m.run(0x800617ec, stops=(0x80061818,))
    assert m.word(TIMER + 0x10) == 7 and m.word(TIMER + 0x14) == 24000
    assert m.word(TIMER) == 1 and m.word(HANDLERS + 4 * 13) == tick_handler == 0x8005bf54
    assert m.word(INTC + 0x20) == 0x01234567 | (1 << 13)
    assert m.word(INTC + 4) == HANDLERS
    return {'cases': 1, 'entry': '0x800617ec', 'stop': '0x80061818',
            'channel': 0, 'interval_ticks': 24000, 'control': 7, 'irq': 13,
            'handler': hex(tick_handler), 'writes': m.writes,
            'nominal_frequency_hz_if_24MHz_source': 1000,
            'limit': 'Stops before RTOS context restore; no timer progression/actual clock or task cadence simulated.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', action='append', required=True, metavar='VERSION=PATH')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(); versions = []
    for inp in args.input:
        version, path = inp.split('=', 1); raw = Path(path).read_bytes()
        assert sha(raw) == EXPECTED_INPUTS[version]
        m = Machine(raw)
        nreg, hreg = registration(m); ndispatch, hdispatch = dispatch(m)
        timer = timers(m); nbridge, hbridge = irq_bridge(m); startup = startup_slice(m, raw)
        labels = []
        for address, name in ((REGISTER, 'RE_INTCRegister'), (DISPATCH, 'RE_INTCVectorDispatch'),
                              (CONFIGURE, 'RE_TimerConfigure'), (START, 'RE_TimerEnable'),
                              (0x8005bf54, 'RE_Timer0StatusUpdate')):
            labels.append({'address': hex(address), 'name': name, 'confidence': 1.0,
                           'proof': 'bounded_original_ARM926_execution',
                           'evidence': 'evidence/2026-11-07-intc-timer-path.json',
                           'guard_bytes': 64, 'guard_sha256': sha(raw[address - BASE:address - BASE + 64])})
        windows = {}
        md = Cs(CS_ARCH_ARM, CS_MODE_ARM)
        for start, end in SCOPES:
            data = raw[start - BASE:end - BASE]
            windows[hex(start)] = {'end_exclusive': hex(end), 'sha256': sha(data),
                                  'assembly': [f'{i.address:08x} {i.mnemonic} {i.op_str}' for i in md.disasm(data, start)],
                                  'note': 'Registration window contains an inline jump table; not every word is an instruction.'}
        versions.append({'version': version, 'input_sha256': sha(raw), 'failed': 0,
                         'registration_cases': nreg, 'registration_results_sha256': hreg,
                         'dispatch_cases': ndispatch, 'dispatch_results_sha256': hdispatch,
                         'timer': timer, 'irq_bridge_cases': nbridge, 'irq_bridge_results_sha256': hbridge,
                         'startup': startup, 'approved_labels': labels, 'windows': windows,
                         'visited_instruction_count': len(m.visited)})
        print(version, nreg, 'registration;', ndispatch, 'dispatch;', timer, '; bridge', nbridge)
    if len(versions) == 2:
        for field in ('registration_results_sha256', 'dispatch_results_sha256', 'timer', 'irq_bridge_results_sha256', 'startup'):
            assert versions[0][field] == versions[1][field]
    report = {'schema': 'ys4470.intc-timer-path.v1', 'date': '2026-11-07', 'cpu': 'UC_CPU_ARM_926',
              'versions': versions, 'reference_sources': [
              'https://github.com/nminaylov/F1C100s_projects/tree/c11422e99c9f33e8419a5ac4dcab6684c8d38296/f1c100s/drivers',
              'https://github.com/mikljohansson/fnirsi-1013d-mcp/blob/fa8377b2b1d148f8596a8befe638df79062c2bd8/firmware/scope/interrupt.c',
              'https://github.com/minilogic/f1c_nonos/blob/73933dbb56d2cbdeb1f260a484bb7c525866616f/src/irq/main.c'],
              'limits': ['Inert MMIO RAM shadows, not live hardware or timer/INTC behavior models.',
                         'Tick/scheduler bodies are API stubs in IRQ bridge experiment; full exception context save/restore is excluded.',
                         'Valid IRQ0..40 and timer channels0..2 tested; unsafe out-of-range indices are not executed.',
                         'Mode0 alternate-table semantics remain unnamed; modes>=8 still update priority/enable without replacing a handler.',
                         'The nominal1kHz startup configuration does not prove UART sampling or audible latency.']}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()
