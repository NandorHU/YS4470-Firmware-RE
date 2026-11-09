param(
    [Parameter(Mandatory=$true)][string]$OllamaExe,
    [Parameter(Mandatory=$true)][string]$ModelDirectory,
    [Parameter(Mandatory=$true)][string]$StateDirectory
)
$ErrorActionPreference='Stop'
$llmExePath=(Resolve-Path -LiteralPath $OllamaExe).Path
$llmModelsPath=(Resolve-Path -LiteralPath $ModelDirectory).Path
$llmExpectedHash='544216ca2082b8bc19b4ba94b513f0098fa06774b232f3c140090e3449e322a5'
if((Get-FileHash -LiteralPath $llmExePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $llmExpectedHash){throw 'This recovery script only starts the already reviewed Ollama executable.'}
$llmSignature=Get-AuthenticodeSignature -LiteralPath $llmExePath
if($llmSignature.Status -ne 'Valid' -or $llmSignature.SignerCertificate.Subject -notmatch 'Ollama Inc.'){throw 'Expected valid Ollama publisher signature.'}
$llmExisting=$false
try{$llmHealth=Invoke-RestMethod 'http://127.0.0.1:11435/api/version' -TimeoutSec 2;$llmExisting=[bool]$llmHealth.version}catch{}
if(-not $llmExisting){
    # Avoid starting a competing instance of the same reviewed runtime when its
    # API is unhealthy; diagnose it instead. Never stop another process here.
    $llmMatching=@(Get-Process -Name ollama -ErrorAction SilentlyContinue | Where-Object {$_.Path -eq $llmExePath})
    if($llmMatching.Count){throw 'An instance of the reviewed runtime exists but its API is unavailable; no duplicate started.'}
    New-Item -ItemType Directory -Path $StateDirectory,(Join-Path $StateDirectory 'tmp') -Force | Out-Null
    $llmStatePath=(Resolve-Path -LiteralPath $StateDirectory).Path
    $env:OLLAMA_HOST='127.0.0.1:11435';$env:OLLAMA_MODELS=$llmModelsPath
    $env:OLLAMA_FLASH_ATTENTION='1';$env:OLLAMA_KV_CACHE_TYPE='q8_0'
    $env:OLLAMA_NUM_PARALLEL='1';$env:OLLAMA_MAX_LOADED_MODELS='1';$env:OLLAMA_NO_CLOUD='1'
    $env:OLLAMA_TMPDIR=Join-Path $llmStatePath 'tmp'
    $llmChild=Start-Process -FilePath $llmExePath -ArgumentList 'serve' -WorkingDirectory $llmStatePath -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $llmStatePath 'server.stdout.log') -RedirectStandardError (Join-Path $llmStatePath 'server.stderr.log')
    [pscustomobject]@{pid=$llmChild.Id;host='127.0.0.1:11435';executable_sha256=$llmExpectedHash} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $llmStatePath 'launch-receipt.json') -Encoding utf8
}
for($llmPoll=0;$llmPoll -lt 20;$llmPoll++){
    try{$llmHealth=Invoke-RestMethod 'http://127.0.0.1:11435/api/version' -TimeoutSec 2;if($llmHealth.version){break}}catch{}
    Start-Sleep -Milliseconds 500
}
if($llmHealth.version -ne '0.40.15'){throw 'Expected reviewed Ollama version0.40.15.'}
$llmModels=Invoke-RestMethod 'http://127.0.0.1:11435/api/tags' -TimeoutSec 5
$llmCoder=@($llmModels.models | Where-Object {$_.name -eq 'qwen2.5-coder:14b'})
if($llmCoder.Count -ne 1 -or $llmCoder[0].digest -ne '9ec8897f747e246e970bc5cfdda85d22f1123dc2e3d34978a010a75968716849'){throw 'Expected existing pinned coder model; no model download is attempted.'}
[pscustomobject]@{version=$llmHealth.version;already_running=$llmExisting;model=$llmCoder[0].name;digest=$llmCoder[0].digest;cloud_disabled_when_started=$true;bound_address_when_started='127.0.0.1:11435'} | ConvertTo-Json
