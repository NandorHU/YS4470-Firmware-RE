from pathlib import Path
import sys,struct,hashlib,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'diode-response-beta2'))
from build_response_beta2 import build_response,code,branch,SRC,BASE,EXPECTED
WRAPPER=0x8000f568;SETTEXT=0x80032038;UI=0x805abefc
SITES=[0x80003344,0x80003350,0x800033fc,0x80003408]
LOGS=[0x8000f404,0x8000f48c,0x8000f500]
def build_display(data):
 previous,_=build_response(data);p=bytearray(previous)
 def cond_branch(a,t,cond):return (branch(a,t)&0x0fffffff)|(cond<<28)
 fallback=WRAPPER+80
 w=[0xe92d500f,0xe3500000,0x13510000,cond_branch(WRAPPER+12,fallback,0),0,0xe5dc2000,0xe3520003,0x05dc2007,0x0352000e,0x05dc2002,0x03520001,cond_branch(WRAPPER+44,fallback,1),0xe5900024,0xe3500000,cond_branch(WRAPPER+56,fallback,0),branch(WRAPPER+60,0x80000c0c,True),0xe3500000,cond_branch(WRAPPER+68,fallback,1),0xe8bd500f,0xe12fff1e,0xe8bd500f,branch(WRAPPER+84,SETTEXT)]
 wrapper=code(WRAPPER,w,[(4,12,14,UI)]);assert len(wrapper)==92
 marker=b'cb_AC_event_cb check '
 assert previous[WRAPPER-BASE:WRAPPER-BASE+len(marker)]==marker
 p[WRAPPER-BASE:WRAPPER-BASE+len(wrapper)]=wrapper
 changes=[dict(address=hex(WRAPPER),offset=hex(WRAPPER-BASE),previous=previous[WRAPPER-BASE:WRAPPER-BASE+len(wrapper)].hex(),modified=wrapper.hex(),purpose='Skip identical measurement label text only in type3/mode14/beta1; forward NULL/new/different text')]
 for a,t,why in [(a,WRAPPER,'measurement label update through scoped equality check') for a in SITES]:
  old=struct.pack('<I',branch(a,SETTEXT,True));assert previous[a-BASE:a-BASE+4]==old
  new=struct.pack('<I',branch(a,t,True));p[a-BASE:a-BASE+4]=new;changes.append(dict(address=hex(a),offset=hex(a-BASE),previous=old.hex(),modified=new.hex(),purpose=why))
 for a in LOGS:
  old=struct.pack('<I',branch(a,0x8005a8a8,True));assert previous[a-BASE:a-BASE+4]==old
  new=struct.pack('<I',0xe1a00000);p[a-BASE:a-BASE+4]=new;changes.append(dict(address=hex(a),offset=hex(a-BASE),previous=old.hex(),modified=new.hex(),purpose='disable only debug logger for reused AC-event strings'))
 assert len(p)==len(previous)
 return bytes(p),changes
if __name__=='__main__':
 p,e=build_display(SRC.read_bytes());previous,_=build_response(SRC.read_bytes());name='f1c100s-diode-display-BETA3-OFFLINE.bin';(HERE/name).write_bytes(p)
 r=dict(status='OFFLINE display optimization; not flashed; physical speed gain not yet established',factory_sha256=EXPECTED,previous_beta2_sha256=hashlib.sha256(previous).hexdigest(),output_sha256=hashlib.sha256(p).hexdigest(),length=len(p),file=name,changes_vs_beta2=e)
 (HERE/'manifest.json').write_text(json.dumps(r,indent=2));print(r['output_sha256'])
