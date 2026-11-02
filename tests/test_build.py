"""Portable patch integrity and negative-input tests. Never opens USB."""
from pathlib import Path
import sys,json,argparse,copy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from build import apply,sha
ap=argparse.ArgumentParser();ap.add_argument('--backup',required=True,type=Path);args=ap.parse_args()
data=args.backup.read_bytes();rows=[]
for variant in ['continuous','timed']:
    p=json.loads((ROOT/'patches'/f'{variant}.json').read_text());out=apply(data,p)
    assert out[0x600000:]==data[0x600000:]
    assert out[0x50000+0x51998:0x50000+0x519a4]==b'highspeedv2\0'
    # Beta3's UART/FSM scheduling, reply timeout helper, and display wrapper are unchanged.
    for a,z in [(0x800045d0,0x80004820),(0x80058750,0x80058780),(0x8005d1a0,0x8005d260),(0x8000f568,0x8000f5c4)]:
        off=0x50000+a-0x7fffffe0;end=0x50000+z-0x7fffffe0
        assert out[off:end]==data[off:end]
    bad=bytearray(data);bad[123]^=1
    cases=[('bad-input',bad,p),('truncated-input',data[:-1],p)]
    q=copy.deepcopy(p);q['edits'][0]['old']='00'+q['edits'][0]['old'][2:];cases.append(('bad-old-bytes',data,q))
    q=copy.deepcopy(p);q['output_sha256']='0'*64;cases.append(('bad-output-hash',data,q))
    q=copy.deepcopy(p);q['edits'].insert(1,q['edits'][0]);cases.append(('overlap',data,q))
    for name,inp,patch in cases:
        try:apply(inp,patch)
        except ValueError:rows.append(dict(variant=variant,case=name,passed=True))
        else:raise AssertionError(name)
    rows.append(dict(variant=variant,case='exact-output-and-Beta3-critical-paths',passed=True,output_sha256=sha(out)))
print(json.dumps(dict(passed=True,cases=rows),indent=2))
