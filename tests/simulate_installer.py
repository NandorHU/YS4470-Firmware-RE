"""Make a temporary copy of the production installer with all native USB calls removed.
Run success and readback-corruption cases against a file-backed virtual16MiB flash.
"""
from pathlib import Path
import subprocess,json,os
import argparse
ap=argparse.ArgumentParser();ap.add_argument('bundle',type=Path);args=ap.parse_args()
diag=args.bundle.resolve();sim=diag/'simulation';sim.mkdir(exist_ok=True)
initial=bytearray((diag/'inputs/current-beta3.bin').read_bytes())
(sim/'initial.bin').write_bytes(initial)
diagnostic_initial=bytearray(initial);diagnostic_initial[:0x600000]=(diag/'candidate-region.bin').read_bytes();(sim/'diagnostic-initial.bin').write_bytes(diagnostic_initial)
source=(diag/'Install-V1.ps1').read_text(encoding='utf-8-sig')
expected_blocks=len(json.loads((diag/'build-manifest.json').read_text())['changed_sectors'])
fake=r'''
 function Run-Fel([string[]]$Command,[string]$Tag){
  switch($Command[0]){
   'spiflash-info' { 'Manufacturer: Winbond (EFh), model: 40h, size: 16777216 bytes.' | Set-Content -LiteralPath (Join-Path $Log ($Tag+'.stdout.txt')) }
   'spiflash-read' {
    $off=[Convert]::ToInt32($Command[1].Substring(2),16);$size=[Convert]::ToInt32($Command[2].Substring(2),16)
    if($script:Corrupt -and $Tag -like 'full-after-*' -and $off -eq 0){$script:Virtual[7]=$script:Virtual[7] -bxor 1}
    $part=New-Object byte[] $size;[Array]::Copy($script:Virtual,$off,$part,0,$size);[IO.File]::WriteAllBytes($Command[3],$part)
   }
   'spiflash-write' {
    $off=[Convert]::ToInt32($Command[1].Substring(2),16);$part=[IO.File]::ReadAllBytes($Command[2])
    if($off%0x10000 -ne 0 -or $part.Length -ne 0x10000){throw 'SIM: unsafe alignment'}
    [Array]::Copy($part,0,$script:Virtual,$off,$part.Length)
   }
   default {throw 'SIM: unexpected command'}
  }
 }
'''
start=source.index(' function Run-Fel(');end=source.index("\n Run-Fel @('spiflash-info')",start)
source=source[:start]+fake+source[end:]
source=source.replace('$listing=& $Fel --list 2>&1',"$global:LASTEXITCODE=0; $listing='USB device 001:019 Allwinner F1C100s'")
source=source.replace("$Log=Join-Path $PSScriptRoot ('run-'",f"$Log=Join-Path '{sim}' ('SIMULATION-'" )
source=source.replace('$PSScriptRoot',f"'{diag}'")
assert 'Start-Process' not in source and '& $Fel' not in source
inject=f"$script:Virtual=[IO.File]::ReadAllBytes('{sim/'initial.bin'}');$script:Corrupt=CORRUPTFLAG\n"
# Insert after param(...) and before executable statements, retaining the actual installer.
pos=source.index("$ErrorActionPreference='Stop'")
results=[]
env=os.environ.copy();env['PSMODULEPATH']=str(Path(env['SYSTEMROOT'])/'System32/WindowsPowerShell/v1.0/Modules')+';'+env.get('PSMODULEPATH','')
for name,corrupt in [('success','$false'),('restore-working','$false'),('readback-corrupt','$true')]:
 script=sim/(name+'.ps1');case_inject=inject.replace('CORRUPTFLAG',corrupt)
 if name=='restore-working':case_inject=case_inject.replace('initial.bin','diagnostic-initial.bin')
 script.write_text(source[:pos]+case_inject+source[pos:],encoding='utf-8-sig')
 run=subprocess.run(['powershell.exe','-NoProfile','-File',str(script),'-Action',('RestoreBeta3' if name=='restore-working' else 'InstallV1'),'-Approval','I_APPROVE_YS4470_V1'],capture_output=True,env=env)
 text=(run.stdout+run.stderr).decode('utf-8',errors='replace');(sim/(name+'.console.txt')).write_text(text,encoding='utf8')
 logs=sorted(sim.glob('SIMULATION-*'),key=lambda p:p.stat().st_mtime)
 log=logs[-1];result_path=log/('error.json' if corrupt=='$true' else 'result.json')
 result=json.loads(result_path.read_text(encoding='utf-8-sig'))
 if corrupt=='$false':
  assert run.returncode==0 and result['Success'] and result['BlocksWritten']==expected_blocks
  got=(log/'full-after.bin').read_bytes();expected=bytearray(initial);expected[:0x600000]=(diag/('previous-region.bin' if name=='restore-working' else 'candidate-region.bin')).read_bytes();assert got==expected
  assert '[100% osszesen]' in text
 else:
  assert run.returncode!=0 and not result['Success'] and result['Overall']<100
  assert '[100% osszesen]' not in text
  assert result['Phase']=='Bajtegyezes ellenorzese'
 results.append(dict(case=name,passed=True,exit_code=run.returncode,result=result,simulation_log=log.name))
(diag/'installer-simulation-tests.json').write_text(json.dumps(dict(passed=True,cases=results,scope='Actual production PowerShell control flow with native device enumeration/Run-Fel replaced in a temporary copy. File-backed virtual16MiB flash only, no USB calls. Success all expected aligned sectors, full readback match, injected readback corruption rejects success/100 percent.'),indent=2))
print('PASS: file-backed installer success and corrupted readback; no USB calls.')



