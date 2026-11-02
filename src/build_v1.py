"""Build 1.0 candidates from the exact physically validated Beta3 backup."""
from pathlib import Path
import hashlib,struct,json,sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'patch-candidates'))
from build_timed_candidate import branch,CREATE,STOP,BASE
sha=lambda b:hashlib.sha256(b).hexdigest()
reference=(HERE.parent/'diode-display-beta3/run-20261102-181738-665/full-after.bin').read_bytes()
assert sha(reference)=='2ce9c1693a9726a2fe042620debd7705e77cfec58d98e8729bb6ec1ade4a9d0f'
main=bytearray(reference[0x50000:0x50000+5943296]);edits=[]
def patch(a,new,expected=None):
    off=a-BASE;old=bytes(main[off:off+len(new)])
    if expected is not None:assert old==expected,(hex(a),old.hex())
    main[off:off+len(new)]=new
    edits.append(dict(address=hex(a),offset=off,old=old.hex(),new=new.hex()))
def words(a,w,expected=None):patch(a,struct.pack('<%dI'%len(w),*w),expected)
patch(0x80051978,b'highspeedv2\0',b'Diag Beta\0\0\0')
assert len(main)==5943296
baseline=bytes(main)
# Refresh a finite watchdog on each valid diode result. No timer allocation,
# sleeping, extra UART command or unconditional PWM restart on repeated results.
refresh=[0xe92d4002,0xe5971050,0xe3510000,0x03a00000,0x05cb000a,0xe3510003,0xc3a0100d,0xc5871050,0xe5db000a,0xe8bd8002]
post=CREATE+40
words(CREATE,refresh+[0xe3a0000d,0xe5870050,0xe12fff1e])
words(0x80003a5c,[branch(0x80003a5c,CREATE,True)],bytes.fromhex('0a00dbe5'))
words(0x80003a78,[branch(0x80003a78,post,True)],struct.pack('<I',branch(0x80003a78,CREATE,True)))
# Both ordinary >10.0 and raw OPEN sentinel paths clear the original latch.
# Stop only a protected measurement tone (counter>3), preserving short key beeps.
invalid=[0xe92d500f,0xe5cb800a,0xe5db0000,0xe3500003,0x05db0007,0x0350000e,0,0xe5970050,0xe3500003,0,0xe3a01000,0xe3a00005,branch(STOP+48,0x80006e4c,True),0xe8bd900f]
for idx,cond in [(6,1),(9,0xd)]:invalid[idx]=(branch(STOP+4*idx,STOP+52)&0x0fffffff)|(cond<<28)
assert len(invalid)*4==56
words(STOP,invalid)
for a in [0x80003a28,0x80003864]:words(a,[branch(a,STOP,True)],bytes.fromhex('0a80cbe5'))
for variant,data in [('timed',baseline),('continuous',bytes(main))]:
    target=bytearray(reference)
    for off,name in [(0,'boot0-bottom-right-OFFLINE.bin'),(0x6000,'logo-bottom-right-OFFLINE.bin')]:
        p=(HERE/name).read_bytes();target[off:off+len(p)]=p
    target[0x50000:0x50000+len(data)]=data
    (HERE/f'v1-{variant}-main.bin').write_bytes(data)
    (HERE/f'v1-{variant}-full.bin').write_bytes(target)
    (HERE/f'v1-{variant}-manifest.json').write_text(json.dumps(dict(version='1.0',variant=variant,status='OFFLINE, NOT PHYSICALLY INSTALLED/TESTED',main_sha256=sha(data),full_sha256=sha(target),label='highspeedv2',sound='1321 Hz PWM approximation; not MP3 playback',physical_speed_regression_tested=False,changes_vs_beta3=edits if variant=='continuous' else edits[:1]),indent=2))
print('Built 1.0 timed fallback and continuous candidate; not flashed')

