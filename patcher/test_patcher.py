"""Offline regression tests with the two owner-published original inputs."""
import copy,hashlib,importlib.util,json,subprocess,sys,tempfile,unittest
from contextlib import contextmanager
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE));import ys4470_patch as p
@contextmanager
def temporary():
    base=(ROOT/'work/public-patcher/test-temp').resolve()
    assert base.is_relative_to(ROOT.resolve())
    base.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=base)as folder:
        assert Path(folder).resolve().parent==base
        yield folder
class PatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=p.load_patch();cls.originals={v:(ROOT/'original-firmware'/v/'f1c100s.bin').read_bytes()for v in('V3.6','V3.8')}
    def container(self,app):
        # Device-specific stand-ins deliberately differ from the author's backup.
        raw=bytearray(b'\xA7'*self.data['full_flash_length']);off=self.data['application_flash_offset'];raw[off:off+len(app)]=app
        marker=b'OWNER-CALIBRATION-PRESERVE-ME-0000';raw[0x900000:0x900000+len(marker)]=marker
        return bytes(raw)
    def test_factory_applications_and_roundtrip(self):
        for version,raw in self.originals.items():
            for name in('continuous','timed'):
                with self.subTest(version=version,variant=name):
                    out,r=p.transform(raw,self.data,name);back,_=p.transform(out,self.data,name,True)
                    self.assertEqual(back,raw);self.assertEqual(r['changed_bytes'],939 if name=='continuous' else 928)
                    self.assertEqual(p.sha(out),self.data['variants'][name]['inputs'][p.sha(raw)]['output_sha256'])
    def test_personalized_full_flash_roundtrip_and_preservation(self):
        for version,app in self.originals.items():
            raw=self.container(app);off=self.data['application_flash_offset']
            for name in('continuous','timed'):
                with self.subTest(version=version,variant=name):
                    out,r=p.transform(raw,self.data,name);back,_=p.transform(out,self.data,name,True)
                    self.assertEqual(back,raw);self.assertEqual(out[:off],raw[:off]);self.assertEqual(out[off+len(app):],raw[off+len(app):])
                    self.assertEqual(r['container'],'full-flash');self.assertTrue(r['outside_application_preserved'])
    def test_version_specific_factory_data_preserved(self):
        a,b=self.originals['V3.6'],self.originals['V3.8'];different={i for i,(x,y)in enumerate(zip(a,b))if x!=y}
        for name in('continuous','timed'):
            out,_=p.transform(a,self.data,name)
            self.assertTrue(all(out[i]==a[i]for i in different))
    def test_unknown_application_rejected(self):
        raw=bytearray(self.originals['V3.8']);raw[123456]^=1
        with self.assertRaises(p.PatchError):p.transform(bytes(raw),self.data,'continuous')
        self.assertFalse(p.inspect(bytes(raw),self.data)['supported'])
    def test_unknown_full_flash_rejected(self):
        raw=bytearray(self.container(self.originals['V3.8']));raw[0x50000+123456]^=1
        with self.assertRaises(p.PatchError):p.transform(bytes(raw),self.data,'continuous')
    def test_wrong_sizes_rejected(self):
        for raw in (b'',b'eGON.EXE',self.originals['V3.8'][:-1]):
            self.assertFalse(p.inspect(raw,self.data)['supported'])
            with self.assertRaises(p.PatchError):p.transform(raw,self.data,'continuous')
    def test_wrong_header_or_offset_rejected(self):
        raw=bytearray(self.originals['V3.8']);raw[4]^=1
        with self.assertRaises(p.PatchError):p.locate(bytes(raw),self.data)
        full=bytearray(self.data['full_flash_length']);full[:len(self.originals['V3.8'])]=self.originals['V3.8']
        with self.assertRaises(p.PatchError):p.locate(bytes(full),self.data)
    def test_original_byte_guard_and_output_hash_guard(self):
        bad=copy.deepcopy(self.data);bad['variants']['continuous']['edits'][0]['old']='00'
        with self.assertRaises(p.PatchError):p.transform(self.originals['V3.8'],bad,'continuous')
        bad=copy.deepcopy(self.data);bad['variants']['continuous']['inputs'][p.sha(self.originals['V3.8'])]['output_sha256']='0'*64
        with self.assertRaises(p.PatchError):p.transform(self.originals['V3.8'],bad,'continuous')
    def test_patch_data_integrity(self):
        with temporary()as t:
            f=Path(t)/'bad.json';f.write_text('{}')
            with self.assertRaises(p.PatchError):p.load_patch(f)
    def test_detect_factory_and_both_output_variants(self):
        for version,raw in self.originals.items():
            self.assertEqual(p.inspect(raw,self.data)['recognized_states'][0]['version'],version)
            for name in('continuous','timed'):
                out,_=p.transform(raw,self.data,name);info=p.inspect(out,self.data)
                self.assertEqual(info['recognized_states'][0],{'state':'patched','variant':name,'source_version':version})
    def test_already_patched_and_wrong_revert_variant_rejected(self):
        out,_=p.transform(self.originals['V3.8'],self.data,'continuous')
        for variant in('continuous','timed'):
            with self.assertRaises(p.PatchError):p.transform(out,self.data,variant)
        with self.assertRaises(p.PatchError):p.transform(out,self.data,'timed',True)
    def test_no_inplace_and_no_overwrite(self):
        with temporary()as t:
            source=Path(t)/'own.bin';source.write_bytes(self.originals['V3.8']);out,r=p.transform(source.read_bytes(),self.data,'continuous')
            with self.assertRaises(p.PatchError):p.write_new(source,source,out,r)
            dest=Path(t)/'keep.bin';dest.write_bytes(b'keep')
            with self.assertRaises(p.PatchError):p.write_new(source,dest,out,r)
            self.assertEqual(dest.read_bytes(),b'keep');self.assertEqual(source.read_bytes(),self.originals['V3.8'])
    def test_existing_receipt_prevents_any_output(self):
        with temporary()as t:
            src=Path(t)/'input.bin';dst=Path(t)/'new.bin';src.write_bytes(self.originals['V3.8']);Path(str(dst)+'.report.json').write_text('keep')
            out,r=p.transform(src.read_bytes(),self.data,'continuous')
            with self.assertRaises(p.PatchError):p.write_new(src,dst,out,r)
            self.assertFalse(dst.exists())
    def test_cli_apply_inspect_revert_and_input_unchanged(self):
        with temporary()as t:
            src=Path(t)/'my firmware.bin';dst=Path(t)/'new firmware.bin';back=Path(t)/'restored.bin';src.write_bytes(self.originals['V3.8'])
            def run(*args):return subprocess.run([sys.executable,str(HERE/'ys4470_patch.py'),*map(str,args)],capture_output=True,text=True)
            self.assertEqual(run('inspect',src).returncode,0)
            self.assertEqual(run('apply',src,'--output',dst).returncode,0)
            self.assertEqual(run('apply',src,'--output',dst).returncode,2)
            self.assertEqual(run('revert',dst,'--output',back).returncode,0)
            self.assertEqual(back.read_bytes(),src.read_bytes());self.assertEqual(src.read_bytes(),self.originals['V3.8'])
if __name__=='__main__':unittest.main()
