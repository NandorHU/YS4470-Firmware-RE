from build_boot_logo import *
import sys
sys.path.insert(0,'work/pylibs')
from unicorn import *
from unicorn.arm_const import *
newboot,newlogo,manifest=build();original=(FACTORY/'boot0_rgb480x854.bin').read_bytes();oldlogo=(FACTORY/'logo.bin').read_bytes();rows=[]
def run(label,boot,logo,x,y):
 u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0,0x10000);u.mem_map(0x80000000,0x2000000);u.mem_write(0,boot)
 sp=0x7000;u.mem_write(sp+4,logo[:32]);u.mem_write(sp+0x24,b'eGON.BMP');u.mem_write(sp+0x34,struct.pack('<I',0x4a000))
 for reg,v in [(UC_ARM_REG_SP,sp),(UC_ARM_REG_R4,0x6000),(UC_ARM_REG_R5,0),(UC_ARM_REG_R6,0x81b00000),(UC_ARM_REG_R7,sp+4),(UC_ARM_REG_R8,0x80000000),(UC_ARM_REG_R9,0x81000000)]:u.reg_write(reg,v)
 reads=[];positions=[];checksum_reads=[]
 def hook(uc,a,n,d):
  if a in [0x21b4,0x7f0,0x37dc,0x28a0]:uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  elif a==0x486c:
   chip=uc.reg_read(UC_ARM_REG_R0);off=uc.reg_read(UC_ARM_REG_R1);dest=uc.reg_read(UC_ARM_REG_R2);length=uc.reg_read(UC_ARM_REG_R3)
   assert chip==0 and off==0x6028 and dest==0x81000000 and length==len(logo)-40
   uc.mem_write(dest,logo[40:40+length]);reads.append(dict(offset=hex(off),length=length,destination=hex(dest)));uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
  elif a==0x1ec:positions.append([uc.reg_read(reg) for reg in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]])
 u.hook_add(UC_HOOK_CODE,hook)
 u.hook_add(UC_HOOK_MEM_READ,lambda uc,a,addr,size,val,d:checksum_reads.append(addr),begin=sp+4+12,end=sp+4+15)
 u.emu_start(0x380,0x328,count=5000000);assert u.reg_read(UC_ARM_REG_PC)==0x328
 w,h=struct.unpack_from('<HH',logo,0x1a);assert positions==[[x,y,w,h]],positions
 expected=bytearray(480*854*2);pixels=logo[40:40+w*h*2]
 for yy in range(h):expected[((y+yy)*480+x)*2:((y+yy)*480+x+w)*2]=pixels[yy*w*2:(yy+1)*w*2]
 got=bytes(u.mem_read(0x81b00000,len(expected)));assert got==expected
 assert not checksum_reads
 if label=='custom':(HERE/'emulated-framebuffer.rgb565le').write_bytes(got)
 return dict(case=label,passed=True,positions=positions,flash_reads=reads,framebuffer_matches=True,opaque_logo_checksum_read=False)
rows.append(run('factory',original,oldlogo,140,275))
rows.append(run('custom',newboot,newlogo,20,530))
assert newboot[:12]==original[:12] and newboot[16:0x45c]==original[16:0x45c]
assert newboot[0x468:]==original[0x468:]
(HERE/'tests.json').write_text(json.dumps(dict(passed=True,cases=rows,scope='Actual boot0 logo parser, framebuffer clear and RGB565 drawing loop executed in Unicorn. SPI read/printf/display-hardware init/delay stubbed. Exact position/pixels and continuation to main-header selection verified; not full ROM/DRAM/panel cold boot.'),indent=2))
print('PASS: factory and custom logo parser/draw path; exact framebuffer and continuation; boot checksum valid.')
