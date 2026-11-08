"""Record real original-input tests and public Release identity without USB."""
import io,json,sys,unittest,zipfile,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
def main():
    sys.path.insert(0,str(ROOT/'patcher'));import ys4470_patch as p
    data=p.load_patch();log=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'patcher'),pattern='test_patcher.py')
    result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    if not result.wasSuccessful():print(log.getvalue());raise SystemExit(1)
    zraw=(ROOT/'work/public-patcher/release.zip').read_bytes();assert p.sha(zraw)==data['source_release']['zip_sha256']
    with zipfile.ZipFile(ROOT/'work/public-patcher/release.zip')as z:released=z.read('firmware/f1c100s-1.0.bin')
    app=(ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes();out,_=p.transform(app,data,'continuous');assert out==released
    variants={name:{'ranges':len(v['edits']),'changed_bytes':v['changed_bytes'],'input_and_output_hashes':v['inputs']}for name,v in data['variants'].items()}
    report={'schema':'ys4470.public-patcher-validation.v1','date':'2026-11-08','tests_passed':result.testsRun,'test_log':log.getvalue(),
      'source_release_zip_sha256':p.sha(zraw),'v38_continuous_byte_identical_to_downloaded_release':True,'variants':variants,
      'patch_data_sha256':p.sha((ROOT/'patcher/patch-data.json').read_bytes()),'physical_device_operations':0,
      'limits':['Only published exact original application hashes are supported; no unknown-hash override.',
        'V3.6 preserves version-specific factory bytes and is offline-validated, not physically tested.',
        'Full-flash inputs use synthetic personalized fixtures in regression tests; no personal backup is published.',
        'Bootloader and logo are preserved. This is an application patcher, not the legacy bootloader/logo installer.']}
    (HERE/'validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'tests_passed':result.testsRun,'v38_matches_public_release':True}))
if __name__=='__main__':main()
