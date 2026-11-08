import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch as mockpatch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent;sys.path.insert(0,str(HERE));import engine as e
class FakeTransport:
    def __init__(self,raw):self.raw=bytearray(raw);self.writes=[];self.reads=0;self.bad_confirm=False;self.bad_verify=False;self.fail_write=False;self.wrong_device=False
    def probe(self):return {'soc':'other'if self.wrong_device else'F1C100s','flash':'Winbond EF/40','bytes':e.FLASH}
    def read(self,offset,length,path):
        self.reads+=1;data=bytes(self.raw[offset:offset+length])
        if self.bad_confirm and self.reads==65:data=bytes([data[0]^1])+data[1:]
        if self.bad_verify and self.reads==129:data=bytes([data[0]^1])+data[1:]
        Path(path).write_bytes(data);return data
    def write(self,offset,path):
        raw=Path(path).read_bytes();self.writes.append(offset)
        if self.fail_write:self.raw[offset:offset+len(raw)]=b'\xff'*len(raw);raise RuntimeError('simulated interrupted write')
        self.raw[offset:offset+len(raw)]=raw
class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=e.patch.load_patch(ROOT/'patcher/patch-data.json');cls.base=(ROOT/'work/easy-installer/tests').resolve();assert cls.base.is_relative_to(ROOT.resolve());cls.base.mkdir(parents=True,exist_ok=True)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(dir=self.base);self.addCleanup(self.temp.cleanup);self.folder=Path(self.temp.name).resolve();assert self.folder.parent==self.base
        app=(ROOT/'original-firmware/V3.8/f1c100s.bin').read_bytes();self.raw=bytearray(b'\xa7'*e.FLASH);self.raw[0x50000:0x50000+len(app)]=app;self.raw=bytes(self.raw)
        self.transport=FakeTransport(self.raw);self.progress=[];self.engine=e.Engine(self.data,self.folder,lambda _:self.transport,lambda n,s:self.progress.append(n))
    def test_install_preserves_all_other_regions_and_verifies(self):
        run,result=self.engine.install(approved=True);expected,_=e.patch.transform(self.raw,self.data,'continuous')
        self.assertEqual(bytes(self.transport.raw),expected);self.assertTrue(result['success']);self.assertEqual(self.progress[-1],100)
        self.assertEqual((run/'backup-before.bin').read_bytes(),self.raw);self.assertEqual(self.transport.reads,192)
        self.assertTrue(all(0x50000<=i<i+e.SECTOR<=0x5fb000 for i in self.transport.writes))
    def test_explicit_approval_required(self):
        with self.assertRaises(e.InstallError):self.engine.install()
        self.assertEqual(self.transport.reads,0);self.assertEqual(self.transport.writes,[])
    def test_v36_preserves_its_version_data(self):
        app=(ROOT/'original-firmware/V3.6/f1c100s.bin').read_bytes()
        raw=bytearray(self.raw);raw[0x50000:0x50000+len(app)]=app;self.transport.raw=raw
        self.engine.install(approved=True)
        result=self.transport.raw[0x50000:0x50000+len(app)]
        self.assertEqual(e.patch.sha(result),self.data['variants']['continuous']['inputs'][e.patch.sha(app)]['output_sha256'])
    def test_corrupt_backup_cannot_restore(self):
        run,_=self.engine.install(approved=True);backup=run/'backup-before.bin';raw=bytearray(backup.read_bytes());raw[0x900000]^=1;backup.write_bytes(raw)
        count=len(self.transport.writes)
        with self.assertRaises(e.InstallError):self.engine.restore(backup,approved=True)
        self.assertEqual(len(self.transport.writes),count)
    def test_wrong_native_tool_hash_is_rejected(self):
        exe=self.folder/'bad.exe';exe.write_bytes(b'bad')
        with self.assertRaises(e.InstallError):e.FelTransport(exe,self.folder)
    def test_probe_rejects_multiple_or_wrong_devices(self):
        for listing in('','USB device 001:001 Allwinner F1C100s\nUSB device 001:002 Allwinner F1C100s','USB device 001:001 Allwinner other'):
            transport=e.FelTransport.__new__(e.FelTransport);transport.command=lambda *args:listing
            with self.assertRaises(e.InstallError):transport.probe()
    def test_unknown_device_never_reads_or_writes(self):
        self.transport.wrong_device=True
        with self.assertRaises(e.InstallError):self.engine.install(approved=True)
        self.assertEqual(self.transport.reads,0);self.assertEqual(self.transport.writes,[])
    def test_unknown_application_saves_backup_but_never_writes(self):
        self.transport.raw[0x50000+100000]^=1
        with self.assertRaises(e.InstallError):self.engine.install(approved=True)
        self.assertEqual(self.transport.writes,[]);self.assertEqual(len(list(self.folder.glob('*/backup-before.bin'))),1)
    def test_inconsistent_double_read_never_writes(self):
        self.transport.bad_confirm=True
        with self.assertRaises(e.InstallError):self.engine.install(approved=True)
        self.assertEqual(self.transport.writes,[]);self.assertNotIn(100,self.progress)
    def test_readback_failure_never_reports_complete(self):
        self.transport.bad_verify=True
        with self.assertRaises(e.InstallError):self.engine.install(approved=True)
        self.assertNotIn(100,self.progress);self.assertFalse(any(self.folder.glob('*/result.json')))
    def test_restore_verified_backup(self):
        run,_=self.engine.install(approved=True);self.progress=[]
        _,r=self.engine.restore(run/'backup-before.bin',approved=True)
        self.assertEqual(bytes(self.transport.raw),self.raw);self.assertEqual(r['action'],'restore')
    def test_interrupted_write_can_restore_only_prior_plan(self):
        self.transport.fail_write=True
        with self.assertRaises(e.InstallError):self.engine.install(approved=True)
        run=next(self.folder.glob('20*'));self.transport.fail_write=False
        self.engine.restore(run/'backup-before.bin',approved=True);self.assertEqual(bytes(self.transport.raw),self.raw)
    def test_restore_rejects_changed_calibration_or_other_device(self):
        run,_=self.engine.install(approved=True);self.transport.raw[0x900000]^=1;count=len(self.transport.writes)
        with self.assertRaises(e.InstallError):self.engine.restore(run/'backup-before.bin',approved=True)
        self.assertEqual(len(self.transport.writes),count)
    def test_already_installed_does_not_rewrite(self):
        self.engine.install(approved=True);count=len(self.transport.writes)
        _,r=self.engine.install(approved=True);self.assertEqual(r['blocks_written'],0);self.assertEqual(len(self.transport.writes),count)
    def test_active_lock_prevents_concurrent_session(self):
        (self.folder/'running.lock').write_text('test')
        with self.assertRaises(e.InstallError):self.engine.install(approved=True)
        self.assertEqual(self.transport.reads,0)
    def test_bundled_factory_has_strict_identity(self):
        root=self.folder/'resources';(root/'factory/V3.8').mkdir(parents=True);(root/'factory/V3.8/f1c100s.bin').write_bytes(b'bad')
        with self.assertRaises(e.InstallError):e.factory_image(root,self.data)
if __name__=='__main__':unittest.main()
