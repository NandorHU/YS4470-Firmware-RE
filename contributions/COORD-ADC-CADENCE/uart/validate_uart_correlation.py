"""Three-way transport tests plus original-code late/interleaved reply cases."""
import argparse,io,itertools
from elftools.elf.elffile import ELFFile
from trace_uart_correlation import *

class Compiled:
    def __init__(self,path,name):
        elf=ELFFile(io.BytesIO(path.read_bytes()));assert elf.header.e_machine=='EM_ARM'and elf.little_endian
        sym=next(s for s in elf.get_section_by_name('.symtab').iter_symbols()if s.name==name)
        section=elf.get_section(sym['st_shndx']);code=section.data();assert len(code)<0xf00
        for s in elf.iter_sections():assert not(s['sh_type']in('SHT_REL','SHT_RELA')and s['sh_info']==sym['st_shndx']and s.num_relocations())
        self.u=Uc(UC_ARCH_ARM,UC_MODE_ARM);self.u.ctl_set_cpu_model(UC_CPU_ARM_926)
        self.u.mem_map(0x20000000,0x1000,UC_PROT_READ|UC_PROT_EXEC);self.u.mem_write(0x20000000,code)
        self.u.mem_map(0x30000000,0x1000,UC_PROT_READ|UC_PROT_WRITE);self.entry=0x20000000+sym['st_value']
        self.code_size=len(code);self.coverage=set();self.u.hook_add(UC_HOOK_CODE,self.code)
        self.u.hook_add(UC_HOOK_MEM_WRITE,self.memory)
    def code(self,u,a,n,_):
        if a==0x20000ff0:u.emu_stop();return
        assert n==4 and 0x20000000<=a<0x20000000+self.code_size
        self.coverage.add(a)
    def memory(self,u,access,a,n,v,_):
        assert 0x30000300<=a and a+n<=0x300003c8 or a==0x30000500 and n==4 or 0x30000d00<=a and a+n<=0x30000f00
    def call(self,args):
        u=self.u
        for r,v in ((UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_SP,0x30000f00),(UC_ARM_REG_LR,0x20000ff0)):
            u.reg_write(r,v)
        for r,v in zip((UC_ARM_REG_R0,UC_ARM_REG_R1,UC_ARM_REG_R2,UC_ARM_REG_R3),args):u.reg_write(r,v)
        u.emu_start(self.entry,0,count=5000);assert u.reg_read(UC_ARM_REG_PC)==0x20000ff0
        assert u.reg_read(UC_ARM_REG_SP)==0x30000f00
        return u.reg_read(UC_ARM_REG_R0)
    def frame(self,payload):
        self.u.mem_write(0x30000100,payload);self.u.mem_write(0x30000300,b'\x5a'*200)
        n=self.call((0x30000100,len(payload),0x30000300))
        return n,bytes(self.u.mem_read(0x30000300,200))
    def receive(self,count,status,value):
        self.u.mem_write(0x30000300,b'\xa5'*200);self.u.mem_write(0x30000500,struct.pack('<I',count))
        r=self.call((0x30000300,0x30000500,status,value))
        return r,struct.unpack('<I',self.u.mem_read(0x30000500,4))[0],bytes(self.u.mem_read(0x30000300,200))

def validate(version,raw,obj):
    m=OriginalUART(raw);frame=Compiled(obj,'ys4470_uart_frame');rx=Compiled(obj,'ys4470_uart_rx_push')
    fingerprint=hashlib.sha256();tx_cases=rx_cases=0
    for n,alignment,pattern,busy in itertools.product((0,1,2,3,4,7,31,32,33,198,199,200,201),range(4),range(2),(0,2)):
        payload=bytes(((i*37+0x60)&255)if pattern==0 else 255 for i in range(n))
        expected=payload+bytes([sum(payload)&255])if n<=199 else b''
        m.reset();r=m.send(payload,busy,alignment);length,buffer=frame.frame(payload)
        assert r==int(n<=199) and bytes(m.wire)==expected and length==len(expected)
        assert bytes(m.u.mem_read(TXBUF,200))==buffer==expected+b'\x5a'*(200-len(expected))
        assert m.total_ready_reads==len(expected)*(busy+1)
        assert bytes(m.u.mem_read(ARGS+alignment,n))==payload
        fingerprint.update(bytes([n,alignment,pattern,busy])+expected);tx_cases+=1
    # Complete byte domain, buffer edge and status gate. This is the established
    # nonnegative-count domain; arbitrary corrupt signed counts are excluded.
    for count,status,value in itertools.product((0,1,198,199,200,201),(0,3,4,0x84),range(256)):
        m.reset();m.put(COUNT,count);m.receive(value|0x12340000,status)
        c_ok,c_count,c_buffer=rx.receive(count,status,value|0x12340000)
        admitted=bool(status&4)and count<200;expected=bytearray(b'\xa5'*200)
        if admitted:expected[count]=value
        assert m.rd(COUNT)==c_count==count+int(admitted)and c_ok==int(admitted)
        assert bytes(m.u.mem_read(RX,200))==c_buffer==bytes(expected)
        assert bytes(m.u.mem_read(TXBUF,200))==b'\x5a'*200
        fingerprint.update(struct.pack('<III',count,status,value)+bytes(expected));rx_cases+=1
    late=[]
    for command,arrival in itertools.product((0x1b,0x1d),range(46)):
        row=replay_late(m,command,arrival)
        if arrival>=33:
            assert row['published']==[dict(t=arrival+5,kind='publish',pc='0x800047b4',raw=50)]
            assert row['tx_bytes']==('5e5e'*2 if command==0x1b else'6060'*2)
        late.append({k:v for k,v in row.items()if k not in ('events','states')})
    examples=[]
    for arrival in (0,26,30,32,33,45):examples.append(replay_late(m,0x1d,arrival))
    interleavings=[]
    for command,site in itertools.product((0x1b,0x1d),(0x8000456c,0x80005efc,0x800045e4)):
        m.reset();m.build(command);packet=bytes([0x5e if command==0x1b else 0x60,50,0,0,0])
        m.injection=dict(site=site,packet=packet,done=False)
        for t in range(4):m.step(t)
        pubs=[e for e in m.events if e['kind']=='publish'];assert len(pubs)==1 and pubs[0]['raw']==50
        assert m.critical_clear_checks==1 and m.injection['done']
        interleavings.append(dict(command=hex(command),site=hex(site),events=m.events,
            scope='Explicit host ISR interleave with full CPU-context save/restore, IRQ-enabled gate, separate ISR stack; not an ARM exception-entry/RTOS proof.'))
    # A reply buffered before state1's clear is lost; a concatenation of two
    # valid replies publishes the first. Finalization retains RX bytes/count;
    # the next state1 clear loses the trailing frame without publishing it.
    concat=[]
    for command in (0x1b,0x1d):
        m.reset();m.build(command);m.step(0);header=0x5e if command==0x1b else 0x60
        m.now=1
        for b in bytes([header,50,0,0,0,header,0x58,2,0,0]):m.receive(b)
        assert m.rd(COUNT)==10
        for t in (1,2,3):m.step(t)
        pubs=[e for e in m.events if e['kind']=='publish']
        assert len(pubs)==1 and pubs[0]['raw']==50 and m.rd(COUNT)==10 and m.byte(FSM)==0
        m.build(command);assert m.rd(COUNT)==10;m.step(4);assert m.rd(COUNT)==0
        assert len([e for e in m.events if e['kind']=='publish'])==1
        concat.append(dict(command=hex(command),events=m.events,count_after_finalize=10,count_after_next_state1=0,
            second_raw_fixture=600,second_not_published=True))
    # The receive header distinguishes command classes, not successive requests
    # of the same class: cross-command old response rejects at original state3.
    m.reset();m.build(0x1d);m.step(0);m.now=1
    for b in b'\x5e\x32\0\0\0':m.receive(b)
    assert m.step(1)==6 and not any(e['kind']=='publish'for e in m.events)
    cross=dict(events=m.events,expected_command='0x1d',old_header='0x5e',rejected=True)
    # Bound the original TX busy loop; no fake success when hardware-ready
    # remains clear. The original code has no loop counter/deadline in this loop.
    m.reset();m.u.mem_write(ARGS,b'\x60');m.busy_reads_per_byte=1000000
    for r,v in ((UC_ARM_REG_CPSR,0x13),(UC_ARM_REG_SP,TOP),(UC_ARM_REG_LR,RET),(UC_ARM_REG_R0,ARGS),(UC_ARM_REG_R1,1)):m.u.reg_write(r,v)
    m.u.emu_start(0x80005e84,0,count=160)
    assert m.u.reg_read(UC_ARM_REG_PC)in(0x80006e00,0x80006e04,0x80006e08)and not m.wire
    blocked=dict(instruction_budget=160,pc=hex(m.u.reg_read(UC_ARM_REG_PC)),ready_reads=m.total_ready_reads,
        no_uart_write=True,not_a_timeout_measurement=True)
    observed=[dict(address=hex(a),bytes=b)for a,b in sorted(m.coverage.items())]
    return dict(version=version,input_sha256=sha(raw),tx_cases=tx_cases,rx_cases=rx_cases,
        late_cases=len(late),interleave_cases=len(interleavings),concatenated_cases=len(concat),
        fingerprint=fingerprint.hexdigest(),late_matrix=late,late_examples=examples,
        interleavings=interleavings,concatenated=concat,cross_command=cross,blocked_tx=blocked,
        c_functions=[dict(name='ys4470_uart_frame',code_bytes=frame.code_size,observed_addresses=len(frame.coverage)),
                     dict(name='ys4470_uart_rx_push',code_bytes=rx.code_size,observed_addresses=len(rx.coverage))],
        original_observed_instructions=observed)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--object',type=Path,required=True);a=ap.parse_args()
    manifest=json.loads((ROOT/'original-firmware/manifest.json').read_text());versions=[]
    for item in manifest['images']:
        raw=(ROOT/item['path']).read_bytes();assert sha(raw)==item['sha256']
        r=validate(item['version'],raw,a.object);versions.append(r)
        print(item['version'],{k:r[k]for k in('tx_cases','rx_cases','late_cases','interleave_cases','concatenated_cases')},flush=True)
    assert versions[0]['fingerprint']==versions[1]['fingerprint']
    for key in ('late_matrix','interleavings','concatenated','cross_command','blocked_tx','original_observed_instructions'):
        assert versions[0][key]==versions[1][key],key
    report=dict(schema='ys4470.uart-correlation.v1',source_sha256=sha(Path(__file__).read_bytes()),
        harness_sha256=sha((HERE/'trace_uart_correlation.py').read_bytes()),
        reconstruction_c_sha256=sha((ROOT/'reconstruction/uart_transport.c').read_bytes()),
        reconstruction_h_sha256=sha((ROOT/'reconstruction/uart_transport.h').read_bytes()),
        arm_object_sha256=sha(a.object.read_bytes()),versions=versions,
        original_python_c_transport_cases=sum(v['tx_cases']+v['rx_cases']for v in versions),
        physical_device_operations=0,
        limits=['Byte arrivals, UART-ready status and counter advance are synthetic; UART framing/checksum, ISR, FSM, original clear/copy/getter/critical code execute.',
            'ISR interleave uses a host context save/restore, not a complete ARM interrupt-entry or RTOS model.',
            'TX source counts0..201 and RX counts0..201 only; corrupt signed counts and count+1 wrap at UINT_MAX are outside the established equivalence domain.',
            'Observed paths do not establish that no other reader/global/protocol layer exists.',
            'This proves acceptance of a deliberately stale fixture, not its frequency on hardware, external conversion restart or physical latency.',
            'C components are pure transformations; MMIO polling and transaction correlation are not reconstructed firmware drivers.'])
    write(HERE/'validation.json',report)
    print('PASS',report['original_python_c_transport_cases'],'three-way transport cases')
if __name__=='__main__':main()
