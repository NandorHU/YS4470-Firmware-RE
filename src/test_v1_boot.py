import sys
sys.path.insert(0,'outputs/firmware/diode-display-beta3')
from build_display_beta3 import build_display
import sys;sys.path.insert(0,'work/pylibs');sys.path.insert(0,'outputs/firmware/patch-candidates')
from build_timed_candidate import *
from unicorn import *
from unicorn.arm_const import *
folder=Path('outputs/firmware/custom-boot')
boot=(folder/'boot0-bottom-right-OFFLINE.bin').read_bytes();original=SRC.read_bytes();patched=(folder/'v1-continuous-main.bin').read_bytes();rows=[]
for label,image in [('original',original),('candidate',patched),('header_checksum_altered',patched[:12]+bytes(4)+patched[16:])]:
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0,0x10000);u.mem_map(0x80000000,0x2000000);u.mem_write(0,boot);sp=0x7000;u.mem_write(sp+4,image[:32]);u.mem_write(sp+0x2c,b'eGON.EXE');u.reg_write(UC_ARM_REG_R7,sp+4);u.reg_write(UC_ARM_REG_SP,sp);u.reg_write(UC_ARM_REG_R4,0x50000);u.reg_write(UC_ARM_REG_R5,0);u.reg_write(UC_ARM_REG_R8,0x80000000);reads=[]
 def hook(u,a,n,d):
  if a in [0x21b4,0x28a0]:u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
  elif a==0x486c:
   chip=u.reg_read(UC_ARM_REG_R0);off=u.reg_read(UC_ARM_REG_R1);dest=u.reg_read(UC_ARM_REG_R2);ln=u.reg_read(UC_ARM_REG_R3)
   assert chip==0 and off==0x50020 and dest==0x80000000 and ln==len(image)-32
   u.mem_write(dest,image[32:32+ln]);reads.append(dict(flash_offset=hex(off),destination=hex(dest),length=ln));u.reg_write(UC_ARM_REG_PC,u.reg_read(UC_ARM_REG_LR))
 u.hook_add(UC_HOOK_CODE,hook);u.emu_start(0x344,0x80000000,count=5000)
 loaded=bytes(u.mem_read(0x80000000,len(image)-32));assert loaded==image[32:]
 rows.append(dict(image=label,jump_address=hex(u.reg_read(UC_ARM_REG_PC)),payload_matches=loaded==image[32:],reads=reads))
Path('outputs/firmware/custom-boot/v1-boot-load-tests.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='modified positioning bootloader raw offset0x344 signature-match through main-image jump; SPI read/printf/delay stubbed; not full cold boot'),indent=2));print('PASS original bootloader main-image load and jump for original/candidate/altered-checksum header; header+32 excluded, payload exact; not full cold boot')


