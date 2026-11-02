param(
 [Parameter(Mandatory=$true)][ValidateSet('InstallV1','RestoreBeta3')][string]$Action,
 [Parameter(Mandatory=$true)][string]$Approval,
 [switch]$ValidateOnly
)
$ErrorActionPreference='Stop'
if($Approval -cne 'I_APPROVE_YS4470_V1'){throw 'A bootloader es firmware 1.0 irasahoz kulon jovahagyas szukseges.'}
$Root=$PSScriptRoot
$Fel=Join-Path $Root 'tools/sunxi-fel.exe'
$Reference=Join-Path $Root 'inputs/current-beta3.bin'
$PinnedFel='da14ffa7243767d9c8c5579618171fde2956c4b37b82139bb519932aba6e9375'
$PinnedBackup='2ce9c1693a9726a2fe042620debd7705e77cfec58d98e8729bb6ec1ade4a9d0f'
$PinnedDiagnostic='TARGET_REGION_HASH'
$PinnedWorking='aaf72639ebbc6e3e92e00306fd7a90bba6fb676bcb762370005c7163847849f3'
$script:Phase='Eloellenorzes';$script:Overall=0;$Log=$null
function Show-Stage([string]$Name,[int]$Part,[int]$Total,[string]$Detail='') {
 $script:Phase=$Name;$script:Overall=$Total
 Write-Progress -Activity 'YS-4470 firmware' -Status "$Name | szakasz: $Part% | osszesen: $Total% | $Detail" -PercentComplete $Total
 Write-Host ('[{0,3}% osszesen] {1}: {2}% - {3}' -f $Total,$Name,$Part,$Detail)
}
function Hash-File([string]$Path){(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()}
function Hash-Region([byte[]]$Bytes){
 $sha=[Security.Cryptography.SHA256]::Create()
 try{([BitConverter]::ToString($sha.ComputeHash($Bytes,0,0x600000))).Replace('-','').ToLowerInvariant()}finally{$sha.Dispose()}
}
try {
 Show-Stage 'Eloellenorzes' 0 0 'Helyi fajlok, meretek es SHA-256'
 if((Hash-File $Fel) -ne $PinnedFel -or (Hash-File $Reference) -ne $PinnedBackup){throw 'Az eszkoz vagy az eredeti teljes mentes hash-e nem egyezik.'}
 $DiagPath=Join-Path $PSScriptRoot 'candidate-region.bin';$WorkingPath=Join-Path $PSScriptRoot 'previous-region.bin'
 if((Get-Item -LiteralPath $DiagPath).Length -ne 0x600000 -or (Hash-File $DiagPath) -ne $PinnedDiagnostic){throw 'Diagnosztikai regio hash/meret hiba'}
 if((Get-Item -LiteralPath $WorkingPath).Length -ne 0x600000 -or (Hash-File $WorkingPath) -ne $PinnedWorking){throw 'Mukodo regio hash/meret hiba'}
 $target=if($Action -eq 'InstallV1'){[IO.File]::ReadAllBytes($DiagPath)}else{[IO.File]::ReadAllBytes($WorkingPath)}
 $targetHash=if($Action -eq 'InstallV1'){$PinnedDiagnostic}else{$PinnedWorking}
 if($ValidateOnly){Write-Host 'Helyi ellenorzes sikeres. USB-muvelet es flash-iras nem tortent.';return}
 $Log=Join-Path $PSScriptRoot ('run-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
 New-Item -ItemType Directory -Path $Log | Out-Null
 $listing=& $Fel --list 2>&1
 if($LASTEXITCODE -ne 0){throw "FEL felsorolas hiba: $LASTEXITCODE"}
 $listing | Set-Content -LiteralPath (Join-Path $Log 'devices.txt')
 $devices=@($listing | Where-Object {"$_" -match '^USB device\s+\d+:\d+'})
 if($devices.Count -ne 1 -or "$($devices[0])" -notmatch '^USB device\s+(\d+:\d+)\s+Allwinner F1C100s\s*$'){throw 'Pontosan egy FEL modban levo F1C100s szukseges.'}
 $Bus=$Matches[1]
 function Run-Fel([string[]]$Command,[string]$Tag){
  $quoted=@('-d',$Bus)+$Command | ForEach-Object {if($_ -match '["\r\n]'){throw 'Ervenytelen argumentum'};'"'+$_+'"'}
  $p=Start-Process -FilePath $Fel -ArgumentList ($quoted -join ' ') -WindowStyle Hidden -Wait -PassThru -RedirectStandardOutput (Join-Path $Log ($Tag+'.stdout.txt')) -RedirectStandardError (Join-Path $Log ($Tag+'.stderr.txt'))
  if($p.ExitCode -ne 0){throw "FEL hiba: $Tag, kod: $($p.ExitCode). Maradjon FEL modban; ne ismeteld vakon."}
 }
 Run-Fel @('spiflash-info') 'flash-info'
 $info=Get-Content -LiteralPath (Join-Path $Log 'flash-info.stdout.txt') -Raw
 if($info -notmatch 'Manufacturer: Winbond \(EFh\), model: 40h, size: 16777216 bytes\.'){throw 'Varatlan flash-azonosito vagy kapacitas'}
 Show-Stage 'Eloellenorzes' 100 5 'F1C100s, 16 MiB Winbond ellenorizve'
 function Read-Full([string]$Name,[int]$StartPercent,[int]$Weight,[string]$Stage){
  $path=Join-Path $Log ($Name+'.bin');$stream=[IO.File]::Open($path,[IO.FileMode]::CreateNew)
  try{
   for($offset=0;$offset -lt 0x1000000;$offset+=0x40000){
    $part=[int](100*$offset/0x1000000);$total=$StartPercent+[int]($Weight*$offset/0x1000000)
    Show-Stage $Stage $part $total ('Blokkonkent mert haladas; az aktualis 256 KiB blokk belseje nem merheto. Cim: 0x{0:x}' -f $offset)
    $chunk=Join-Path $Log ('{0}-{1:x6}.bin' -f $Name,$offset)
    Run-Fel @('spiflash-read',('0x{0:x}' -f $offset),'0x40000',$chunk) ('{0}-{1:x6}' -f $Name,$offset)
    $bytes=[IO.File]::ReadAllBytes($chunk)
    if($bytes.Length -ne 0x40000){throw "Hianyos olvasas: $chunk"}
    $stream.Write($bytes,0,$bytes.Length);$stream.Flush()
   }
  }finally{$stream.Dispose()}
  Show-Stage $Stage 100 ($StartPercent+$Weight) 'A teljes 16 MiB olvasas befejezodott'
  return $path
 }
 $beforePath=Read-Full 'full-before' 5 25 'Teljes mentes'
 $before=[IO.File]::ReadAllBytes($beforePath);$referenceBytes=[IO.File]::ReadAllBytes($Reference)
 Show-Stage 'Mentes ellenorzese' 0 30 'Celeszkoz allapotanak ellenorzese'
 $beforeHash=Hash-Region $before
 if($beforeHash -ne $PinnedWorking -and $beforeHash -ne $PinnedDiagnostic){throw 'A celregio sem a mukodo, sem a diagnosztikai kep. Iras nem indul; kulon helyreallitasi vizsgalat kell.'}
 if(-not ('YS4470Compare' -as [type])){Add-Type 'public static class YS4470Compare { public static int FirstDiff(byte[] a, byte[] b, int off, int count) { for(int i=off;i<off+count;i++) if(a[i]!=b[i]) return i; return -1; } }'}
 $bad=[YS4470Compare]::FirstDiff($before,$referenceBytes,0x600000,0xa00000)
 if($bad -ge 0){throw ('A celregion kivuli adat elter: 0x{0:x}. Iras nem tortent.' -f $bad)}
 $expected=[byte[]]$before.Clone();[Array]::Copy($target,0,$expected,0,$target.Length)
 $blocks=@()
 for($offset=0;$offset -lt 0x600000;$offset+=0x10000){
  if([YS4470Compare]::FirstDiff($before,$expected,$offset,0x10000) -ge 0){$blocks+=$offset}
 }
 $allowed=@(ALLOWED_SECTORS)
 if(@($blocks | Where-Object {$_ -notin $allowed}).Count -gt 0){throw 'Varatlan modosulasi blokk; iras nem indul.'}
 [pscustomobject]@{Action=$Action;BeforeRegionSHA256=$beforeHash;TargetRegionSHA256=$targetHash;Blocks=$blocks;FreshFullBackupSHA256=(Hash-File $beforePath);BootIssued=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Log 'plan.json')
 Show-Stage 'Mentes ellenorzese' 100 40 ('Ellenorzott teljes mentes; modosulo blokkok: '+$blocks.Count)
 for($index=0;$index -lt $blocks.Count;$index++){
  $offset=$blocks[$index];$chunk=Join-Path $Log ('write-{0:x6}.bin' -f $offset);$bytes=New-Object byte[] 0x10000
  [Array]::Copy($expected,$offset,$bytes,0,0x10000);[IO.File]::WriteAllBytes($chunk,$bytes)
  Show-Stage 'Firmware-iras' ([int](100*$index/$blocks.Count)) (40+[int](20*$index/$blocks.Count)) ('A kesz 64 KiB blokkok szerint; az aktualis blokk belseje nem merheto. Cim: 0x{0:x}' -f $offset)
  Run-Fel @('spiflash-write',('0x{0:x}' -f $offset),$chunk) ('write-{0:x6}' -f $offset)
  Show-Stage 'Firmware-iras' ([int](100*($index+1)/$blocks.Count)) (40+[int](20*($index+1)/$blocks.Count)) 'Blokk irasa visszatert; teljes visszaellenorzes meg hatravan'
 }
 Show-Stage 'Firmware-iras' 100 60 'Teljes visszaolvasas kovetkezik; ne huzd ki'
 $afterPath=Read-Full 'full-after' 60 30 'Teljes visszaolvasas'
 $after=[IO.File]::ReadAllBytes($afterPath)
 for($offset=0;$offset -lt 0x1000000;$offset+=0x40000){
  Show-Stage 'Bajtegyezes ellenorzese' ([int](100*$offset/0x1000000)) (90+[int][Math]::Floor(10*$offset/0x1000000)) ('Ellenorzes: 0x{0:x}' -f $offset)
  $bad=[YS4470Compare]::FirstDiff($after,$expected,$offset,0x40000)
  if($bad -ge 0){throw ('Visszaellenorzesi hiba: 0x{0:x}. Maradjon FEL modban; naplok megorzendoek.' -f $bad)}
 }
 if((Hash-Region $after) -ne $targetHash){throw 'Vegso regio SHA-256 hiba'}
 [pscustomobject]@{Success=$true;Action=$Action;FullFlashSHA256=(Hash-File $afterPath);RegionSHA256=$targetHash;BlocksWritten=$blocks.Count;Timestamp=(Get-Date -Format o);BootIssued=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Log 'result.json')
 Show-Stage 'Kesz, teljes visszaellenorzes sikeres' 100 100 '16 MiB bajtegyezes. Ujrainditas nem tortent.'
 Write-Host "Naplo es friss teljes mentes: $Log"
}catch{
 $message=$_ | Out-String
 if($Log){[pscustomobject]@{Success=$false;Phase=$script:Phase;Overall=$script:Overall;Error=$message;BootIssued=$false} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $Log 'error.json')}
 Write-Host "HIBA | fazis: $script:Phase | osszesen: $script:Overall% | naplo: $Log`n$message" -ForegroundColor Red
 throw
}


