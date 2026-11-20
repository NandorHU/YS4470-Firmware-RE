"""Bounded ARM926 ownprotocol checks. UART/conversion timing is a synthetic model."""
import json
from pathlib import Path
import struct
import sys
from build_ownprotocol import ROOT, HERE, BASE, BITMAP, BITMAP_END, sha, build, reproduce
sys.path.insert(0,str(ROOT/'contributions/COORD-DIODE-VOLUME'))
import test_diode_volume as volume_test
import trace_profiles as trace


def profile_machine(image, init, profile=4, scenario='stable-low', highspeed=1, **kw):
    # Explicitly bind the existing harness to this generated candidate. Keep all
    # ARM write, UART payload, stack and instruction-budget checks enabled.
    trace.E2_SHA=sha(image)
    trace.NAMES=['Base','Direct','Auto','Ready','ownprotocol']
    return trace.ProfileMachine(image,profile,highspeed,scenario,init=init,**kw)


def check_selection(image, receipt):
    t=volume_test
    app=t.Replay(image,receipt['overlay_bytes']);app.create()
    button=app.get(t.PROFILE+12)
    # GUI harness models original registration leaves during construction. Replay
    # the captured registration outside init so the real LVGL descriptor is built.
    callback, mask, user_data=app.bindings[button][0]
    app.call(t.EVENT_REGISTER,button,callback,mask,user_data)
    labels=[]
    for expected in [1,2,3,4,0,1,2,3,4,0]:
        # Actual indirect LVGL event dispatch, not a direct callback invocation.
        app.call(t.EVENT,button,14,0)
        assert app.u.mem_read(t.PROFILE+1,1)==bytes([expected])
        text=app.objects[app.get(t.PROFILE+8)]['text']
        assert text==trace.NAMES[expected], (expected,text)
        assert app.objects[button]['size']==[180 if expected==4 else 112,30]
        labels.append(text)
    # Real factory glyph metrics plus LVGL letter spacing fit the enlarged button.
    width=0
    label='ownprotocol'
    for k,ch in enumerate(label):
        assert app.call(0x8002c9c0,0x80080888,0x81110000,ord(ch),ord(label[k+1]) if k+1<len(label) else 0)==1
        width+=struct.unpack('<H',app.u.mem_read(0x81110004,2))[0]
    width+=2*(len(label)-1)
    assert width+20<=180
    return dict(event_cycles=labels,glyph_and_spacing_px=width,own_button_px=180)


def main():
    original=(ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes()
    e2=reproduce(original)[0]['profiles-E2']; image,receipt=build(e2)
    init=trace.restore_globals(original)
    report=dict(application_sha256=sha(image), physical_device_operations=0,
                physical_time_units_established=False)
    report['controls']=volume_test.check_controls(e2,image,receipt)
    report['font']=volume_test.check_font(e2,image,receipt)
    report['existing_profiles']=volume_test.check_profiles(e2,image,original,ROOT)
    trace.NAMES=['Base','Direct','Auto','Ready','ownprotocol']
    report['selection']=check_selection(image,receipt)
    rows=[]
    for scenario in ('stable-low','open-contact','contact-open','short-contact','late','missing','wrong-header','truncated'):
        m=profile_machine(image,init,scenario=scenario,reply_delay=35 if scenario=='late' else 1)
        row=m.run(300)
        assert row['queue_max']<=1
        assert not any(x['kind']=='enqueue' and x['phase']=='service' for x in row['events']), 'ownprotocol must not enqueue a synthetic request'
        if scenario in ('missing','wrong-header','truncated'):
            assert row['counts']['accepted']==0
            assert not any(x['kind']=='sound_control' and x['args'][1]==1321 and x['args'][2] for x in row['events'])
            assert 1<len(m.tx)<=60, (scenario,len(m.tx))
            assert all(b-a>=5 for a,b in zip(m.tx,m.tx[1:])), (scenario,m.tx)
        else:
            assert row['counts']['accepted']>0
        # Every new request follows acceptance or a timeout/rejection of the old
        # transaction. No overlapping requests, including late/malformed frames.
        outstanding=False
        for ev in row['events']:
            if ev['kind']=='request':
                assert not outstanding,(scenario,ev)
                outstanding=True
            if ev['kind']=='accepted' or (ev['kind']=='state_write' and ev['new']==6):
                outstanding=False
        rows.append({k:v for k,v in row.items() if k not in ('events',)})
    report['own_scenarios']=rows
    # Highspeed is independent of the reply-driven profile; a slower/phased GUI
    # must not control its UART cadence or accepted-result sound timing.
    schedules=[]
    for hs,period,phase in ((0,25,0),(1,25,0),(0,71,13),(1,71,13)):
        m=profile_machine(image,init,scenario='open-contact',highspeed=hs,gui_period=period,gui_phase=phase)
        row=m.run(250)
        schedules.append(dict(highspeed=hs,gui_period=period,gui_phase=phase,requests=m.tx,
            accepted=[e['t']for e in row['events']if e['kind']=='accepted'],
            sounds=[e['t']for e in row['events']if e['kind']=='sound_control'and e['args'][1]==1321 and e['args'][2]]))
    assert all(s['requests']==schedules[0]['requests'] and s['accepted']==schedules[0]['accepted'] and s['sounds']==schedules[0]['sounds'] for s in schedules)
    report['independent_gui_schedules']=[{k:v for k,v in s.items()if k not in ('requests','accepted')}for s in schedules]
    # Resume valid replies after a period of total silence without resetting FSM.
    class Recovery(trace.ProfileMachine):
        def code(self,u,pc,size,opaque):
            if pc==0x80005e84 and self.now>=150:
                self.scenario='stable-low'
            super().code(u,pc,size,opaque)
    trace.E2_SHA=sha(image)
    recovery=Recovery(image,4,1,'missing',init=init)
    recovered=recovery.run(300)
    accepted=[e for e in recovered['events']if e['kind']=='accepted']
    assert accepted and accepted[0]['t']>=150
    report['missing_then_valid_recovery']=dict(first_accepted=accepted[0]['t'],accepted=len(accepted))
    # Compare sound/render/request events with Ready on the same supplied waveform.
    comparison={}
    for profile in (3,4):
        m=profile_machine(image,init,profile=profile,scenario='open-contact')
        row=m.run(250)
        comparison[trace.NAMES[profile]]=dict(counts=row['counts'],first_requests=m.tx[:8],
            first_low_accepted=next(e['t']for e in row['events']if e['kind']=='accepted'and e['raw']==50),
            first_low_sound=next(e['t']for e in row['events']if e['kind']=='sound_control'and e['args'][1]==1321 and e['args'][2]))
    assert comparison['ownprotocol']['counts']['request']>comparison['Ready']['counts']['request']
    report['synthetic_comparison']=comparison
    # Apply a requested switch only when idle, and do not rearm the old profile.
    m=profile_machine(image,init)
    row=m.run(120,switch=(3,0))
    changes=[e for e in row['events']if e['kind']=='active_profile']
    assert changes and changes[0]['new']==0 and changes[0]['busy']==0
    assert changes[0]['t']>3
    for requested in range(5):
        m=profile_machine(image,init)
        m.u.mem_write(trace.PROFILE+1,bytes([requested]));m.u.mem_write(trace.FSM+0x34,b'\1')
        m.call(trace.SYMBOLS['apply'],'switch_busy')
        assert m.byte(trace.PROFILE)==4
        m.u.mem_write(trace.FSM+0x34,b'\0');m.call(trace.SYMBOLS['apply'],'switch_idle')
        assert m.byte(trace.PROFILE)==requested
    report['deferred_switches']=5
    # Owned protocol cannot start across pending control traffic, wrong function,
    # busy transaction, pending profile switch, or an unrelated measurement mode.
    blocked=[]
    for addr,value in [(trace.CTRL,1),(trace.CTRL+1,2),(trace.FSM+0x34,1),(trace.PROFILE+1,0),(trace.UI,4),(trace.UI+7,13),(trace.CTRL+8,13)]:
        m=profile_machine(image,init)
        m.u.mem_write(addr,bytes([value]))
        # Exercise the guarded auto entry without unwinding the service stack.
        m.call(0x8001110c,'auto_guard')
        assert not m.tx,(hex(addr),value,m.tx)
        blocked.append(hex(addr))
    m=profile_machine(image,init);m.wr(trace.CTRL+8,0x10e)
    m.call(0x8001110c,'full_width_mode_guard');assert not m.tx
    report['blocked_rearm_conditions']=blocked+['CTRL+8 full-width alias 0x10e']
    # Malformed LZ back-references fail before any destination byte is written.
    malformed=[]
    for payload in (bytes([128,0,0]),bytes([128,1,0])):
        app=volume_test.Replay(image,receipt['overlay_bytes'])
        app.u.mem_write(BITMAP+receipt['overlay_bytes'],payload)
        assert app.call(BITMAP+12,volume_test.FONT,65)==0
        assert not app.bitmap_writes and len(app.frees)==1
        malformed.append(payload.hex())
    report['invalid_font_backreferences_rejected']=malformed
    # Failed inputs cannot silently produce another image.
    bad=bytearray(e2);bad[0x1234]^=1
    try:build(bytes(bad))
    except ValueError:pass
    else:raise AssertionError('Corrupt base accepted')
    assert build(e2)==(image,receipt)
    report['reproducible_and_corrupt_base_rejected']=True
    target=ROOT/'out/ownprotocol'
    target.mkdir(parents=True,exist_ok=True)
    (target/'ys4470-e2-ownprotocol-OFFLINE.bin').write_bytes(image)
    (target/'build-receipt.json').write_bytes((json.dumps(receipt,indent=2)+'\n').encode('utf-8'))
    (HERE/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PASS: ownprotocol selection, ARM scheduler, errors, guards, volume/font and existing profiles')
    print(json.dumps(comparison,indent=2))
if __name__=='__main__':main()
