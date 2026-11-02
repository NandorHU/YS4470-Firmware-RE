from pathlib import Path
import sys,struct,json
HERE=Path(__file__).resolve().parent
sys.path.insert(0,'work/pylibs')
from unicorn import *
from unicorn.arm_const import *
BASE=0x7fffffe0;UI=0x805abefc;SH=0x805ac714;HW=0x805ab924;END=0x81fff000
data=(HERE/'v1-continuous-main.bin').read_bytes()
u=Uc(UC_ARCH_ARM,UC_MODE_ARM);u.mem_map(0x7fff0000,0x2100000);u.mem_write(BASE,data)
def wr(a,v):u.mem_write(a,struct.pack('<I',v))
def rd(a):return struct.unpack('<I',u.mem_read(a,4))[0]
events=[];instructions=0
def hook(uc,a,n,d):
    global instructions
    instructions+=1
    if a==0x80040894:raise AssertionError('No timer may be allocated')
    if a in [0x80062d2c,0x80000544,0x800630a4,0x800060d0]:
        if a==0x800060d0:events.append([uc.reg_read(r) for r in [UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3]])
        uc.reg_write(UC_ARM_REG_PC,uc.reg_read(UC_ARM_REG_LR))
u.hook_add(UC_HOOK_CODE,hook)
def regs():
    for r,v in [(UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_SP,0x81ff0000),(UC_ARM_REG_LR,END),(UC_ARM_REG_R4,0x81001000),(UC_ARM_REG_R6,1),(UC_ARM_REG_R8,0),(UC_ARM_REG_R11,UI),(UC_ARM_REG_R7,SH)]:u.reg_write(r,v)
def measure(value):
    regs();u.reg_write(UC_ARM_REG_R5,struct.unpack('<I',struct.pack('<f',value))[0]);u.reg_write(UC_ARM_REG_R1,0x41200000)
    u.emu_start(0x80003a0c,0x80003c40,count=5000)
    assert u.reg_read(UC_ARM_REG_SP)==0x81ff0000
def keycycle():
    regs();u.reg_write(UC_ARM_REG_R4,SH);u.reg_write(UC_ARM_REG_R6,HW)
    u.emu_start(0x8000553c,0x8000556c,count=2000)
def scope(typ=3,mode=14):u.mem_write(UI,bytes([typ]));u.mem_write(UI+7,bytes([mode]));wr(0x805ac770+16,1)
scope();measure(20);assert events==[]
measure(.65);assert len(events)==1 and events[0][1]==1321 and rd(SH+80)==13
start=instructions
for i in range(1000):
    measure(.65)
    if i%2==0:keycycle()
assert len(events)==1 and rd(HW)==1 and rd(SH+80)>=12
steady_instructions=(instructions-start)/1000
measure(20);assert len(events)==2 and events[-1][2]==0 and rd(HW)==0
measure(.65);assert len(events)==3 and rd(HW)==1
# Original raw OPEN sentinel branch including the patched clear hook.
regs();u.emu_start(0x80003858,0x80003868,count=2000)
assert len(events)==4 and rd(HW)==0 and u.mem_read(UI+10,1)==b'\0'
measure(.65)
for _ in range(12):keycycle()
assert rd(HW)==1
keycycle();assert rd(HW)==0
measure(.65);assert rd(HW)==1 # watchdog expiry does not leave one-shot latch stuck
# A superseding short key sound has counter=3: invalid measurement must not cut it.
wr(SH+80,3);before=len(events);measure(20);assert len(events)==before
# Repeated valid results must also leave a superseding short beep's counter alone.
wr(SH+80,3);u.mem_write(UI+10,b'\1');before=len(events);measure(.65)
assert rd(SH+80)==3 and len(events)==before
# Shared sentinel hook in other modes leaves sound behavior unchanged.
scope(1,34);wr(SH+80,13);before=len(events)
regs();u.emu_start(0x80003858,0x80003868,count=2000)
assert len(events)==before and rd(SH+80)==13
assert data[0x80051978-BASE:0x80051984-BASE]==b'highspeedv2\0'
report=dict(passed=True,steady_measurements=1000,pwm_start_events_during_steady_contact=1,timer_allocations=0,tests=['1321Hz selection through original sound gate','1000 valid results: no PWM stop/restart','ordinary invalid result stops tone','raw OPEN sentinel stops tone','13-cycle original KeyTask watchdog','contact restarts after watchdog','superseding short beep preserved','other-mode sentinel unchanged','highspeedv2 string and terminator fit original 12-byte allocation'],stubs=['float conversion/formatting','volume conversion','PWM endpoint 0x800060d0'],executed=['original diode branch','original sound gate and tone selector','original KeyTask countdown','new refresh/stop hooks'],scope='Function-level ARM emulation; no UART/ADC/LCD or real hardware timing validation',steady_instruction_count_with_keycycle_average=steady_instructions)
(HERE/'v1-sound-tests.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

