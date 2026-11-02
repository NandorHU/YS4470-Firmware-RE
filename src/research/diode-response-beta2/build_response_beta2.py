from pathlib import Path
import sys,struct,json,hashlib
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'latency-diagnostic'))
from build_diagnostic import build_diagnostic,code,branch,SRC,BASE,EXPECTED
HELPER=0x80058750;SITE=0x8000461c
PACK=0x8005fd0c;REPORT=0x8001078c;TRACE=0x800600ac

def build_response(data):
 image,_=build_diagnostic(data);p=bytearray(image)
 assert p[SITE-BASE:SITE-BASE+4]==bytes.fromhex('1e00a0e3')
 # Preserve r1 and the caller return; change only the scalar timeout result r0.
 helper=code(HELPER,[0xe92d4002,0,0xe5d10000,0xe3500003,0x05d10007,0x0350000e,0x05d10002,0x03500001,0x03a00028,0x13a0001e,0xe8bd8002],[(1,1,14,0x805abefc)])
 assert len(helper)==48 and HELPER+len(helper)<=0x80058788
 p[HELPER-BASE:HELPER-BASE+len(helper)]=helper
 p[SITE-BASE:SITE-BASE+4]=struct.pack('<I',branch(SITE,HELPER,True))
 pack=code(PACK,[0,0xe5d12000,0xe5d13007,0xe1a02402,0xe1822803,0xe5d13002,0xe1822c03,0xe3822002,0xe5802004,0xe12fff1e],[(0,1,14,0x805abefc)])
 assert len(pack)==44
 p[PACK-BASE:PACK-BASE+len(pack)]=pack
 report=code(REPORT,[0xe92d4010,0xe1a04000,0,0,0xe591100c,0xe5801034,branch(REPORT+24,PACK,True),0xe1a01000,0xe1a00004,0xe3a02040,branch(REPORT+40,0x80000a98,True),0xe8bd8010],[(2,0,14,TRACE),(3,1,14,0x805abbbc)])
 assert len(report)==56
 p[REPORT-BASE:REPORT-BASE+len(report)]=report
 for a in [0x8005fc44,0x8005fce8,0x8005fcf8]:
  assert image[a-BASE:a-BASE+4]==struct.pack('<I',branch(a,0x8004283c,True))
  p[a-BASE:a-BASE+4]=struct.pack('<I',0xe1a00000)
 changes=[]
 for a,n,why in [(HELPER,len(helper),'timeout40 only type3/mode14/Highspeed1; timeout30 otherwise'),(SITE,4,'mode-specific response deadline selector'),(PACK,len(pack),'pack version2/type/mode/beta state into report header'),(REPORT,len(report),'snapshot live state before copying diagnostic report'),*[(a,4,'disable logger for reused debug text') for a in [0x8005fc44,0x8005fce8,0x8005fcf8]]]:
  o=a-BASE;changes.append(dict(address=hex(a),offset=hex(o),previous=image[o:o+n].hex(),modified=bytes(p[o:o+n]).hex(),purpose=why))
 assert len(p)==len(image)
 return bytes(p),changes

if __name__=='__main__':
 raw=SRC.read_bytes();p,e=build_response(raw);previous,_=build_diagnostic(raw)
 name='f1c100s-diode-response40-BETA2-OFFLINE.bin';(HERE/name).write_bytes(p)
 r=dict(status='OFFLINE response-deadline candidate; not flashed; physical latency fix unproven',factory_sha256=EXPECTED,previous_diagnostic_sha256=hashlib.sha256(previous).hexdigest(),output_sha256=hashlib.sha256(p).hexdigest(),file=name,length=len(p),changes_vs_diagnostic=e,behavior='Only beta-enabled diode: wait up to40 ticks instead of30 for the complete response. Already complete responses are processed immediately; no fixed40-tick delay.')
 (HERE/'manifest.json').write_text(json.dumps(r,indent=2));print(r['output_sha256'])
