"""Build a reusable Windows EXE, its external firmware package and sources."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;WORK=ROOT/'work/easy-installer'
from app import VERSION
from firmware_package import read_package
def sha(b):return hashlib.sha256(b).hexdigest()
def archive(path,files):
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
        for source,name in files:z.write(source,name)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--skip-compile',action='store_true');ap.add_argument('--firmware-package',required=True,type=Path);a=ap.parse_args()
    firmware = a.firmware_package.resolve()
    package = read_package(firmware)
    out=WORK/'release';out.mkdir(parents=True,exist_ok=True);resources=WORK/'resources'
    if not a.skip_compile:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name','YS4470-Installer',
          '--distpath',str(WORK/'dist'),'--workpath',str(WORK/'pyinstaller'),'--specpath',str(WORK),
          '--paths',str(ROOT/'patcher'),'--add-data',str(resources/'tools')+os.pathsep+'tools',
          '--add-data',str(resources/'patch-data.json')+os.pathsep+'.',str(HERE/'app.py')],check=True)
    exe=WORK/'dist/YS4470-Installer.exe';report=WORK/'compiled-self-test.json'
    if report.exists():raise FileExistsError('Compiled self-test already exists; do not overwrite results')
    subprocess.run([str(exe),'--self-test-report',str(report),'--firmware-package',str(firmware)],check=True,timeout=45)
    result=json.loads(report.read_text());assert result['resources_valid']and not result['device_access']
    assert result['external_firmware'] == package.manifest()
    notices=HERE/'THIRD-PARTY-NOTICES.txt'
    runtime=[(exe,'YS4470-Installer.exe'),(HERE/'README.md','README.md'),(HERE/'QUICK-START.txt','QUICK-START.txt'),(notices,'THIRD-PARTY-NOTICES.txt'),
      (firmware,'firmware/firmware.ysfw'),(HERE/'dependencies.lock.json','dependencies.lock.json'),(report,'compiled-self-test.json')]
    # Preserve Python/Tcl/Tk license texts in the binary distribution.
    for p in [Path(sys.base_prefix)/'LICENSE.txt',Path(sys.base_prefix)/'tcl/tcl8.6/license.terms',Path(sys.base_prefix)/'tcl/tk8.6/license.terms']:
        if p.exists():runtime.append((p,'licenses/'+p.parent.name+'-'+p.name))
    import importlib.metadata
    dist=importlib.metadata.distribution('pyinstaller')
    for name in dist.files:
        if str(name).endswith('/licenses/COPYING.txt'):
            runtime.append((Path(dist.locate_file(name)),'licenses/PyInstaller-COPYING.txt'))
    for p in (HERE/'licenses').glob('*'):
        if p.is_file():runtime.append((p,'licenses/'+p.name))
    runtimezip=out/f'YS4470-Installer-{VERSION}-Windows-x64.zip';archive(runtimezip,runtime)
    source_files=[(p,'source/'+p.relative_to(ROOT).as_posix())for folder in(HERE,ROOT/'patcher')for p in folder.rglob('*')if p.is_file()and p.suffix in('.py','.md','.json','.txt','.cmd','.terms')]
    for relative in (
        'original-firmware/manifest.json',
        'contributions/COORD-ADC-CADENCE/reproduce_profiles.py',
        'contributions/COORD-ADC-CADENCE/profile-chain.json',
        'contributions/COORD-ADC-CADENCE/trace_profiles.py',
    ):
        source_files.append((ROOT/relative, 'source/'+relative))
    for p in (ROOT/'contributions/COORD-DIODE-VOLUME').iterdir():
        if p.is_file() and p.suffix in ('.py','.s','.md','.json'):
            source_files.append((p, 'source/'+p.relative_to(ROOT).as_posix()))
    lock=json.loads((HERE/'dependencies.lock.json').read_text());source_files.extend((WORK/'downloads'/r['name'],'third-party-sources/'+r['name'])for r in lock['sources'])
    archive(out/f'YS4470-Installer-{VERSION}-Sources.zip',source_files)
    with (out/'YS4470-E2-V3.8-Diode-Volume.ysfw').open('xb') as stream:
        stream.write(firmware.read_bytes())
    checks=[]
    for p in sorted(out.iterdir()):
        if p.suffix in ('.zip','.ysfw'):
            checks.append(sha(p.read_bytes())+'  '+p.name)
    (out/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='ascii')
    summary={'version':VERSION,'compiled_self_test':result,'exe_sha256':sha(exe.read_bytes()),'assets':[{ 'name':p.name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}for p in sorted(out.glob('*'))],
      'physical_device_operations':0,'validation_scope':'Simulated transport, source regression, packaged EXE resource self-test; not a physical install test.'}
    (out/'build-validation.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
