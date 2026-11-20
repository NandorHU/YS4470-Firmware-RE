"""Regression for copying only the installer EXE into Downloads; no device access."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import app
from firmware_package import PackageError, read_package

class DefaultPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.portable=self.root/'Downloads'
        self.embedded=self.root/'embedded'
        self.portable.mkdir()
        (self.embedded/'firmware').mkdir(parents=True)
        self.bundled=self.embedded/'firmware/firmware.ysfw'
        self.bundled.write_bytes(b'fixture')
        for name,value in [('portable_folder',self.portable),('resources',self.embedded)]:
            patcher=patch.object(app,name,return_value=value)
            patcher.start();self.addCleanup(patcher.stop)
    def test_exe_alone_finds_embedded_package(self):
        self.assertEqual(app.default_package(),self.bundled)
    def test_existing_adjacent_package_has_priority(self):
        external=self.portable/'firmware/firmware.ysfw'
        external.parent.mkdir();external.write_bytes(b'new update')
        self.assertEqual(app.default_package(),external)
    def test_corrupt_adjacent_package_is_refused_without_fallback(self):
        external=self.portable/'firmware/firmware.ysfw'
        external.parent.mkdir();external.write_bytes(b'corrupt')
        with self.assertRaises(PackageError):read_package(app.default_package())
        self.assertEqual(app.default_package(),external)
if __name__=='__main__':unittest.main()
