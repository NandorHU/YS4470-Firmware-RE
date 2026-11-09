"""Static, byte-checked callee context; no execution or physical access."""
import argparse,json,sys,hashlib,struct
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,default=Path(__file__).resolve().parents[3])
ap.add_argument('--out-dir',type=Path,default=Path(__file__).resolve().parent);a=ap.parse_args();root=a.repo.resolve()
sys.path.insert(0,str(root/'contributions/COORD-FUNCTION-PACKETS'))
from export_packets import cfg,BASE
sha=lambda b:hashlib.sha256(b).hexdigest()
rows=[]
for item in json.loads((root/'original-firmware/manifest.json').read_text())['images']:
 raw=(root/item['path']).read_bytes();assert sha(raw)==item['sha256']
 ins,edges,calls,unknown=cfg(raw,0x80005f14);assert not unknown
 assert struct.unpack_from('<I',raw,0x80006090-BASE)[0]==0x805ab938
 rows.append(dict(version=item['version'],input_sha256=sha(raw),entry='0x80005f14',
  body_sha256=sha(b''.join(i.bytes for _,i in sorted(ins.items()))),
  assembly=[dict(address=hex(pc),bytes=i.bytes.hex(),assembly=i.mnemonic+' '+i.op_str)for pc,i in sorted(ins.items())],
  calls=calls,edges=edges,rx_count_literal=dict(address='0x80006090',value='0x805ab938')))
assert rows[0]['assembly']==rows[1]['assembly']and rows[0]['calls']==rows[1]['calls']
a.out_dir.mkdir(parents=True,exist_ok=True)
(a.out_dir/'synchronous-static.json').write_text(json.dumps(dict(schema='ys4470.synchronous-static.v1',versions=rows,
 source_sha256=sha(Path(__file__).read_bytes()),
 limits=['Complete local ARM CFG under reused direct-branch/return rules; callees not expanded.',
         'No synchronous helper body execution or concurrent clear demonstrated by this index.',
         'Function label/role is a static analyst candidate; indirect callers remain unclassified.']),indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(functions=2,instructions_per_original=len(rows[0]['assembly']),same_body_bytes=True)))
