"""Static heuristic: find PC-relative loads of the UI base and any [reg,#8] access in the next ~120 words."""
import sys,struct,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'YS4470-EMULATOR-CLAUDE-20261120/runtime/windows'))
from capstone import *
B=0x7fffffe0
d=open(sys.argv[1],'rb').read()
md=Cs(CS_ARCH_ARM,CS_MODE_ARM)
UI=0x805abefc
for off in range(0,len(d)-4,4):
    w,=struct.unpack_from('<I',d,off)
    if w&0x0F7F0000!=0x051F0000: continue
    a=B+off; lit=a+8+(w&0xfff)*(1 if w&0x800000 else -1)
    if not 0<=lit-B<len(d)-4: continue
    v,=struct.unpack_from('<I',d,lit-B)
    if v!=UI: continue
    rd=(w>>12)&15
    rn={9:'sb',10:'sl',11:'fp',12:'ip'}.get(rd,f'r{rd}')
    for i in md.disasm(d[off:off+4*160],a):
        if i.address==a: continue
        if re.search(r'\['+rn+r', #8\]',i.op_str): print(hex(a),hex(i.address),i.mnemonic,i.op_str)
        if i.mnemonic.startswith('pop') or i.mnemonic=='bx' or (i.mnemonic.startswith('ldm') and 'pc' in i.op_str): break
        if re.match(rn+r'(,|$)',i.op_str) and not i.mnemonic.startswith(('str','cmp','tst','teq','cmn')): break
