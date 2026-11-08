param([ValidateSet('versions','promptfoo','dspy','rea')][string]$Task='versions')
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$prefix=Join-Path $root 'work/local-llm-tools'
$machine=Get-Content -LiteralPath (Join-Path $prefix 'machine.json') -Raw | ConvertFrom-Json
$env:PROMPTFOO_CONFIG_DIR=Join-Path $prefix 'promptfoo-config'
$env:PROMPTFOO_DISABLE_TELEMETRY='true';$env:PROMPTFOO_DISABLE_UPDATE='true'
$env:OLLAMA_BASE_URL='http://127.0.0.1:11435';$env:NO_PROXY='127.0.0.1,localhost';$env:REQUEST_TIMEOUT_MS='30000'
$py=Join-Path $prefix 'python/Scripts/python.exe'
$cli=Join-Path $prefix 'node/node_modules/promptfoo/dist/src/entrypoint.js'
Push-Location $root
try {
  switch($Task){
    'versions'{& $machine.node $cli --version; & $py -c 'import importlib.metadata as m; print({p:m.version(p) for p in ("dspy","mcp")})'}
    'dspy'{& $py (Join-Path $PSScriptRoot 'evaluate_dspy.py')}
    'rea'{& $py (Join-Path $PSScriptRoot 'rea_gateway.py')}
    'promptfoo'{
      $out=Join-Path $prefix 'promptfoo-results.json'
      if(Test-Path -LiteralPath $out){throw 'Completed responses exist; regrade them or prepare a new owned manifest'}
      & $machine.node $cli eval -c (Join-Path $PSScriptRoot 'promptfooconfig.json') -j 1 --no-cache --no-progress-bar --no-table --no-share --no-write -o $out
    }
  }
} finally {Pop-Location}
