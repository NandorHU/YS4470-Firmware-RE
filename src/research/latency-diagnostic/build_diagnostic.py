"""Temporary measurement-latency instrumentation; never opens the USB device."""
from pathlib import Path
import sys, struct, hashlib, json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'patch-candidates'))
from build_highspeed_beta import build_beta
from build_timed_candidate import code,branch
from build_period_patch import SRC,BASE,EXPECTED
STATE=0x800600ac;GUI=0x800600ec;CONSUME=0x80060130;IRQ=0x80060170
TX=0x800586ec;RX=0x8005871c;REPORT=0x8001078c
TICK=0x805abbbc
LOG_CALLS=[0x8005fec8,0x8005fee8,0x8005fefc,0x8005ff0c,0x8005ff70,0x8005ffa8,0x8005ffbc,0x80060038,0x80060044,0x80060050,0x800585a4,0x800585c4,0x800585e4,0x80058604,0x80058638,0x80058650,0x80058658,0x800105e0]
REGIONS=[(STATE,0x800601b8),(TX,0x80058788),(REPORT,0x800107c4)]

def build_diagnostic(data):
 beta,_=build_beta(data);p=bytearray(beta)
 def put(a,new,expected=None):
  o=a-BASE
  if expected is not None and bytes(p[o:o+len(expected)])!=expected:raise ValueError('unexpected bytes '+hex(a))
  p[o:o+len(new)]=new
 def words(a,w,lit):return code(a,w,lit)
 # The state resides in the loaded RAM copy of a disabled debug-string cluster.
 state=struct.pack('<16I',0x52545359,1,*([0]*14))
 put(STATE,state)
 tx=words(TX,[0xe92d5003,0,0,0xe590000c,0xe58c0008,0xe59c0038,0xe2800001,0xe58c0038,0xe8bd5003,branch(TX+36,0x80005e84)],[(1,12,14,STATE),(2,0,14,TICK)])
 assert len(tx)==48
 put(TX,tx)
 rx=words(RX,[0xe92d5003,0,0,0xe590000c,0xe58c003c,0xe59c102c,0xe2811001,0xe58c102c,0xe8bd5003,0xe5dc4001,0xe12fff1e],[(1,12,14,STATE),(2,0,14,TICK)])
 assert len(rx)==52
 put(RX,rx)
 gui=words(GUI,[0xe92d41f0,0xe92d1007,0,0,0xe591100c,0xe5902014,0xe5801014,0xe3520000,0x10412002,0xe5802018,0xe590c01c,0xe152000c,0x8580201c,0xe8bd1007,branch(GUI+56,0x8005d04c)],[(2,0,14,STATE),(3,1,14,TICK)])
 assert len(gui)==68
 put(GUI,gui)
 consume=words(CONSUME,[0xe92d400e,0,0,0xe592200c,0xe5812020,0xe597001c,0xe5913028,0xe1500003,0x15812024,0x15810028,0x15913030,0x12833001,0x15813030,0xe8bd800e],[(1,1,14,STATE),(2,2,14,TICK)])
 assert len(consume)==64
 put(CONSUME,consume)
 irq=words(IRQ,[0xe3500005,0xe5c31000,(branch(IRQ+8,0x80007410)&0x0fffffff)|0x10000000,0xe92d5003,0,0,0xe590000c,0xe58c000c,0xe59c1008,0xe0401001,0xe58c1010,0xe8bd5003,branch(IRQ+48,0x80007410)],[(4,12,14,STATE),(5,0,14,TICK)])
 assert len(irq)==60 and IRQ+len(irq)<=0x800601b8
 put(IRQ,irq)
 report=words(REPORT,[0xe92d4010,0xe1a04000,0,0,0xe591100c,0xe5801034,0xe1a01000,0xe1a00004,0xe3a02040,branch(REPORT+36,0x80000a98,True),0xe8bd8010],[(2,0,14,STATE),(3,1,14,TICK)])
 assert len(report)==52
 put(REPORT,report)
 for a in LOG_CALLS:
  old=data[a-BASE:a-BASE+4]
  assert old==struct.pack('<I',branch(a,0x8004283c,True)),hex(a)
  put(a,struct.pack('<I',0xe1a00000),old)
 for a,t,old,link in [(0x800045e0,TX,'270600eb',True),(0x80004738,RX,'0140dce5',True),(0x8005d048,GUI,'f0412de9',False),(0x800037fc,CONSUME,'1c0097e5',True),(0x80010648,REPORT,'2fc1ffeb',True),(0x8000740c,IRQ,'0010c3e5',False)]:
  put(a,struct.pack('<I',branch(a,t,link)),bytes.fromhex(old))
 put(0x80051978,b'Diag Beta\0\0\0',b'HS + Beta\0\0\0')
 assert len(p)==len(data)
 changes=[];i=0
 while i<len(data):
  if p[i]==data[i]:i+=1;continue
  start=i
  while i<len(data) and p[i]!=data[i]:i+=1
  changes.append(dict(address=hex(BASE+start),offset=hex(start),original=data[start:i].hex(),modified=p[start:i].hex()))
 return bytes(p),changes

if __name__=='__main__':
 p,e=build_diagnostic(SRC.read_bytes());name='f1c100s-latency-DIAGNOSTIC-OFFLINE.bin';(HERE/name).write_bytes(p)
 r=dict(status='OFFLINE diagnostic; not flashed; USB GET_REPORT transport not physically verified',input_sha256=EXPECTED,output_sha256=hashlib.sha256(p).hexdigest(),length=len(p),file=name,changes=e,state_address=hex(STATE),cave_ranges=[[hex(a),hex(z)] for a,z in REGIONS],get_report_behavior='64 diagnostic bytes instead of factory zeros; interrupt IN/OUT code unchanged')
 (HERE/'manifest.json').write_text(json.dumps(r,indent=2));print(r['output_sha256'])

