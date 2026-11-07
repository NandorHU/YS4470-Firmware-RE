param([string]$Destination = (Join-Path (Get-Location) 'references/f1c100s'))
$ErrorActionPreference = 'Stop'
$pins = @(
    @('mikljohansson/fnirsi-1013d-mcp','fa8377b2b1d148f8596a8befe638df79062c2bd8'),
    @('nminaylov/F1C100s_projects','c11422e99c9f33e8419a5ac4dcab6684c8d38296'),
    @('nminaylov/F1C100s_info','ec42b9b4147070b4277e86d12324d5cd0662cd1a'),
    @('minilogic/f1c_nonos','73933dbb56d2cbdeb1f260a484bb7c525866616f')
)
New-Item -ItemType Directory -Force -Path $Destination | Out-Null
foreach ($pin in $pins) {
    $repo, $revision = $pin
    $target = Join-Path $Destination ($repo.Replace('/','__'))
    if (-not (Test-Path -LiteralPath $target)) {
        git init -q $target
        if ($LASTEXITCODE) { throw "git init failed: $repo" }
        git -C $target remote add origin "https://github.com/$repo.git"
        if ($LASTEXITCODE) { throw "git remote failed: $repo" }
    }
    $origin = git -C $target remote get-url origin
    if ($origin -ne "https://github.com/$repo.git") { throw "Unexpected origin: $target" }
    $changes = git -C $target status --porcelain
    if ($changes) { throw "Refusing to replace modified reference files: $target" }
    git -C $target config core.autocrlf false
    if ($LASTEXITCODE) { throw "git line-ending configuration failed: $repo" }
    git -C $target fetch --depth=1 origin $revision
    if ($LASTEXITCODE) { throw "git fetch failed: $repo" }
    git -C $target checkout --detach $revision
    if ($LASTEXITCODE) { throw "git checkout failed: $repo" }
    # The worktree was checked clean above. Re-materialize canonical LF bytes
    # when an existing checkout inherited a global autocrlf=true setting.
    git -C $target checkout-index --force --all
    if ($LASTEXITCODE) { throw "git canonical checkout failed: $repo" }
    $actual = git -C $target rev-parse HEAD
    if ($actual -ne $revision) { throw "Wrong revision: $repo" }
    [PSCustomObject]@{ repository=$repo; commit=$actual; path=$target }
}
