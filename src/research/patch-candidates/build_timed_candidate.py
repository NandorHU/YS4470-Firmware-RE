from pathlib import Path
import sys,struct,hashlib,json
sys.path.insert(0,str(Path(__file__).parent))
from build_period_patch import build,SRC,BASE,EXPECTED
CREATE=0x80060928;STOP=0x80010718;TONE=0x80010754;ACTIVE=CREATE+68

def branch(a,t,link=False):return (0xeb000000 if link else 0xea000000)|(((t-a-8)//4)&0xffffff)
def code(start,words,lituses):
 words=list(words)
 for idx,rd,cond,value in lituses:
  pos=len(words);words.append(value);imm=start+pos*4-(start+idx*4+8);assert 0<=imm<=4095
  words[idx]=(cond<<28)|0x059f0000|(rd<<12)|imm
 return struct.pack('<%dI'%len(words),*words)
def build_timed(data):
 p,edits=build(data);p=bytearray(p)
 def edit(a,new,why,expected=None):
  o=a-BASE;old=data[o:o+len(new)]
  if expected is not None and old!=expected:raise ValueError('unexpected bytes '+hex(a))
  assert p[o:o+len(new)]==old
  p[o:o+len(new)]=new;edits.append(dict(address=hex(a),offset=hex(o),original=old.hex(),modified=new.hex(),purpose=why))
 creator=code(CREATE,[0xe92d4010,0,0,0xe3a01c01,0xe38110a4,0xe3a02000,branch(CREATE+24,0x80040894,True),0xe5840000,0xe3a01001,0xe5801010,0,0xe3a0100d,0xe5801050,0xe8bd8010],[(1,4,14,ACTIVE),(2,0,14,STOP),(10,0,14,0x805ac714)])
 assert len(creator)==68
 creator+=bytes(4)
 stopper=code(STOP,[0xe1a0c000,0,0xe5901000,0xe15c0001,0x112fff1e,0,0xe5901050,0xe3510003,0x912fff1e,0xe3a01000,0xe3a00005,branch(STOP+44,0x80006e4c)],[(1,0,14,ACTIVE),(5,0,14,0x805ac714)])
 assert len(stopper)==56
 tone=struct.pack('<8I',0xe15060b2,0xe59dc00c,0xe59f0008,0xe15c0000,0x059f6004,0xe12fff1e,0x80003a78,1321)
 assert data[CREATE-BASE:CREATE-BASE+32]==b'_______________________________\n'
 assert data[STOP-BASE:STOP-BASE+8]==b'Warnning'
 assert data[TONE-BASE:TONE-BASE+8]==b'HID_REQ_'
 edit(CREATE,creator,'start one-shot420 timer and protect from old50-unit sound counter')
 edit(STOP,stopper,'generation-aware stop callback; skip if another sound superseded diode tone')
 edit(TONE,tone,'1321Hz parameter only for the diode-candidate caller')
 for a,old in [(0x80060744,'3c88ffeb'),(0x8006075c,'3688ffeb'),(0x8001058c,'aac800eb'),(0x80010598,'a7c800eb')]:edit(a,struct.pack('<I',0xe1a00000),'disable only logger whose string is reused',bytes.fromhex(old))
 edit(0x80006e80,struct.pack('<I',branch(0x80006e80,TONE,True)),'tone selector',bytes.fromhex('b26050e1'))
 edit(0x80003a78,struct.pack('<I',branch(0x80003a78,CREATE,True)),'schedule nonblocking stop after successful diode-candidate sound call',bytes.fromhex('506087e5'))
 return bytes(p),edits
if __name__=='__main__':
 p,e=build_timed(SRC.read_bytes());d=Path(__file__).parent;name='f1c100s-period25-tone1321-timer420-EXPERIMENTAL.bin';(d/name).write_bytes(p)
 r=dict(status='EXPERIMENTAL OFFLINE; nominal420 RTOS ticks, PWM approximation; not approved for flash',input_sha256=EXPECTED,output_sha256=hashlib.sha256(p).hexdigest(),length=len(p),changes=e)
 (d/'timed-manifest.json').write_text(json.dumps(r,indent=2));print(r['output_sha256'])

