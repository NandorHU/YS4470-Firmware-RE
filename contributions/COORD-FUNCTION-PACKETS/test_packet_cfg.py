import struct,unittest
from export_packets import BASE,cfg,blocks
class CfgTests(unittest.TestCase):
    def test_high_address_backward_branch_stays_local(self):
        raw=b'\0'*32+struct.pack('<2I',0xe3a00000,0xeafffffd)
        ins,edges,calls,unknown=cfg(raw,BASE+32)
        self.assertEqual(len(ins),2);self.assertEqual(calls,[]);self.assertEqual(unknown,[])
        self.assertIn({'from':'0x80000004','to':'0x80000000','kind':'local'},edges)
    def test_conditional_return_keeps_fallthrough(self):
        raw=b'\0'*32+struct.pack('<3I',0x112fff1e,0xe3a00001,0xe12fff1e)
        ins,edges,calls,unknown=cfg(raw,BASE+32)
        self.assertEqual(len(ins),3);self.assertEqual(unknown,[])
        self.assertEqual(sum(e['kind']=='return'for e in edges),2)
        self.assertEqual(sum(len(b['instructions'])for b in blocks(ins,edges)),3)
    def test_unresolved_indirect_is_explicit(self):
        raw=b'\0'*32+struct.pack('<I',0xe12fff13)
        self.assertEqual(len(cfg(raw,BASE+32)[3]),1)
if __name__=='__main__':unittest.main()
