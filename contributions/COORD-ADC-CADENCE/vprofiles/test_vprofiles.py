"""Bounded ARM926 checks for Beta Diode profiles Base, v1..v4. UART/conversion timing is a synthetic model.
Run from the repository root with unicorn/capstone/keystone importable. No device I/O."""
import hashlib, json, struct, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path[:0] = [str(HERE), str(ROOT / 'contributions/COORD-ADC-CADENCE'), str(ROOT / 'contributions/COORD-DIODE-VOLUME'),
                str(ROOT / 'contributions/COORD-ADC-CADENCE/ownprotocol'), str(ROOT / 'contributions/COORD-ADC-CADENCE/diodefixed')]
import build_vprofiles as bv
import build_diodefixed
import trace_profiles as trace
import test_diode_volume as volume_test
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1

NAMES = ['Base', 'v1', 'v2', 'v3', 'v4']
BETA4_SHA = build_diodefixed.OUT_SHA
def sha(b): return hashlib.sha256(b).hexdigest()


class VM(trace.ProfileMachine):
    """ProfileMachine that also answers configuration frames (echo of the first byte, as the existing
    dispatcher harnesses do), records every UART payload, and admits writes to the overlay state words."""
    state = None
    wave = None
    def __init__(self, image, profile, *a, **k):
        trace.E2_SHA = sha(image)
        super().__init__(image, profile, *a, **k)
        self.wire = []
    def raw(self, t):
        return self.wave(t) if self.wave else super().raw(t)
    def code(self, u, a, size, _):
        if a == 0x80005E84:
            msg = bytes(u.mem_read(u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)))
            self.wire.append((self.now, msg.hex()))
            if msg != b'\x60':
                self.event('setup', payload=msg.hex())
                self.pending.append((self.now + self.reply_delay, self.sequence, msg[0], 0))
                self.sequence += 1; self.pending.sort(); self.ret(); return
        super().code(u, a, size, _)
    def memory(self, u, access, a, size, v, _):
        if self.state and self.state[0] <= a < self.state[1]:
            return
        super().memory(u, access, a, size, v, _)
    def setup_payloads(self):
        return [w for _, w in self.wire if w != '60']
    def tone_on(self):
        return [e['t'] for e in self.events if e['kind'] == 'sound_control' and e['args'][2]]


def timeline(row):
    keep = ('request', 'accepted', 'sound_control', 'renderer', 'setup')
    return [(e['t'], e['kind'], e.get('raw'), tuple(e.get('args', ())), e.get('payload')) for e in row['events']
            if e['kind'] in keep]


def machine(image, receipt, init, profile, **kw):
    VM.state = (int(receipt['symbols']['own_hist'], 16), int(receipt['symbols']['own_state'], 16) + 4)
    wave = kw.pop('wave', None)
    m = VM(image, profile, kw.pop('highspeed', 1), kw.pop('scenario', 'stable-low'), init=init, **kw)
    m.wave = wave
    return m


def no_overlap(row):
    outstanding = False
    for e in row['events']:
        if e['kind'] == 'request':
            assert not outstanding, e; outstanding = True
        if e['kind'] in ('accepted', 'parser') or (e['kind'] == 'state_write' and e['new'] == 6):
            outstanding = False


def check_selection(image, receipt):
    t = volume_test
    app = t.Replay(image, receipt['overlay_bytes']); app.create()
    button = app.get(t.PROFILE + 12)
    callback, mask, user_data = app.bindings[button][0]
    app.call(t.EVENT_REGISTER, button, callback, mask, user_data)
    labels = []
    assert app.u.mem_read(t.PROFILE, 2) == bytes([2, 2]), 'boot profile must be v2'
    for expected in [4, 2, 4, 2, 4, 2]:
        app.call(t.EVENT, button, 14, 0)
        assert app.u.mem_read(t.PROFILE + 1, 1) == bytes([expected])
        text = app.objects[app.get(t.PROFILE + 8)]['text']
        assert text == NAMES[expected], (expected, text)
        assert app.objects[button]['size'] == [112, 30]
        labels.append(text)
    # The second (0x800609e0) toggle callback also only alternates v2 <-> v4.
    for start, expected in ((2, 4), (4, 2), (0, 2), (1, 2), (3, 2)):
        app.u.mem_write(t.PROFILE + 1, bytes([start]))
        app.call(0x800609e0)
        assert app.u.mem_read(t.PROFILE + 1, 1) == bytes([expected]), (start, expected)
    for label in NAMES[1:]:
        for k, ch in enumerate(label):
            assert app.call(0x8002c9c0, 0x80080888, 0x81110000, ord(ch), ord(label[k + 1]) if k + 1 < len(label) else 0) == 1
    return labels


def exp_wave(start, target, q, t0=200, period=10, hold=6000):
    def f(t):
        if t < t0: return hold
        k = (t - t0) // period
        return int(round(target + (start - target) * q ** k))
    return f


def lin_wave(start, target, step, t0=200, period=10, hold=6000):
    def f(t):
        if t < t0: return hold
        return max(target, start - step * ((t - t0) // period))
    return f


def main():
    original = (ROOT / 'original-firmware/V3.8/f1c100s.bin').read_bytes()
    e2 = bv.reproduce(original)[0]['profiles-E2']
    image, receipt = bv.build(e2)
    beta4, _ = bv.own.build(e2); beta4, _ = build_diodefixed.apply(beta4)
    assert sha(beta4) == BETA4_SHA
    init = trace.restore_globals(original)
    trace.NAMES = NAMES
    report = dict(application_sha256=sha(image), physical_device_operations=0, physical_time_units_established=False)

    # Build properties
    assert bv.build(e2) == (image, receipt)
    bad = bytearray(e2); bad[0x1234] ^= 1
    try: bv.build(bytes(bad))
    except ValueError: pass
    else: raise AssertionError('corrupt base accepted')
    diff = [bv.BASE + i for i in range(len(image)) if image[i] != beta4[i]]
    report['bytes_differing_from_beta4'] = len(diff)
    report['controls'] = volume_test.check_controls(e2, image, receipt)
    report['font'] = volume_test.check_font(e2, image, receipt)
    report['selection'] = check_selection(image, receipt)

    # Base: identical to the E2 baseline (and to beta.4 profile 0)
    base_rows = []
    for scenario in ('stable-low', 'contact-open', 'open-contact', 'short-contact'):
        rows = []
        for img in (e2, beta4, image):
            m = machine(img, receipt, init, 0, scenario=scenario); rows.append(timeline(m.run(185)))
        assert rows[1] == rows[2], scenario
        # E2 differs only by the volume-controlled tone gain (same rule as test_diode_volume.check_profiles).
        mask = lambda row: [(t, k, r, (a[0], a[1], None, a[3]) if k == 'sound_control' and a[2] else a, pl) for t, k, r, a, pl in row]
        assert mask(rows[0]) == mask(rows[2]), scenario
        base_rows.append(scenario)
    report['base_identical_to_e2_and_beta4'] = base_rows

    # v1 == beta.4 ownprotocol (profile 4), v3 == v1 on step waveforms (OL -> value has no valid history)
    scen = ('stable-low', 'open-contact', 'contact-open', 'short-contact', 'late', 'missing', 'wrong-header', 'truncated')
    for scenario in scen:
        kw = dict(scenario=scenario, reply_delay=35 if scenario == 'late' else 1)
        b4 = machine(beta4, receipt, init, 4, **kw); rb = b4.run(300)
        v1 = machine(image, receipt, init, 1, **kw); r1 = v1.run(300)
        v3 = machine(image, receipt, init, 3, **kw); r3 = v3.run(300)
        assert timeline(rb) == timeline(r1) == timeline(r3), scenario
        assert not v1.setup_payloads() and r1['queue_max'] <= 1
        no_overlap(r1)
    report['v1_v3_identical_to_beta4_ownprotocol'] = list(scen)

    # v2/v4: diode configuration with 68 0a is sent first, then the same polling as v1
    cfg = {}
    for p in (2, 4):
        m = machine(image, receipt, init, p, scenario='open-contact'); r = m.run(300)
        assert m.setup_payloads() == ['580a', '680a', '5900'], m.setup_payloads()
        assert m.rd(trace.CTRL + 8) == 14 and r['counts']['accepted'] > 0
        last_setup = max(t for t, w in m.wire if w != '60')
        disc = [e['discard_counter'] for e in r['events'] if e['kind'] == 'parser' and e['t'] > last_setup][:3]
        assert disc == [2, 1, 0], disc
        no_overlap(r)
        assert m.tone_on(), 'no tone after short'
        cfg[NAMES[p]] = dict(setup=m.setup_payloads(), setup_times=[t for t, w in m.wire if w != '60'],
                             accepted=r['counts']['accepted'], first_tone=m.tone_on()[0])
    report['v2_v4_configuration'] = cfg

    # Profile switches inside diode mode re-send the configuration only when the 68-state changes
    switches = {}
    for start, target, expect in ((1, 2, ['580a', '680a', '5900']), (2, 1, ['580a', '5900']),
                                  (2, 0, ['580a', '5900']), (4, 3, ['580a', '5900']),
                                  (1, 3, []), (3, 4, ['580a', '680a', '5900']), (0, 1, [])):
        m = machine(image, receipt, init, start, scenario='stable-low')
        r = m.run(400, switch=(200, target))
        after = [w for t, w in m.wire if t >= 200 and w != '60']
        assert after == expect, (start, target, after)
        assert m.byte(trace.PROFILE) == target and m.rd(trace.CTRL + 8) == 14
        no_overlap(r)
        switches[f'{NAMES[start]}->{NAMES[target]}'] = after
    report['profile_switch_reconfiguration'] = switches

    # Early short tone (v3/v4) on decaying readings; conversions change every 10 model units
    waves = {
        'short_exp_q0.5': exp_wave(2000, 0, 0.5), 'short_exp_q0.7': exp_wave(2000, 0, 0.7),
        'short_linear_400': lin_wave(2000, 0, 400),
        'diode_exp_600': exp_wave(2000, 600, 0.5), 'diode_linear_600': lin_wave(2000, 600, 400),
        'led_exp_1800': exp_wave(2200, 1800, 0.5), 'schottky_exp_250': exp_wave(2000, 250, 0.5),
    }
    early = {}
    for name, wave in waves.items():
        res = {}
        for p in (1, 2, 3, 4):
            m = machine(image, receipt, init, p, wave=wave); r = m.run(420)
            res[NAMES[p]] = dict(tone_on=m.tone_on(),
                                 offs=[e['t'] for e in r['events'] if e['kind'] == 'sound_control' and not e['args'][2]])
            no_overlap(r)
        v1, v2, v3, v4 = res['v1'], res['v2'], res['v3'], res['v4']
        def settled_off(x):  # a tone, if any, has been switched off again by the end
            return not x['tone_on'] or (x['offs'] and x['offs'][-1] > x['tone_on'][-1])
        if name.startswith('short'):
            assert v3['tone_on'][0] < v1['tone_on'][0] and v4['tone_on'][0] < v2['tone_on'][0], (name, res)
            assert not v3['offs'] and not v4['offs'], (name, res)          # continuous once started
        else:
            assert all(settled_off(x) for x in res.values()), (name, res)  # no lasting tone for junctions/LED
        if name.startswith('led'):
            assert not v1['tone_on'] and not v2['tone_on'] and v3['tone_on'] and v4['tone_on'], (name, res)
        if name.startswith(('diode', 'schottky')):
            assert v3['tone_on'][0] <= v1['tone_on'][0] and v4['tone_on'][0] <= v2['tone_on'][0], (name, res)
        early[name] = res
    report['early_tone'] = early

    # Owned polling still refuses to start across pending control, busy FSM, pending switch, other modes.
    blocked = []
    for p in (1, 2, 3, 4):
        for addr, value in [(trace.CTRL, 1), (trace.CTRL + 1, 2), (trace.FSM + 0x34, 1), (trace.PROFILE + 1, 0),
                            (trace.UI, 4), (trace.UI + 7, 13), (trace.CTRL + 8, 13)]:
            m = machine(image, receipt, init, p)
            m.u.mem_write(addr, bytes([value]))
            m.call(0x8001110c, 'auto_guard')
            assert not m.tx and not m.queue, (p, hex(addr), value)
            blocked.append(f'{NAMES[p]}:{hex(addr)}')
        m = machine(image, receipt, init, p); m.wr(trace.CTRL + 8, 0x10e)
        m.call(0x8001110c, 'full_width_mode_guard'); assert not m.tx and not m.queue
    report['blocked_rearm_conditions'] = len(blocked) + 4

    out = ROOT / 'out/vprofiles'; out.mkdir(parents=True, exist_ok=True)
    (out / 'ys4470-e2-vprofiles-OFFLINE.bin').write_bytes(image)
    (out / 'build-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    (HERE / 'validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print('PASS: v2/v4-only selection and boot default, Base==E2, v1==beta.4, 68 0a configuration, switches, early tone, guards')
    print(json.dumps({k: report[k] for k in ('application_sha256', 'v2_v4_configuration', 'profile_switch_reconfiguration')}, indent=1))
    print(json.dumps(report['early_tone'], indent=0))


if __name__ == '__main__':
    main()
