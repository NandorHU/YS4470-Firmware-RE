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
        assert z.read('firmware/firmware.ysfw') == (WORK/'release/YS4470-E2-V3.8-v2v4.ysfw').read_bytes()
        assert 'licenses/PyInstaller-COPYING.txt'in z.namelist()and 'licenses/Tcl-8.6.15-license.terms'in z.namelist()
        assert not any('backup-before'in n or 'target-full'in n for n in z.namelist())
    # Launch the extracted EXE from a different working directory without an
    # explicit package argument: this is the user's ready-to-start layout.
    with tempfile.TemporaryDirectory(dir=WORK) as temp:
        extracted = Path(temp) / 'ownprotocol ready'
        with zipfile.ZipFile(WORK/f'release/YS4470-Installer-{VERSION}-Windows-x64.zip') as bundle:
            bundle.extractall(extracted)
        default_report = Path(temp) / 'default-package.json'
        subprocess.run([str(extracted/'YS4470-Installer.exe'), '--self-test-report',
                        str(default_report)], cwd=Path(temp), check=True, timeout=45)
        default = json.loads(default_report.read_text())
        assert default['external_firmware'] == read_package(extracted/'firmware/firmware.ysfw').manifest()
        assert not default['device_access']
        # Reproduce the screenshot failure: copy only the EXE into a Downloads-
        # like directory. No adjacent firmware directory and no explicit argument.
        import shutil
        isolated = Path(temp) / 'Downloads alone'
        isolated.mkdir()
        lone_exe = isolated / 'YS4470-v2v4-Standalone.exe'
        shutil.copy2(extracted/'YS4470-Installer.exe', lone_exe)
        lone_report = Path(temp) / 'standalone-package.json'
        subprocess.run([str(lone_exe),'--self-test-report',str(lone_report)],
                       cwd=WORK, check=True, timeout=45)
        lone = json.loads(lone_report.read_bytes())
        assert lone['external_firmware'] == default['external_firmware'] and not lone['device_access']
    report['extracted_exe_auto_selects_bundled_firmware_from_unrelated_cwd']=True
    report['exe_alone_without_adjacent_firmware_uses_embedded_package']=True
    with zipfile.ZipFile(WORK/f'release/YS4470-Installer-{VERSION}-Sources.zip') as sources:
        assert 'source/contributions/COORD-ADC-CADENCE/ownprotocol/build_ownprotocol.py' in sources.namelist()
        assert 'source/contributions/COORD-ADC-CADENCE/ownprotocol/ownprotocol.s' in sources.namelist()
        assert 'source/contributions/COORD-ADC-CADENCE/diodefixed/build_diodefixed.py' in sources.namelist()
        assert 'source/contributions/COORD-ADC-CADENCE/diodefixed/candidate_adapter.py' in sources.namelist()
        assert 'source/contributions/COORD-ADC-CADENCE/vprofiles/vprofiles.s' in sources.namelist()
        assert 'source/contributions/COORD-ADC-CADENCE/vprofiles/test_vprofiles.py' in sources.namelist()
    from PyInstaller.archive.readers import CArchiveReader
    names=set(CArchiveReader(str(WORK/'dist/YS4470-Installer.exe')).toc)
    expected=['python312.dll','_tkinter.pyd','tcl86t.dll','tk86t.dll','VCRUNTIME140.dll',
      'patch-data.json','tools\\sunxi-fel.exe','tools\\zadig-2.9.exe']
    # Archive names use native path separators on Windows builds.
    normalized={n.replace('\\','/').lower()for n in names}
    missing=[n for n in expected if n.replace('\\','/').lower()not in normalized]
    if missing:raise RuntimeError('Missing runtime prerequisites: '+str(missing))
    assert 'firmware/firmware.ysfw' in normalized, 'Standalone EXE must embed its default firmware'
    released = read_package(WORK/'release/YS4470-E2-V3.8-v2v4.ysfw')
    assert released.family == 'V3.8'
    assert released.image_sha256 == 'da35f4968038801ddfe5d3528fb45d59df644ee80350a940e8c76a9e8d264c01'
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
        # A fresh backup store also recognizes the reviewed ownprotocol image,
        # so later updates do not depend on this PC's previous install history.
        fresh_engine = Engine(data, scratch/'fresh-backups', lambda _:transport)
        next_run, next_result = fresh_engine.install_package(other, approved=True)
        assert next_result['application_sha256'] == other.image_sha256
        assert bytes(transport.raw) == before
        fresh_engine.restore(next_run/'backup-before.bin', approved=True)
        assert bytes(transport.raw) == before[:off]+released.image+before[off+len(factory):]
        engine.restore(run/'backup-before.bin', approved=True)
        assert bytes(transport.raw) == before
        # Upgrade path of the current user: beta.5 app already installed -> beta.6, from a fresh backup
        # store, then restore back to beta.5. The beta.5 package is a pinned input (not rebuilt here).
        beta4 = read_package(WORK/'inputs/YS4470-E2-V3.8-vprofiles.ysfw')
        assert beta4.image_sha256 == 'f477c1acf54704817410c165f495d7c48db007e14160bda08aff9c5e0d57b497'
        with_own = before[:off]+beta4.image+before[off+len(factory):]
        upgrade_transport = FakeTransport(with_own)
        upgrade = Engine(data, scratch/'upgrade-backups', lambda _:upgrade_transport)
        up_run, up_result = upgrade.install_package(released, approved=True)
        assert up_result['application_sha256'] == released.image_sha256
        assert bytes(upgrade_transport.raw) == before[:off]+released.image+before[off+len(factory):]
        upgrade.restore(up_run/'backup-before.bin', approved=True)
        assert bytes(upgrade_transport.raw) == with_own
    report['same_exe_verified_with_two_external_packages']=True
    report['released_firmware_simulated_install_and_restore']=True
    report['ownprotocol_update_from_fresh_backup_store_and_restore']=True
    report['upgrade_from_beta5_app_and_restore']=True
    report['runtime_components_checked']=expected;report['release_has_no_personal_backup']=True
    report['physical_device_operations']=0;report['gui_visual_check']='Not established by automated desktop control; compiled resource/Tcl checks and source inspection only.'
    (WORK/'release/build-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'simulation_tests':result.testsRun,'runtime_components':len(expected),'external_firmware_verified':True}))
if __name__=='__main__':main()
