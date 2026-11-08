"""Reproducible profile validation; real ARM code, explicitly modeled I/O leaves."""
import hashlib,json,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from unicorn.arm_const import UC_ARM_REG_PC
from reproduce_profiles import reproduce
from trace_profiles import *

def first(row,kind,predicate=lambda e:True):return next((e['t']for e in row['events']if e['kind']==kind and predicate(e)),None)
def compact(row):
    return {k:v for k,v in row.items()if k!='events'}|{
      'first_low_accept':first(row,'accepted',lambda e:e['raw']==50),
      'first_sound_on':first(row,'sound_control',lambda e:e['args'][2]!=0),
      'first_sound_off':first(row,'sound_control',lambda e:e['args'][2]==0),
      'first_low_render':first(row,'renderer',lambda e:e['raw']==50)}
def collect():
    original=(ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes();assert sha(original)==V38_SHA
    images,replay=reproduce(original);image=images['profiles-E2'];init=restore_globals(original)
    scenarios=['stable-low','open-contact','contact-open','short-contact','late','wrong-header','truncated','missing']
    rows=[];coverage={};trace_records=[];checks=0
    for hs in (0,1):
      for scenario in scenarios:
        group=[]
        for profile in range(4):
            machine=ProfileMachine(image,profile,hs,scenario,reply_delay=35 if scenario=='late'else 1,init=init)
            row=machine.run();assert row['active']==row['requested']==profile and row['highspeed']==hs
            assert row['counts']['sleep_calls']==250;checks+=2
            if scenario in ('wrong-header','truncated','missing'):
                assert row['counts']['accepted']==0 and row['counts']['sound_control']==0;checks+=1
            if hs==1 and profile and scenario in ('stable-low','open-contact','contact-open','short-contact','late'):
                assert first(row,'sound_control',lambda e:e['args'][2]!=0)==first(row,'accepted',lambda e:e['raw']==50);checks+=1
            group.append(row);rows.append(compact(row));coverage.update(machine.coverage)
            # Compact event arrays retain all event boundaries, not repeated idle
            # instruction hooks. Each scenario/profile/HS has its own short line.
            trace_records.append(row)
        assert [e['t']for e in group[0]['events']if e['kind']=='request']==[e['t']for e in group[1]['events']if e['kind']=='request'];checks+=1
    # Selection changes never alter ACTIVE mid-transaction. Test all pairs,
    # at four deterministic locations, not only a final matching menu label.
    switches=[]
    for start in range(4):
      for target in range(4):
       for when in (2,5,7,26):
        machine=ProfileMachine(image,start,1,'stable-low',init=init)
        row=machine.run(80,switch=(when,target));assert row['active']==row['requested']==target
        for e in row['events']:
            if e['kind']=='active_profile':assert e['busy']==0
        checks+=1;switches.append(dict(start=start,target=target,when=when,final_active=row['active'],
            changes=[e for e in row['events']if e['kind']in('requested_profile','active_profile')]))
        coverage.update(machine.coverage)
    # Independent, public-input replay of the existing offline reply-audio parent.
    # This verifies its speed mechanism without changing polling or requiring E2.
    candidate=[]
    for name in ('threshold-1.1','reply-audio'):
      for s in scenarios:
        m=ProfileMachine(images[name],0,1,s,init=init,reply_delay=35 if s=='late'else 1)
        r=m.run();candidate.append(dict(build=name,sha256=sha(images[name]),**compact(r)))
        if s in ('wrong-header','truncated','missing'):assert r['counts']['sound_control']==0;checks+=1
    for s in scenarios:
        old,new=[r for r in candidate if r['scenario']==s]
        assert old['counts']['request']==new['counts']['request'] and old['counts']['accepted']==new['counts']['accepted'];checks+=1
        if s in scenarios[:5]:assert new['first_sound_on']==new['first_low_accept']<=old['first_sound_on'];checks+=1
    # Recheck the six supplied packet identities and every instruction, without
    # importing legacy test modules or repeating the old experiment matrices.
    packet_index=json.loads((ROOT/'contributions/COORD-FUNCTION-PACKETS/packet-index.json').read_text())
    guards=0
    for p in packet_index['packets']:
        raw=(ROOT/p['path']).read_bytes();assert sha(raw)==p['sha256'];packet=json.loads(raw)
        binary=(ROOT/packet['binary']['path']).read_bytes();assert sha(binary)==packet['binary']['sha256']
        for ins in packet['assembly']:
            address=int(ins['address'],16);b=bytes.fromhex(ins['bytes']);assert binary[address-BASE:address-BASE+len(b)]==b;guards+=1
    # One idle service iteration per original proves only the FSM-call / sleep
    # placement, with empty queue, inactive FSM and explicit RTOS models.
    original_service=[]
    for version in ('V3.6','V3.8'):
        raw=(ROOT/f'original-firmware/{version}/f1c100s.bin').read_bytes()
        m=ProfileMachine(raw,0,1,'missing',init=init);m.call(0x80005b6c,'service')
        assert [e['kind']for e in m.events]==['fsm','task_sleep'];assert m.sleep_count==1;checks+=1
        assert raw[0x80005b6c-BASE:0x80005d18-BASE]==original[0x80005b6c-BASE:0x80005d18-BASE]
        original_service.append(dict(version=version,sha256=sha(raw),events=m.events,instructions=m.steps,
            executed_instructions=sorted(m.coverage.values(),key=lambda x:int(x['address'],16))))
    # Every recorded instruction byte must still belong to the pinned E2 image.
    # Coverage includes mutable data only as data, never as instruction bytes.
    for c in coverage.values():
        a=int(c['address'],16);assert image[a-BASE:a-BASE+c['size']].hex()==c['bytes']
    report=dict(schema='ys4470.profile-validation.v1',image_sha256=sha(image),replay=replay,
        runner_sha256=sha((HERE/'trace_profiles.py').read_bytes()),validator_sha256=sha(Path(__file__).read_bytes()),
        restored_globals_sha256=sha(init),profile_cases=len(rows),transition_cases=len(switches),candidate_cases=len(candidate),
        assertion_groups=checks,packet_instruction_byte_guards=guards,packet_count=len(packet_index['packets']),
        e2_observed_instruction_addresses=len(coverage),profile_rows=rows,switch_rows=switches,candidate_rows=candidate,
        original_service=original_service,
        physical_device_operations=0,physical_time_units_established=False,
        limits=['Synthetic RTOS counter/queue/critical/sleep, service+GUI task order, UART TX/responder, formatter/renderer/PWM endpoints.',
        'The original tick/critical execution is reused from COORD-FSM-TIMEOUT, not rerun by this profile harness.',
        'UART answers snapshot the common input waveform at modeled response start. Analog conversion and command restart behavior are unknown.',
        'Late frames carry only a host request label, not a firmware transaction identifier; attribution to current hardware conversion is not proven.',
        'Renderer entry is an observation, not LCD completion. PWM control is an observation, not acoustic output.',
        'Code-hook coverage includes modeled-leaf entry addresses whose original instructions are skipped; it is not an executed-instruction percentage.',
        'The replay reproduces recorded edits and hashes, not historical source generators or physical E2 identity.',
        'This does not reproduce the reported Base physical advantage or justify an ADC/timeout change.'])
    return report,trace_records,coverage

def main():
    report,traces,coverage=collect();jsonwrite(HERE/'profile-validation.json',report)
    out=HERE/'traces';out.mkdir(exist_ok=True)
    for hs in (0,1):
        # One JSON object per line; deterministic without millions of indent bytes.
        (out/f'highspeed-{hs}.jsonl').write_text(''.join(json.dumps(r,separators=(',',':'))+'\n'for r in traces if r['highspeed']==hs),encoding='utf8')
    jsonwrite(HERE/'observed-e2-instructions.json',sorted(coverage.values(),key=lambda x:int(x['address'],16)))
    print(json.dumps({k:report[k]for k in('profile_cases','transition_cases','candidate_cases','assertion_groups','packet_instruction_byte_guards','e2_observed_instruction_addresses')},indent=2))
if __name__=='__main__':main()
