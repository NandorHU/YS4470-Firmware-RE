"""Build a portable English Windows EXE plus public factory/source archives."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;WORK=ROOT/'work/easy-installer';VERSION='1.1.0-beta.1'
def sha(b):return hashlib.sha256(b).hexdigest()
def archive(path,files):
    with zipfile.ZipFile(path,'x',zipfile.ZIP_DEFLATED,compresslevel=9)as z:
        for source,name in files:z.write(source,name)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--skip-compile',action='store_true');a=ap.parse_args()
    out=WORK/'release';out.mkdir(parents=True,exist_ok=True);resources=WORK/'resources'
    if not a.skip_compile:
        subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--windowed','--name','YS4470-Installer',
          '--distpath',str(WORK/'dist'),'--workpath',str(WORK/'pyinstaller'),'--specpath',str(WORK),
          '--paths',str(ROOT/'patcher'),'--add-data',str(resources)+os.pathsep+'.',str(HERE/'app.py')],check=True)
    exe=WORK/'dist/YS4470-Installer.exe';report=WORK/'compiled-self-test.json'
    if report.exists():raise FileExistsError('Compiled self-test already exists; do not overwrite results')
    subprocess.run([str(exe),'--self-test-report',str(report)],check=True,timeout=45)
    result=json.loads(report.read_text());assert result['resources_valid']and not result['device_access']
    notices=HERE/'THIRD-PARTY-NOTICES.txt'
    runtime=[(exe,'YS4470-Installer.exe'),(HERE/'README.md','README.md'),(HERE/'QUICK-START.txt','QUICK-START.txt'),(notices,'THIRD-PARTY-NOTICES.txt'),
      (resources/'factory/V3.8/f1c100s.bin','factory/V3.8/f1c100s.bin'),(HERE/'dependencies.lock.json','dependencies.lock.json'),(report,'compiled-self-test.json')]
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
    lock=json.loads((HERE/'dependencies.lock.json').read_text());source_files.extend((WORK/'downloads'/r['name'],'third-party-sources/'+r['name'])for r in lock['sources'])
    archive(out/f'YS4470-Installer-{VERSION}-Sources.zip',source_files)
    checks=[]
    for p in sorted(out.glob('*.zip')):checks.append(sha(p.read_bytes())+'  '+p.name)
    (out/'SHA256SUMS.txt').write_text('\n'.join(checks)+'\n',encoding='ascii')
    summary={'version':VERSION,'compiled_self_test':result,'exe_sha256':sha(exe.read_bytes()),'assets':[{ 'name':p.name,'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size}for p in sorted(out.glob('*'))],
      'physical_device_operations':0,'validation_scope':'Simulated transport, source regression, packaged EXE resource self-test; not a physical install test.'}
    (out/'build-validation.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
