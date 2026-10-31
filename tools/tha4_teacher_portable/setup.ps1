param([switch]$SkipAssets)
$ErrorActionPreference='Stop'
$Root=[IO.Path]::GetFullPath($PSScriptRoot)
$InstallRoot=$Root
if((Split-Path (Split-Path $Root -Parent) -Leaf) -eq 'addons') {
    $candidate=Split-Path (Split-Path $Root -Parent) -Parent
    if(Test-Path -LiteralPath (Join-Path $candidate 'packaging/portable_environment.ps1')) { $InstallRoot=$candidate }
}
if($InstallRoot -eq $Root) { throw 'Install teacher under addons/tha4_training inside EVS; standalone runtimes are no longer built.' }
. (Join-Path $InstallRoot 'packaging/portable_environment.ps1')
Initialize-LocalProcessEnvironment $InstallRoot
Set-CommonRuntimeBindings $InstallRoot
$bound=Get-ComponentPythonExecutable $InstallRoot 'tha4_training' 'runtime/venvs/common/Scripts/python.exe'
$relative=(Split-Path (Split-Path $bound -Parent) -Parent).Substring($InstallRoot.TrimEnd('\').Length+1)
$python=New-LocalPythonEnvironment $InstallRoot $relative
Install-LockedRuntime $InstallRoot $python @('base','teacher')
if(-not $SkipAssets) {
    & (Join-Path $InstallRoot 'packaging/fetch_upstream_assets.ps1') -PortableRoot $InstallRoot -PackageIds @('tha4_teacher_training')
    if($LASTEXITCODE -ne 0) { throw 'Teacher assets unavailable' }
}
& $python -I (Join-Path $Root 'app/check_runtime.py') --root $Root
if($LASTEXITCODE -ne 0) { throw 'Teacher initialization failed' }
Write-Host 'Teacher uses shared common runtime with optional teacher extras; no training started.'

# dep-007 / hotspot #6: do not leak robocopy 1 (successful copy) to callers.
exit 0
