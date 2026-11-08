"""Reproduce patch data using only public originals and the public v1.0 ZIP."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ZIP_SHA='d336adcb687a1f53695cf1cf98419265f284f97ded2690449f2553fe1e50c038'
APP_LENGTH=5943296;APP_OFFSET=0x50000
ORIGINALS={'V3.6':'7523b2e91dd8627ffebfc7ac0525c0607a56df4cece04028a9c3a8ee558f6eb9',
           'V3.8':'7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290'}
sha=lambda b:hashlib.sha256(b).hexdigest()
def region_delta(data,patch,reverse=False):
    out=bytearray(data)
    for e in patch['edits']:
        off=e['offset'];old,new=bytes.fromhex(e['old']),bytes.fromhex(e['new'])
        if off+len(old)<=APP_OFFSET or off>=APP_OFFSET+APP_LENGTH:continue
        assert APP_OFFSET<=off<off+len(old)<=APP_OFFSET+APP_LENGTH
        off-=APP_OFFSET
        if reverse:old,new=new,old
        assert out[off:off+len(old)]==old and len(old)==len(new)
        out[off:off+len(new)]=new
    return bytes(out)
def differences(before,after):
    assert len(before)==len(after);rows=[];i=0
    while i<len(before):
        if before[i]==after[i]:i+=1;continue
        start=i
        while i<len(before)and before[i]!=after[i]:i+=1
        rows.append({'offset':start,'old':before[start:i].hex(),'new':after[start:i].hex()})
    return rows
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--release-zip',type=Path,required=True);ap.add_argument('--original-dir',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    zraw=a.release_zip.read_bytes();assert sha(zraw)==ZIP_SHA
    with zipfile.ZipFile(a.release_zip)as z:
        continuous=z.read('firmware/f1c100s-1.0.bin')
        assert len(continuous)==APP_LENGTH and sha(continuous)=='697d160047e9f040b31acd79d5b0febb940bc712f15eb6e2d91d997a5608011d'
        cp=json.loads(z.read('project/patches/continuous.json'));tp=json.loads(z.read('project/patches/timed.json'))
    beta_app=region_delta(continuous,cp,True);timed=region_delta(beta_app,tp)
    assert sha(timed)=='89a5bb79ec304a57a758e33bf89d6d7b3848982573460a476fb53e7412877729'
    originals={v:(a.original_dir/v/'f1c100s.bin').read_bytes()for v in ORIGINALS}
    assert all(len(b)==APP_LENGTH and sha(b)==ORIGINALS[v]for v,b in originals.items())
    variants={}
    for name,target in [('continuous',continuous),('timed',timed)]:
        edits=differences(originals['V3.8'],target);inputs={}
        for version,raw in originals.items():
            candidate=bytearray(raw)
            for e in edits:
                off=e['offset'];old,new=bytes.fromhex(e['old']),bytes.fromhex(e['new'])
                assert candidate[off:off+len(old)]==old,'Version-dependent preimage: do not silently port'
                candidate[off:off+len(new)]=new
            changed={i for i,(x,y)in enumerate(zip(raw,candidate))if x!=y}
            intended={i for e in edits for i in range(e['offset'],e['offset']+len(bytes.fromhex(e['old'])))}
            assert changed==intended
            if version=='V3.8':assert candidate==target
            inputs[sha(raw)]={'version':version,'output_sha256':sha(candidate),
              'validation':'Published v1.0 application byte-identical'if version=='V3.8'else'Offline application of identical guarded edits; factory version-specific bytes retained; not physically tested'}
        variants[name]={'inputs':inputs,'edits':edits,'changed_bytes':sum(len(bytes.fromhex(e['old']))for e in edits)}
    data={'schema':'ys4470.public-factory-patch.v1','application_length':APP_LENGTH,'full_flash_length':0x1000000,'application_flash_offset':APP_OFFSET,
      'source_release':{'tag':'v1.0','zip_sha256':ZIP_SHA,'url':'https://github.com/NandorHU/YS4470-Firmware-RE/releases/download/v1.0/YS4470-highspeedv2-1.0-Windows.zip'},
      'variants':variants,'scope':'Application edits only; preserve all other input bytes. No private backup, bootloader/logo replacement or device code.'}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({n:{'ranges':len(v['edits']),'changed_bytes':v['changed_bytes'],'outputs':{i['version']:i['output_sha256']for i in v['inputs'].values()}}for n,v in variants.items()},indent=2))
if __name__=='__main__':main()
