"""Windows GUI with a replaceable, external YS-4470 firmware package."""
from __future__ import annotations
import argparse,json,os,queue,subprocess,sys,threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from engine import Engine,FelTransport,save_bytes,save_json,patch
from firmware_package import read_package
VERSION='2.0.0-beta.1'
ZADIG_SHA='4ecaa95df3da3621486a043aef8b3050b8bafe7c901402871e816229ef82039b'
def resources():return Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parents[1]/'work/easy-installer/resources'))
def portable_folder():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]

def user_root():
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'YS4470 Installer'
    return Path.home()/'.ys4470-installer'
def self_test(package_path=None):
    from engine import FEL_SHA
    root=resources();patch.load_patch(root/'patch-data.json')
    assert patch.sha((root/'tools/sunxi-fel.exe').read_bytes())==FEL_SHA
    assert patch.sha((root/'tools/zadig-2.9.exe').read_bytes())==ZADIG_SHA
    interpreter=tk.Tcl()
    result = {'version':VERSION,'resources_valid':True,'tcl_patchlevel':interpreter.eval('info patchlevel'),
              'device_access':False}
    if package_path:
        result['external_firmware'] = read_package(package_path).manifest()
    return result
class App:
    def __init__(self,window):
        self.window=window;self.root=resources();self.data=patch.load_patch(self.root/'patch-data.json')
        self.events=queue.Queue();self.busy=False
        self.firmware_path = portable_folder() / 'firmware' / 'firmware.ysfw'
        window.title('YS-4470 Firmware Installer '+VERSION);window.geometry('700x490');window.minsize(640,460)
        frame=ttk.Frame(window,padding=22);frame.pack(fill='both',expand=True)
        ttk.Label(frame,text='YS-4470 Firmware Installer',font=('Segoe UI',18,'bold')).pack(anchor='w')
        ttk.Label(frame,text='Replace firmware/firmware.ysfw beside the installer, or select another firmware package. No Python setup is required.',wraplength=630).pack(anchor='w',pady=(6,10))
        self.firmware_label = tk.StringVar()
        self.describe_package()
        ttk.Label(frame,textvariable=self.firmware_label,wraplength=630).pack(anchor='w',pady=(0,10))
        self.buttons=[]
        for label,command in [('1. Choose firmware package…',self.choose_package),('2. Install selected firmware in FEL mode',self.install),('USB driver setup (only if detection fails)',self.driver),('Restore from an automatic backup',self.restore)]:
            b=ttk.Button(frame,text=label,command=command);b.pack(fill='x',pady=4);self.buttons.append(b)
        self.status=tk.StringVar(value='Ready. For installation: connect one YS-4470 in FEL mode using a USB data cable.')
        ttk.Label(frame,textvariable=self.status,wraplength=630).pack(anchor='w',pady=(18,8))
        self.bar=ttk.Progressbar(frame,maximum=100);self.bar.pack(fill='x')
        ttk.Label(frame,text='Installation automatically creates and confirms a full backup, changes only guarded application sectors, then verifies a full readback. This beta installer has not been physically tested.',wraplength=630).pack(anchor='w',pady=(12,0))
        window.protocol('WM_DELETE_WINDOW',self.close);window.after(100,self.poll)
    def close(self):
        if self.busy:messagebox.showinfo('Operation in progress','Wait for the operation to finish. Do not disconnect the meter.')
        else:self.window.destroy()
    def describe_package(self):
        try:
            package = read_package(self.firmware_path)
        except Exception as e:
            self.firmware_label.set(f'No usable firmware package selected. {e}')
        else:
            self.firmware_label.set(f'Selected: {package.label} · {package.family} · {self.firmware_path.name}')

    def choose_package(self):
        name = filedialog.askopenfilename(title='Choose YS-4470 firmware package',
                                         initialdir=str(self.firmware_path.parent),
                                         filetypes=[('YS-4470 firmware package','*.ysfw')])
        if name:
            self.firmware_path = Path(name)
            self.describe_package()
    def engine(self):
        return Engine(self.data,user_root()/'backups',lambda run:FelTransport(self.root/'tools/sunxi-fel.exe',run),lambda value,text:self.events.put(('progress',value,text)))
    def start(self,operation):
        if self.busy:return
        self.busy=True;self.bar['value']=0
        for b in self.buttons:b.state(['disabled'])
        def work():
            try:self.events.put(('done',operation()))
            except Exception as e:self.events.put(('error',str(e)))
        threading.Thread(target=work,daemon=False).start()
    def install(self):
        try:
            firmware = read_package(self.firmware_path)
        except Exception as e:
            messagebox.showerror('Firmware package rejected', str(e))
            return
        detail = (f'Install {firmware.label} ({firmware.family}) on the connected YS-4470?\n'
                  f'SHA-256: {firmware.image_sha256}\n\n'
                  'A complete backup is saved and confirmed before any write. Keep USB and power stable until full readback verification finishes.')
        if messagebox.askyesno('Install application firmware', detail):
            self.start(lambda:self.engine().install_package(firmware,approved=True))
    def restore(self):
        name=filedialog.askopenfilename(title='Select automatic backup-before.bin',initialdir=str(user_root()/'backups'),filetypes=[('Automatic backup','backup-before.bin')])
        if name and messagebox.askyesno('Restore application','Restore this verified automatic backup? The device must still match outside the original write plan.'):
            self.start(lambda:self.engine().restore(name,approved=True))
    def driver(self):
        source=self.root/'tools/zadig-2.9.exe'
        try:
            if patch.sha(source.read_bytes())!=ZADIG_SHA:raise RuntimeError('Driver helper integrity failed')
            if not messagebox.askokcancel('USB driver setup','The included official Zadig helper will open.\n\nSelect ONLY the FEL device with USB ID 1F3A:EFE8, choose WinUSB, and click Install Driver. Do not replace drivers for other devices. Windows may request administrator approval. Close Zadig and retry installation when finished.'):return
            # No silent certificate install, driver replacement or approval bypass.
            folder=user_root()/'driver-helper';folder.mkdir(parents=True,exist_ok=True)
            target=folder/source.name
            if target.exists()and patch.sha(target.read_bytes())!=ZADIG_SHA:raise RuntimeError('Existing driver helper was modified')
            if not target.exists():save_bytes(target,source.read_bytes())
            if os.name!='nt':raise RuntimeError('USB driver setup is available on Windows only')
            os.startfile(str(target),'runas',cwd=str(folder))
        except Exception as e:messagebox.showerror('Driver setup failed',str(e))
    def poll(self):
        try:
            while True:
                event=self.events.get_nowait()
                if event[0]=='progress':self.bar['value']=event[1];self.status.set(event[2])
                elif event[0]in('done','error'):
                    self.busy=False
                    for b in self.buttons:b.state(['!disabled'])
                    if event[0]=='done':
                        folder,result=event[1];self.status.set('Verified successfully. Backup: '+str(folder))
                        messagebox.showinfo('Verified successfully','Full readback matches. No reset was issued. You may now power-cycle the meter.\n\nBackup and logs:\n'+str(folder))
                    else:self.status.set('Stopped: '+event[1]);messagebox.showerror('Operation stopped',event[1])
        except queue.Empty:pass
        self.window.after(100,self.poll)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--self-test-report',type=Path);ap.add_argument('--firmware-package',type=Path);args=ap.parse_args()
    if args.self_test_report:
        save_json(args.self_test_report,self_test(args.firmware_package));return
    root=tk.Tk()
    try:App(root)
    except Exception as e:messagebox.showerror('Package integrity failed',str(e));root.destroy();return
    root.mainloop()
if __name__=='__main__':main()
