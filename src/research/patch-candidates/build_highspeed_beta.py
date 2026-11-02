"""Opt-in diode polling beta on the existing HighSpeed switch. Offline only."""
from build_timed_candidate import build_timed, branch
from build_period_patch import SRC, BASE, EXPECTED
from pathlib import Path
import hashlib, struct, json

def build_beta(data):
 timed, previous=build_timed(data)
 p=bytearray(timed)
 # Restore factory OFF behavior and put the mode-specific helper on the ON/100 path.
 for a,n in [(0x8005d210,4),(0x8005c084,4),(0x8005c374,20)]:
  p[a-BASE:a-BASE+n]=data[a-BASE:a-BASE+n]
 cave=0x8005c374
 helper=struct.pack('<5I',0xe5d41007,0xe351000e,0x03a01019,0x13a01064,0xe12fff1e)
 p[cave-BASE:cave-BASE+20]=helper
 p[0x8005c084-BASE:0x8005c088-BASE]=struct.pack('<I',0xe1a00000)
 assert data[0x8005d230-BASE:0x8005d234-BASE]==bytes.fromhex('6410a0e3')
 p[0x8005d230-BASE:0x8005d234-BASE]=struct.pack('<I',branch(0x8005d230,cave,True))
 # Same-size English label, includes its NUL terminator and padding.
 assert data[0x80051978-BASE:0x80051984-BASE]==b'HighSpeed\0\0\0'
 p[0x80051978-BASE:0x80051984-BASE]=b'HS + Beta\0\0\0'
 # Construct a final, non-overlapping diff against the validated factory image.
 changes=[];i=0
 while i<len(data):
  if p[i]==data[i]:i+=1;continue
  start=i
  while i<len(data) and p[i]!=data[i]:i+=1
  changes.append(dict(address=hex(BASE+start),offset=hex(start),original=data[start:i].hex(),modified=p[start:i].hex()))
 assert len(p)==len(data)
 return bytes(p),changes

if __name__=='__main__':
 p,e=build_beta(SRC.read_bytes());d=Path(__file__).parent
 name='f1c100s-HS-diode-BETA-tone1321-timer420-OFFLINE.bin'
 (d/name).write_bytes(p)
 r=dict(status='OFFLINE EXPERIMENT; not flashed; physical diode latency not established',input_sha256=EXPECTED,output_sha256=hashlib.sha256(p).hexdigest(),length=len(p),file=name,changes=e,behavior={'diode_highspeed_off':'factory default 200 ticks','diode_highspeed_on':'25 ticks instead of factory 100','sound':'existing 1321Hz / nominal420 ticks','external_meter_commands':'unchanged','english_switch_label':'HS + Beta'})
 (d/'highspeed-beta-manifest.json').write_text(json.dumps(r,indent=2))
 print(r['output_sha256'])
