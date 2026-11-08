"""Bounded ARM926 bootloader payload-read arguments; no real flash or init."""
import argparse,json,sys,zipfile
from pathlib import Path
from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_HOOK_CODE,UC_PROT_READ,UC_PROT_EXEC
from unicorn.arm_const import UC_CPU_ARM_926,UC_ARM_REG_CPSR,UC_ARM_REG_SP,UC_ARM_REG_PC,UC_ARM_REG_LR,UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3,UC_ARM_REG_R4,UC_ARM_REG_R5,UC_ARM_REG_R8
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'patcher'));import ys4470_patch as patch
FACTORY_BOOT_SHA='cdecb2aa58beb830c0efceb77e9488dc91de328df64341c6191df8d042a6d132'
def run(boot,app):
    u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.ctl_set_cpu_model(UC_CPU_ARM_926)
    u.mem_map(0,0x10000,UC_PROT_READ|UC_PROT_EXEC);u.mem_write(0,boot)
    u.mem_map(0x10000000,0x4000);sp=0x10002000;u.mem_write(sp+4,app[:32])
    for reg,value in((UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_SP,sp),(UC_ARM_REG_R4,0x50000),(UC_ARM_REG_R5,0),(UC_ARM_REG_R8,0x80000000)):u.reg_write(reg,value)
    reads=[];visited=[]
    def code(cpu,a,size,_):
        if a==0x508:cpu.emu_stop();return
        if a in(0x21b4,0x486c):
            if a==0x486c:reads.append([cpu.reg_read(r)for r in(UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3)])
            cpu.reg_write(UC_ARM_REG_PC,cpu.reg_read(UC_ARM_REG_LR));return
        assert 0x490<=a<0x508;visited.append(hex(a))
    u.hook_add(UC_HOOK_CODE,code);u.emu_start(0x490,0x50c,count=160)
    assert u.reg_read(UC_ARM_REG_PC)==0x508 and reads==[[0,0x50020,0x80000000,len(app)-32]]
    return {'flash_read_args_port_flash_ram_length':reads[0],'visited':visited,'stop_before_jump':'0x508'}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--factory-boot',type=Path,required=True);a=ap.parse_args()
    factory=a.factory_boot.read_bytes();assert patch.sha(factory)==FACTORY_BOOT_SHA
    with zipfile.ZipFile(ROOT/'work/public-patcher/release.zip')as z:released=z.read('firmware/boot0-1.0.bin')
    data=patch.load_patch();cases=[]
    for version in('V3.6','V3.8'):
        original=(ROOT/'original-firmware'/version/'f1c100s.bin').read_bytes()
        apps=[('original',original)]+[(n,patch.transform(original,data,n)[0])for n in('continuous','timed')]
        for name,app in apps:
            for bootname,boot in(('factory',factory),('released',released)):
                cases.append({'version':version,'application':name,'app_sha256':patch.sha(app),'boot':bootname,'boot_sha256':patch.sha(boot),**run(boot,app)})
    report={'schema':'ys4470.public-patcher-loader.v1','cpu':'UC_CPU_ARM_926','cases':cases,'passed':len(cases),
      'limits':['Only the loader0x490..0x508 window executes; startup/clock/DRAM/cold boot are not emulated.',
        'SPI read and printf are leaf models; no actual peripheral or device is accessed.',
        'This proves unchanged payload-read arguments for these two known bootloaders, not compatibility with every unknown bootloader.',
        'The patcher never replaces a bootloader or logo. No bootloader binary is published in this contribution.']}
    (HERE/'loader-validation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps({'passed':len(cases),'read_length':len(original)-32,'device_operations':0}))
if __name__=='__main__':main()
