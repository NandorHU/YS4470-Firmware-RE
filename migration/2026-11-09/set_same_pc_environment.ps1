param([Parameter(Mandatory=$true)][string]$Inventory)
$ErrorActionPreference = 'Stop'
$inventoryData = Get-Content -LiteralPath $Inventory -Raw -Encoding UTF8 | ConvertFrom-Json
function Existing-InventoryPath([string]$Key) {
    $candidate = $inventoryData.paths.$Key.path
    if (-not $candidate -or -not (Test-Path -LiteralPath $candidate)) {
        throw "Missing inventoried path: $Key. Configure this machine explicitly."
    }
    return $candidate
}
$analysisPackages = Existing-InventoryPath 'analysis_packages'
$jpypePackages = Existing-InventoryPath 'jpype_packages'
$pyghidraPackages = Existing-InventoryPath 'pyghidra_packages'
$ghidraDirectory = Existing-InventoryPath 'ghidra'
$env:JAVA_HOME = Existing-InventoryPath 'java'
$env:PYTHONPATH = "$analysisPackages;$jpypePackages;$pyghidraPackages;$ghidraDirectory\Ghidra\Features\PyGhidra\pypkg\src"
$env:JAVA_TOOL_OPTIONS = "-Duser.home=$PWD\work\ghidra-profile"
$env:APPDATA = "$PWD\work\ghidra-profile\AppData\Roaming"
Write-Output 'Process-only analysis environment set. No model/device operation performed.'
