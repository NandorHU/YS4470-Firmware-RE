"""Emulate touch / release / re-touch with ProfileMachine; report sound-control ON/OFF and RESULT+0x50."""
import sys, json, struct, hashlib
from pathlib import Path
ROOT = Path.cwd()
import os
sys.path.insert(0, os.environ.get('YS4470_ARM_RUNTIME', str(Path(__file__).resolve().parents[5] / 'YS4470-EMULATOR-CLAUDE-20261120/runtime/windows')))
sys.path[:0] = [str(ROOT/'contributions/COORD-ADC-CADENCE'), str(ROOT/'tools')]
import trace_profiles as trace
img = Path(sys.argv[1]).read_bytes()
factory = (ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes()
init = trace.restore_globals(factory)
trace.NAMES = ['Base','Direct','Auto','Ready','ownprotocol']
WAVE = [(0,100,6000),(100,160,0),(160,175,6000),(175,320,0),(320,400,6000)]   # OPEN / SHORT segments
class M(trace.ProfileMachine):
    def raw(self, t):
        return next(v for a,b,v in WAVE if a <= t < b)
    def code(self, u, a, size, _):
        if a == 0x800060d0:
            self.event('countdown', value=self.rd(trace.SH + 0x50))
        super().code(u, a, size, _)
out = {}
for profile in (0, 1, 4):
    trace.E2_SHA = hashlib.sha256(img).hexdigest()
    m = M(img, profile, 1, 'custom', init=init)
    r = m.run(400)
    snd = [(e['t'], [hex(x) for x in e['args']]) for e in r['events'] if e['kind']=='sound_control']
    cd = [(e['t'], e['value']) for e in r['events'] if e['kind']=='countdown']
    acc = [(e['t'], e['raw']) for e in r['events'] if e['kind']=='accepted']
    first_short2 = next(t for t,v in acc if t >= 175 and v == 0)
    out[trace.NAMES[profile]] = dict(sound=snd, first_short_accept_after_retouch=first_short2,
        accepted_count=len(acc), countdown=cd, renders=[e['t'] for e in r['events'] if e['kind']=='renderer'])
print(json.dumps(out, indent=1))
