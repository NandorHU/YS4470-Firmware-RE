from pathlib import Path
import hashlib,struct,json
ROOT=Path(__file__).resolve().parent.parent
SRC=ROOT/'Project_March_V3.8_V02.26.6/f1c100s.bin'
EXPECTED='7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290'
BASE=0x7fffffe0

def build(data):
 if hashlib.sha256(data).hexdigest()!=EXPECTED:raise ValueError('Unexpected input SHA256')
 result=bytearray(data);changes=[]
 def edit(addr,old,new,label):
  o=addr-BASE
  if result[o:o+len(old)]!=old:raise ValueError(f'Unexpected bytes {addr:x}')
  result[o:o+len(old)]=new;changes.append(dict(address=hex(addr),offset=hex(o),original=old.hex(),modified=new.hex(),purpose=label))
 cave=0x8005c374;site=0x8005d210
 helper=struct.pack('<5I',0xe5d41007,0xe351000e,0x03a01019,0x13a010c8,0xe12fff1e)
 edit(cave,b'Current key = %s\n\0\0\0',helper,'mode0x0e period=25, otherwise original 200')
 edit(0x8005c084,bytes.fromhex('07faffeb'),struct.pack('<I',0xe1a00000),'disable only logging of replaced debug string')
 branch=0xeb000000|(((cave-site-8)//4)&0xffffff)
 edit(site,bytes.fromhex('c810a0e3'),struct.pack('<I',branch),'call mode-specific period selector')
 return bytes(result),changes
if __name__=='__main__':
 raw=SRC.read_bytes();patched,changes=build(raw)
 out=Path(__file__).parent/'f1c100s-diode-period25-OFFLINE.bin';out.write_bytes(patched)
 manifest=dict(status='OFFLINE EXPERIMENT ONLY - integrity and physical operation not validated',input_sha256=EXPECTED,output_sha256=hashlib.sha256(patched).hexdigest(),length=len(patched),changes=changes)
 (out.parent/'manifest.json').write_text(json.dumps(manifest,indent=2));print(json.dumps(manifest,indent=2))
