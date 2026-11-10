"""Audit release assets and record source/simulation checks without hardware."""
import hashlib,io,json,subprocess,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];HERE=Path(__file__).resolve().parent;WORK=ROOT/'work/easy-installer'
from app import VERSION
from engine import Engine, FLASH, patch
from firmware_package import create_package, read_package
from test_engine import FakeTransport
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    report=json.loads((WORK/'release/build-validation.json').read_text());capture=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(HERE),pattern='test_*.py')
    result=unittest.TextTestRunner(stream=capture,verbosity=2).run(suite)
    if not result.wasSuccessful():print(capture.getvalue());raise SystemExit(1)
    report['simulated_transport_tests_passed']=result.testsRun;report['simulation_test_log']=capture.getvalue()
    with zipfile.ZipFile(WORK/f'release/YS4470-Installer-{VERSION}-Windows-x64.zip')as z:
        assert 'YS4470-Installer.exe'in z.namelist()
        assert z.read('firmware/firmware.ysfw') == (WORK/'release/YS4470-E2-V3.8-Diode-Volume.ysfw').read_bytes()
        assert 'licenses/PyInstaller-COPYING.txt'in z.namelist()and 'licenses/Tcl-8.6.15-license.terms'in z.namelist()
        assert not any('backup-before'in n or 'target-full'in n for n in z.namelist())
    from PyInstaller.archive.readers import CArchiveReader
    names=set(CArchiveReader(str(WORK/'dist/YS4470-Installer.exe')).toc)
    expected=['python312.dll','_tkinter.pyd','tcl86t.dll','tk86t.dll','VCRUNTIME140.dll',
      'patch-data.json','tools\\sunxi-fel.exe','tools\\zadig-2.9.exe']
    # Archive names use native path separators on Windows builds.
    normalized={n.replace('\\','/').lower()for n in names}
    missing=[n for n in expected if n.replace('\\','/').lower()not in normalized]
    if missing:raise RuntimeError('Missing runtime prerequisites: '+str(missing))
    assert not any(n.endswith(('.bin', '.ysfw')) for n in normalized), 'Firmware must be external to the EXE'
    released = read_package(WORK/'release/YS4470-E2-V3.8-Diode-Volume.ysfw')
    assert released.family == 'V3.8'
    assert released.image_sha256 == 'e8c00750df2fc465b182c60d2c32dd8cd87cafc4a5cbff4f7e6abbfaec48c76a'
    factory = (ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes()
    data = patch.load_patch(ROOT/'patcher/patch-data.json')
    off = data['application_flash_offset']
    before = b'\xa7'*off + factory + b'\xa7'*(FLASH-off-len(factory))
    with tempfile.TemporaryDirectory(dir=WORK) as temp:
        scratch = Path(temp)
        other_path = scratch/'alternate.ysfw'
        other = create_package(factory, 'V3.8', 'Factory V3.8 validation fixture', other_path)
        alternate_report = scratch/'compiled-alternate.json'
        subprocess.run([str(WORK/'dist/YS4470-Installer.exe'), '--self-test-report',
                        str(alternate_report), '--firmware-package', str(other_path)], check=True, timeout=45)
        alternate = json.loads(alternate_report.read_text())
        assert alternate['external_firmware'] == other.manifest() and not alternate['device_access']
        transport = FakeTransport(before)
        engine = Engine(data, scratch/'backups', lambda _:transport)
        run, installed = engine.install_package(released, approved=True)
        assert installed['application_sha256'] == released.image_sha256 and installed['blocks_written'] > 0
        assert bytes(transport.raw) == before[:off]+released.image+before[off+len(factory):]
        engine.restore(run/'backup-before.bin', approved=True)
        assert bytes(transport.raw) == before
    report['same_exe_verified_with_two_external_packages']=True
    report['released_firmware_simulated_install_and_restore']=True
    report['runtime_components_checked']=expected;report['release_has_no_personal_backup']=True
    report['physical_device_operations']=0;report['gui_visual_check']='Not established by automated desktop control; compiled resource/Tcl checks and source inspection only.'
    (WORK/'release/build-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'simulation_tests':result.testsRun,'runtime_components':len(expected),'external_firmware_verified':True}))
if __name__=='__main__':main()
