param([Parameter(Mandatory=$true)][string]$NodeDirectory)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$prefix=Join-Path $root 'work/local-llm-tools'
$node=Join-Path $NodeDirectory 'node.exe';$npm=Join-Path $NodeDirectory 'npm.cmd'
if(-not(Test-Path -LiteralPath $node)){throw 'Supply an existing Node >=22.22 directory'}
$nodeVersion=[version]((& $node -p 'process.versions.node'))
if($nodeVersion -lt [version]'22.22.0'){throw 'Node >=22.22 required'}
New-Item -ItemType Directory -Path $prefix -Force | Out-Null
if(-not(Test-Path -LiteralPath (Join-Path $prefix 'python/Scripts/python.exe'))){
  python -m venv (Join-Path $prefix 'python')
  if($LASTEXITCODE){throw 'venv creation failed'}
}
& (Join-Path $prefix 'python/Scripts/python.exe') -m pip install -r (Join-Path $PSScriptRoot 'requirements.lock.txt')
if($LASTEXITCODE){throw 'pip install failed'}
New-Item -ItemType Directory -Path (Join-Path $prefix 'node') -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'package.json') -Destination (Join-Path $prefix 'node/package.json')
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'package-lock.json') -Destination (Join-Path $prefix 'node/package-lock.json')
& $npm ci --prefix (Join-Path $prefix 'node') --no-audit --no-fund
if($LASTEXITCODE){throw 'npm install failed'}
# No global installation, new model weights, service, driver or firmware changes.
