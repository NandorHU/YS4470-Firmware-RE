"""Reproduce historical experimental application inputs from public stock V3.8.

This replays pinned recorded edits, not the historical source generators. It
does not connect to USB, create a full flash image or approve installation.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'patcher'))
from ys4470_patch import load_patch,transform
CHAIN_SHA='0fe84b836b685cae034abfa6a656d56b23883c989840f87dc0eb152d433dd86b'
def sha(b):return hashlib.sha256(b).hexdigest()
def reproduce(original):
    raw=(HERE/'profile-chain.json').read_bytes();assert sha(raw)==CHAIN_SHA
    chain=json.loads(raw);assert sha(original)==chain['original_sha256']
    image,receipt=transform(original,load_patch(),chain['public_patcher_variant'])
    outputs={};steps=[]
    for stage in chain['stages']:
        assert sha(image)==stage['input_sha256'];p=bytearray(image)
        for edit in stage['edits']:
            off=edit['offset'];old=bytes.fromhex(edit['original']);new=bytes.fromhex(edit['modified'])
            assert int(edit['address'],16)==0x7fffffe0+off
            assert 0<=off and off+len(old)<=len(p) and len(old)==len(new)
            assert p[off:off+len(old)]==old,(stage['name'],hex(off))
            p[off:off+len(new)]=new
        image=bytes(p);assert sha(image)==stage['output_sha256']
        assert len(image)==len(original)and image[:32]==original[:32]
        outputs[stage['name']]=image
        steps.append(dict(name=stage['name'],sha256=sha(image),bytes=len(image),preimage_guards=len(stage['edits'])))
    return outputs,dict(schema='ys4470.profile-replay-receipt.v1',chain_sha256=CHAIN_SHA,
                        stock_sha256=sha(original),public_patcher=receipt,stages=steps,
                        source_generators_executed=False,device_operations=0)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    outputs,receipt=reproduce((ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes())
    a.out.mkdir(parents=True,exist_ok=True)
    for name,raw in outputs.items():
        p=a.out/(name+'-OFFLINE.bin')
        if p.exists():assert p.read_bytes()==raw
        else:
            with p.open('xb')as f:f.write(raw)
    (a.out/'replay-validation.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    print(json.dumps(receipt['stages'],indent=2))
if __name__=='__main__':main()
