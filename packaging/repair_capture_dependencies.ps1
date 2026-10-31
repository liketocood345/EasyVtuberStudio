param([Parameter(Mandatory=$true)][string]$PortableRoot)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
Initialize-LocalProcessEnvironment $PortableRoot
$python=& (Join-Path $PSScriptRoot 'resolve_portable_python.ps1') -PortableRoot $PortableRoot
if(-not $python -or -not(Test-LocalPython $PortableRoot $python)) { throw 'Install a folder-local runtime with DEPLOY first' }
$previousPreference=$ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    & $python -I -m pip uninstall -y onnx
    if($LASTEXITCODE -ne 0) { throw 'Cannot remove conflicting onnx package' }
} finally { $ErrorActionPreference=$previousPreference }
Install-LocalRequirements $PortableRoot $python (Join-Path $PortableRoot 'deps/pip/requirements-shell.txt')
& $python -I -m pip check
if($LASTEXITCODE -ne 0) { throw 'Capture dependency consistency check failed' }
