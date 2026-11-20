"""Diode-mode sweep on the real image: OPEN until t=50, then a constant raw value. Records the float handed to the
E2 threshold routine (r5 at 0x800602b4), its branch, sound-gate calls and the renderer's numeric float. No device I/O."""
import sys, json, struct, hashlib
from pathlib import Path
ROOT = Path.cwd()
import os
sys.path.insert(0, os.environ.get('YS4470_ARM_RUNTIME', str(Path(__file__).resolve().parents[5] / 'YS4470-EMULATOR-CLAUDE-20261120/runtime/windows')))
sys.path[:0] = [str(ROOT/'contributions/COORD-ADC-CADENCE'), str(ROOT/'tools')]
import trace_profiles as trace
from unicorn.arm_const import UC_ARM_REG_R5, UC_ARM_REG_R0, UC_ARM_REG_R1
img = Path(sys.argv[1]).read_bytes(); profile = int(sys.argv[2])
init = trace.restore_globals((ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes())
trace.NAMES = ['Base','Direct','Auto','Ready','ownprotocol']
f = lambda bits: struct.unpack('<f', struct.pack('<I', bits & 0xffffffff))[0]
class M(trace.ProfileMachine):
    def raw(self, t): return 6000 if t < 50 else self.level
    def code(self, u, a, size, _):
        if a == 0x800602b4: self.event('thr', v=round(f(u.reg_read(UC_ARM_REG_R5)), 6))
        if a in (0x800602f0, 0x800602f8, 0x80060304, 0x800602d4): self.event('branch', at=hex(a))
        if a == 0x80006e4c: self.event('gate', r0=u.reg_read(UC_ARM_REG_R0), r1=u.reg_read(UC_ARM_REG_R1))
        super().code(u, a, size, _)
rows = []
for level in (0, 50, 99, 100, 101, 400, 699, 700, 701, 2000, 5000, 5001):
    trace.E2_SHA = hashlib.sha256(img).hexdigest()
    m = M(img, profile, 1, 'custom', init=init); m.level = level
    r = m.run(160); ev = r['events']
    after = [e for e in ev if e['t'] >= 50]
    acc = [e['t'] for e in after if e['kind'] == 'accepted']
    thr = [(e['t'], e['v']) for e in after if e['kind'] == 'thr']
    gates = [(e['t'], e['r0'], e['r1']) for e in after if e['kind'] == 'gate']
    nums = [(e['t'], round(f(int(e['float_bits'], 16)), 4)) for e in after if e['kind'] == 'numeric']
    rows.append(dict(raw=level, first_accept=acc[:1], threshold_inputs=thr[:2],
                     branches=sorted({e['at'] for e in after if e['kind'] == 'branch'}),
                     gates=gates[:4], renders=nums[:2]))
print(json.dumps(rows))
