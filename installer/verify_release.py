"""Audit release assets and record source/simulation checks without hardware."""
import hashlib,io,json,sys,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;WORK=ROOT/'work/easy-installer'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    report=json.loads((WORK/'release/build-validation.json').read_text());capture=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
    result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    if not result.wasSuccessful():print(capture.getvalue());raise SystemExit(1)
    report['simulated_transport_tests_passed']=result.testsRun;report['simulation_test_log']=capture.getvalue()
    with zipfile.ZipFile(WORK/'release/YS4470-Installer-1.1.0-beta.2-Windows-x64.zip')as z:
        assert 'YS4470-Installer.exe'in z.namelist()
        assert sha(z.read('factory/V3.8/f1c100s.bin'))=='7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290'
        assert 'licenses/PyInstaller-COPYING.txt'in z.namelist()and 'licenses/Tcl-8.6.15-license.terms'in z.namelist()
        assert not any('backup-before'in n or 'target-full'in n for n in z.namelist())
    from PyInstaller.archive.readers import CArchiveReader
    names=set(CArchiveReader(str(WORK/'dist/YS4470-Installer.exe')).toc)
    expected=['python312.dll','_tkinter.pyd','tcl86t.dll','tk86t.dll','VCRUNTIME140.dll',
      'factory\\V3.8\\f1c100s.bin','tools\\sunxi-fel.exe','tools\\zadig-2.9.exe']
    # Archive names use native path separators on Windows builds.
    normalized={n.replace('\\','/').lower()for n in names}
    missing=[n for n in expected if n.replace('\\','/').lower()not in normalized]
    if missing:raise RuntimeError('Missing runtime prerequisites: '+str(missing))
    report['runtime_components_checked']=expected;report['release_has_no_personal_backup']=True
    report['physical_device_operations']=0;report['gui_visual_check']='Not established by automated desktop control; compiled resource/Tcl checks and source inspection only.'
    (WORK/'release/build-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'simulation_tests':result.testsRun,'runtime_components':len(expected),'factory_verified':True}))
if __name__=='__main__':main()
