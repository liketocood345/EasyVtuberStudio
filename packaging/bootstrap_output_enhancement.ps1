# dep-024/025, f-055/056: verify the canonical module path, not legacy data/.
param([Parameter(Mandatory=$true)][string]$PortableRoot)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'addon_paths.ps1')
. (Join-Path $PSScriptRoot 'deploy_common.ps1')
$PortableRoot=Resolve-PortableRoot $PortableRoot
Initialize-DeploySession $PortableRoot
& (Join-Path $PSScriptRoot 'fetch_upstream_assets.ps1') -PortableRoot $PortableRoot -PackageIds @('ezvtb_nn_weights')
if($LASTEXITCODE -ne 0) { throw 'NN module integrity verification failed' }
$seen=@{}; $installed=0
foreach($role in @('app','basic_run','face_puppeteer','tha3_models')) {
    $python=Get-ComponentPythonExecutable $PortableRoot $role 'runtime/venvs/common/Scripts/python.exe'
    if(-not(Test-Path -LiteralPath $python) -or $seen.ContainsKey($python.ToLowerInvariant())) { continue }
    $seen[$python.ToLowerInvariant()]=$true
    if(-not(Test-LocalPython $PortableRoot $python)) { throw 'External NN runtime rejected' }
    Install-LockedRuntime $PortableRoot $python @('base','output')
    if(-not(Test-OutputEnhancementPipImports $python) -or -not(Test-OrtHasDirectML $python)) { throw 'NN/DirectML initialization failed' }
    $installed++
}
if(-not $installed) { throw 'Install a local base runtime before output enhancement' }
$addonRoot=Join-Path $PortableRoot 'addons/output_enhancement'
Set-Content -LiteralPath (Join-Path $addonRoot '.installed') -Value (Get-Date -Format o) -Encoding UTF8
Write-Host '[OK] NN canonical addon module and DirectML runtime verified.'
exit 0
