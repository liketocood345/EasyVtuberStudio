# dep-043: sync only a verified public CORE; never live workspace or whole dirs.
# Local only. Does not stage/commit/push. Existing target changes are preserved.
param([string]$DevRoot='', [string]$ForkRoot='', [string]$CoreRoot='')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'repo_paths.ps1')
$roots=Resolve-DevelopForkRoots -DevRoot $DevRoot -ForkRoot $ForkRoot
$DevRoot=$roots.DevRoot; $ForkRoot=$roots.ForkRoot
. (Join-Path $DevRoot 'packaging/portable_environment.ps1')
Initialize-LocalProcessEnvironment $DevRoot
$python=Join-Path $DevRoot 'runtime/python310/python.exe'
if(-not(Test-LocalPython $DevRoot $python)) { throw 'Folder-local build Python required' }
if(-not $CoreRoot) {
    $CoreRoot=Join-Path $DevRoot ('workspace/release/github-sync-'+[Guid]::NewGuid().ToString('N'))
    & (Join-Path $DevRoot 'packaging/build_github_zip.ps1') -ForkRoot $DevRoot -StageDir $CoreRoot -OutputZip ($CoreRoot+'.zip')
    if($LASTEXITCODE -ne 0) { throw 'Public CORE construction failed' }
}
& $python -I (Join-Path $DevRoot 'packaging/sync_core_to_github.py') --core $CoreRoot --target $ForkRoot
if($LASTEXITCODE -ne 0) { throw 'CORE-only GitHub synchronization failed; existing target changes were not overwritten' }
exit 0
