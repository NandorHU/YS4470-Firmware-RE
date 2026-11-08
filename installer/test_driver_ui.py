"""Driver helper launcher tests; no real GUI, elevation or driver installation."""
import sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE));import app
class DriverTests(unittest.TestCase):
    def setUp(self):
        base=(HERE.parent/'work/easy-installer/driver-ui-tests').resolve();assert base.is_relative_to(HERE.parent.resolve());base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();assert self.root.parent==base
        self.resources=self.root/'resources';(self.resources/'tools').mkdir(parents=True)
        self.raw=b'controlled fake helper';(self.resources/'tools/zadig-2.9.exe').write_bytes(self.raw);self.fake=SimpleNamespace(root=self.resources)
    def test_explicit_driver_action_requests_windows_elevation(self):
        with patch.object(app,'ZADIG_SHA',app.patch.sha(self.raw)),patch.object(app,'user_root',return_value=self.root/'user'),patch.object(app.messagebox,'askokcancel',return_value=True),patch.object(app.messagebox,'showerror')as error,patch.object(app.os,'startfile',create=True)as start:
            app.App.driver(self.fake)
            self.assertFalse(error.called);self.assertEqual(start.call_args.args[1],'runas')
            target=Path(start.call_args.args[0]);self.assertEqual(target.read_bytes(),self.raw);self.assertTrue(target.is_relative_to(self.root))
    def test_cancel_does_not_run_helper(self):
        with patch.object(app,'ZADIG_SHA',app.patch.sha(self.raw)),patch.object(app.messagebox,'askokcancel',return_value=False),patch.object(app.os,'startfile',create=True)as start:
            app.App.driver(self.fake);self.assertFalse(start.called)
    def test_bad_helper_is_never_started(self):
        with patch.object(app.messagebox,'showerror')as error,patch.object(app.os,'startfile',create=True)as start:
            app.App.driver(self.fake);self.assertTrue(error.called);self.assertFalse(start.called)
if __name__=='__main__':unittest.main()
