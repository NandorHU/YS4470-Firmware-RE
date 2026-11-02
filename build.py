"""Reproduce 1.0 from the pinned working Beta3 full backup. No device access."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parent
FEL_SHA='da14ffa7243767d9c8c5579618171fde2956c4b37b82139bb519932aba6e9375'
sha=lambda b:hashlib.sha256(b).hexdigest()
def apply(data,patch):
    if len(data)!=patch['length'] or sha(data)!=patch['input_sha256']:raise ValueError('Unexpected Beta3 full-backup hash/length')
    out=bytearray(data);end=0
    for e in patch['edits']:
        off=e['offset'];old=bytes.fromhex(e['old']);new=bytes.fromhex(e['new'])
        if off<end or not old or len(old)!=len(new) or off+len(old)>len(out) or out[off:off+len(old)]!=old:raise ValueError('Patch range/original-byte validation failed')
        out[off:off+len(new)]=new;end=off+len(old)
    if sha(out)!=patch['output_sha256']:raise ValueError('Output hash mismatch')
    blocks=[o for o in range(0,len(out),65536) if out[o:o+65536]!=data[o:o+65536]]
    if blocks!=patch['changed_sectors'] or any(o>=0x600000 for o in blocks):raise ValueError('Changed-sector mismatch')
    return bytes(out)
def build(backup,output,fel=None):
    data=Path(backup).read_bytes();output=Path(output)
    if fel and sha(Path(fel).read_bytes())!=FEL_SHA:raise ValueError('Unexpected sunxi-fel executable hash')
    records=[]
    for variant in ['continuous','timed']:
        patch=json.loads((ROOT/'patches'/f'{variant}.json').read_text());target=apply(data,patch)
        folder=output/variant;folder.mkdir(parents=True,exist_ok=True)
        # CreateNew at the installer stage protects its own run logs/backups.
        (folder/'inputs').mkdir(exist_ok=True);(folder/'tools').mkdir(exist_ok=True)
        (folder/'inputs/current-beta3.bin').write_bytes(data)
        (folder/'candidate-region.bin').write_bytes(target[:0x600000])
        (folder/'previous-region.bin').write_bytes(data[:0x600000])
        (folder/'firmware-1.0-full.bin').write_bytes(target)
        (folder/'f1c100s-1.0.bin').write_bytes(target[0x50000:0x50000+5943296])
        if fel:shutil.copyfile(fel,folder/'tools/sunxi-fel.exe')
        source=(ROOT/'src/Install-V1.template.ps1').read_text(encoding='utf-8-sig')
        source=source.replace('TARGET_REGION_HASH',sha(target[:0x600000])).replace('ALLOWED_SECTORS',','.join(hex(o) for o in patch['changed_sectors']))
        assert 'TARGET_REGION_HASH' not in source and 'ALLOWED_SECTORS' not in source
        (folder/'Install-V1.ps1').write_text(source,encoding='utf-8-sig')
        for name,action in [('Install-V1','InstallV1'),('Restore-Beta3','RestoreBeta3')]:
            cmd='@echo off\necho YS-4470 1.0 '+variant+' - bootloader es firmware; csak kulon jovahagyas utan!\npowershell.exe -NoProfile -Command "try { & \'%~dp0Install-V1.ps1\' -Action '+action+' -Approval I_APPROVE_YS4470_V1 2>&1 | Tee-Object -FilePath \'%~dp0'+name+'-console.txt\' } catch { Write-Host $_; exit 1 }"\npause\n'
            (folder/(name+'-APPROVAL-REQUIRED.cmd')).write_text(cmd,encoding='ascii')
        record=dict(version='1.0',variant=variant,full_sha256=sha(target),region_sha256=sha(target[:0x600000]),changed_sectors=patch['changed_sectors'],status='OFFLINE, physical installation and speed regression pending')
        (folder/'build-manifest.json').write_text(json.dumps(record,indent=2));records.append(record)
    return records
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--backup',required=True,type=Path);ap.add_argument('--fel',type=Path);ap.add_argument('--output',type=Path,default=ROOT/'out')
    a=ap.parse_args();print(json.dumps(build(a.backup,a.output,a.fel),indent=2))
