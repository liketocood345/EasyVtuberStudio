# dep-007: minimum environmental acceptance, never trains or evaluates motion/FPS.
param([string]$PortableRoot=(Split-Path $PSScriptRoot -Parent),[switch]$TeacherUi)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
$PortableRoot=[IO.Path]::GetFullPath($PortableRoot).TrimEnd('\')
Initialize-LocalProcessEnvironment $PortableRoot
$python=Join-Path $PortableRoot 'runtime/python310/python.exe'
if(-not(Test-LocalPython $PortableRoot $python)) { throw 'Root-local Python is missing; verification does not install it.' }
$report=Join-Path $PortableRoot 'workspace/validation/environment-current.json'
& $python -I (Join-Path $PSScriptRoot 'audit_installed_environments.py') --root $PortableRoot --output $report
if($LASTEXITCODE -ne 0) { throw 'Actual bound runtime/module/pip verification failed' }
# verify_full_install exits its own script scope, not this parent invocation.
& (Join-Path $PSScriptRoot 'verify_full_install.ps1') -PortableRoot $PortableRoot -Strict
if($LASTEXITCODE -ne 0) { throw 'Full resource and entry layout verification failed' }
$entry=Join-Path $PortableRoot 'addons/tha4_training/THA4Train.exe'
$arguments=@('--check-runtime')
if($TeacherUi) { $arguments+='--smoke-ui' }
foreach($argument in $arguments) {
    $process=Start-Process -FilePath $entry -ArgumentList $argument -WorkingDirectory $PortableRoot -WindowStyle Hidden -PassThru
    if(-not $process.WaitForExit(30000)) { throw ('Teacher entry timed out: '+$argument) }
    if($process.ExitCode -ne 0) { throw ('Teacher entry failed: '+$argument) }
}
Write-Host 'Environment baseline PASS. No training, motion comparison or FPS target was tested.'
