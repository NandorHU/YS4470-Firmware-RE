"""Guarded application-only installer. Native transport is never used by tests."""
from __future__ import annotations
import json,os,re,subprocess,sys,time,uuid
from contextlib import contextmanager
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'patcher'))
import ys4470_patch as patch
FLASH=0x1000000;SECTOR=0x10000;CHUNK=0x40000
FACTORY_SHA='7e7d7230155fe0790eb48531de2ef463bb122c0ae1a820ab6d10cf2e60f50290'
FEL_SHA='cc1e338a238ab99dc0ca12bdb3558d2781f9e81ed411a9b92d1c4021a67a2acf'
class InstallError(RuntimeError):pass
def save_json(path,obj):
    with Path(path).open('x',encoding='utf8')as f:json.dump(obj,f,indent=2);f.write('\n');f.flush();os.fsync(f.fileno())
def save_bytes(path,data):
    with Path(path).open('xb')as f:f.write(data);f.flush();os.fsync(f.fileno())
    if Path(path).read_bytes()!=data:raise InstallError('Saved file verification failed')
def factory_image(resources,data,variant='continuous'):
    raw=(Path(resources)/'factory/V3.8/f1c100s.bin').read_bytes()
    if patch.sha(raw)!=FACTORY_SHA:raise InstallError('Bundled factory firmware hash mismatch')
    return patch.transform(raw,data,variant)[0]
class FelTransport:
    def __init__(self,exe,log):
        self.exe=Path(exe);self.log=Path(log);self.bus=None;self.counter=0
        if patch.sha(self.exe.read_bytes())!=FEL_SHA:raise InstallError('Bundled FEL utility integrity failed')
    def command(self,args,select=True):
        self.counter+=1;argv=[str(self.exe)]+(['-d',self.bus]if select else[])+list(args)
        r=subprocess.run(argv,capture_output=True,timeout=120,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (self.log/f'fel-{self.counter:04d}.stdout.txt').write_bytes(r.stdout)
        (self.log/f'fel-{self.counter:04d}.stderr.txt').write_bytes(r.stderr)
        if r.returncode:raise InstallError('FEL command failed. Keep the meter in FEL mode. '+r.stderr.decode(errors='replace')[-400:])
        return (r.stdout+r.stderr).decode(errors='replace')
    def probe(self):
        listing=self.command(['--list'],False)
        devices=[line.strip()for line in listing.splitlines()if line.startswith('USB device')]
        if len(devices)!=1:raise InstallError('Connect exactly one YS-4470 in FEL mode. Check the USB driver and data cable.')
        m=re.fullmatch(r'USB device\s+(\d+:\d+)\s+Allwinner F1C100s',devices[0])
        if not m:raise InstallError('The selected device is not the expected F1C100s')
        self.bus=m[1];info=self.command(['spiflash-info'])
        if not re.search(r'Manufacturer: Winbond \(EFh\), model: 40h, size: 16777216 bytes\.',info):
            raise InstallError('Unsupported flash identity or size. No write is allowed.')
        return {'bus':self.bus,'soc':'F1C100s','flash':'Winbond EF/40','bytes':FLASH}
    def read(self,offset,length,path):
        self.command(['spiflash-read',hex(offset),hex(length),str(path)])
        raw=Path(path).read_bytes()
        if len(raw)!=length:raise InstallError('Incomplete flash read')
        return raw
    def write(self,offset,path):self.command(['spiflash-write',hex(offset),str(path)])

class Engine:
    def __init__(self,data,root,transport_factory,progress=lambda *args:None):
        self.data=data;self.root=Path(root).resolve();self.transport_factory=transport_factory;self.progress=progress
        self.root.mkdir(parents=True,exist_ok=True)
    @contextmanager
    def locked(self):
        lock=self.root/'running.lock'
        try:
            with lock.open('x')as f:f.write(str(os.getpid()))
        except FileExistsError:raise InstallError('Another installer session or unfinished lock exists. Review the backup folder before retrying.')
        try:yield
        finally:lock.unlink(missing_ok=True)
    def read_full(self,transport,run,name,start,weight):
        chunks=[]
        for off in range(0,FLASH,CHUNK):
            path=run/f'{name}-{off:06x}.bin';raw=transport.read(off,CHUNK,path)
            if len(raw)!=CHUNK:raise InstallError('Incomplete read before any further operation')
            chunks.append(raw);self.progress(start+int(weight*(off+CHUNK)/FLASH),name)
        raw=b''.join(chunks);save_bytes(run/(name+'.bin'),raw);return raw
    def blocks(self,before,target):
        if len(before)!=FLASH or len(target)!=FLASH:raise InstallError('Full flash length required')
        off=self.data['application_flash_offset'];end=off+self.data['application_length']
        if before[:off]!=target[:off]or before[end:]!=target[end:]:raise InstallError('Bootloader/logo/storage preservation failed')
        blocks=[i for i in range(0,FLASH,SECTOR)if before[i:i+SECTOR]!=target[i:i+SECTOR]]
        if any(i<off or i+SECTOR>end for i in blocks):raise InstallError('Write range leaves the application')
        return blocks
    def install(self,variant='continuous',approved=False):
        if not approved:raise InstallError('The user must explicitly start installation')
        return self.run('install',variant)
    def restore(self,backup,approved=False):
        if not approved:raise InstallError('The user must explicitly approve restoration')
        return self.run('restore','continuous',Path(backup))
    def run(self,action,variant,backup=None):
      with self.locked():
        run=self.root/(time.strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]);run.mkdir()
        transport=self.transport_factory(run);identity=None
        try:
            self.progress(0,'Checking device');identity=transport.probe()
            if identity.get('soc')!='F1C100s'or identity.get('bytes')!=FLASH or identity.get('flash')!='Winbond EF/40':raise InstallError('Unsupported device')
            before=self.read_full(transport,run,'backup-before',2,28)
            if action=='install':
                info=patch.inspect(before,self.data)
                if not info['supported']:raise InstallError('Unsupported installed application. Your automatic backup was saved; no write occurred.')
                state=info['recognized_states'][0]
                if state['state']=='patched':
                    if state['variant']==variant:target=before;receipt={'already_installed':True}
                    else:
                        original,_=patch.transform(before,self.data,state['variant'],True);target,receipt=patch.transform(original,self.data,variant)
                else:target,receipt=patch.transform(before,self.data,variant)
                allowed=self.blocks(before,target)
            else:
                manifest=json.loads((backup.parent/'backup-manifest.json').read_text())
                target=backup.read_bytes()
                if len(target)!=FLASH or patch.sha(target)!=manifest['backup_sha256']or manifest.get('confirmed_second_read')is not True:raise InstallError('Backup integrity failed')
                # Backup is from a previous verified pre-write snapshot, tied to a stored plan.
                plan=json.loads((backup.parent/'plan.json').read_text())
                if plan['backup_sha256']!=patch.sha(target):raise InstallError('Backup/plan mismatch')
                allowed=plan['write_blocks']
                if any(i%SECTOR or not self.data['application_flash_offset']<=i<i+SECTOR<=self.data['application_flash_offset']+self.data['application_length']for i in allowed):raise InstallError('Invalid recovery write scope')
                # Accept a failed partial write only in the prior planned application sectors.
                for i in range(0,FLASH,SECTOR):
                    if i not in allowed and before[i:i+SECTOR]!=target[i:i+SECTOR]:raise InstallError('Current device differs outside the previous write plan; restoration refused')
                receipt={'restores_backup_sha256':patch.sha(target)}
                allowed=self.blocks(before,target)
            confirm=self.read_full(transport,run,'backup-confirm',30,20)
            if confirm!=before:raise InstallError('Two backup reads differ; no write is allowed')
            backup_sha=patch.sha(before)
            save_json(run/'backup-manifest.json',{'backup_sha256':backup_sha,'confirmed_second_read':True,'identity':identity})
            save_json(run/'plan.json',{'action':action,'variant':variant,'backup_sha256':backup_sha,'target_sha256':patch.sha(target),'write_blocks':allowed,'receipt':receipt,'boot_issued':False})
            save_bytes(run/'target-full.bin',target)
            for n,offset in enumerate(allowed):
                path=run/f'write-{offset:06x}.bin';save_bytes(path,target[offset:offset+SECTOR])
                transport.write(offset,path);self.progress(50+int(20*(n+1)/max(1,len(allowed))),'Writing application')
            after=self.read_full(transport,run,'readback-after',70,29)
            if after!=target:raise InstallError('Readback differs. Keep FEL mode and use the saved backup for recovery; no automatic retry.')
            result={'success':True,'action':action,'variant':variant,'full_flash_sha256':patch.sha(after),'backup_sha256':backup_sha,'blocks_written':len(allowed),'boot_issued':False,'identity':identity}
            save_json(run/'result.json',result);self.progress(100,'Verified successfully');return run,result
        except Exception as e:
            save_json(run/'error.json',{'success':False,'action':action,'error':str(e),'identity':identity,'boot_issued':False})
            raise InstallError(str(e)+'\nBackup and logs: '+str(run))from e
