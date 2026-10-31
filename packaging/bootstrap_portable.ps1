param([string]$PortableRoot='', [switch]$Quiet, [switch]$ForceRebuildRuntime,
      [switch]$MouseStudentOnly, [switch]$Tha3Only)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'addon_paths.ps1')
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
if(-not $PortableRoot) { $PortableRoot=Join-Path $PSScriptRoot '..' }
$PortableRoot=Resolve-PortableRoot $PortableRoot
if($Tha3Only) { $relative='runtime/venvs/common'; $requirements=@('requirements-mouse-student.txt','requirements-tha3-pytorch.txt','requirements-tha3-ort.txt') }
elseif($MouseStudentOnly) { $relative='runtime/venvs/common'; $requirements=@('requirements-mouse-student.txt') }
else { $relative='runtime/venvs/common'; $requirements=@('requirements-common.txt','requirements-tha4-student.txt') }
$component=if($Tha3Only) { 'tha3_models' } elseif($MouseStudentOnly) { 'basic_run' } else { 'face_puppeteer' }
$bound=Get-ComponentPythonExecutable $PortableRoot $component ($relative+'/Scripts/python.exe')
$relative=(Split-Path (Split-Path $bound -Parent) -Parent).Substring($PortableRoot.TrimEnd('\').Length+1)
$python=New-LocalPythonEnvironment $PortableRoot $relative -Force:$ForceRebuildRuntime
$profiles=@('base'); if(-not $MouseStudentOnly) { $profiles+='face' }; if($Tha3Only) { $profiles+='output' }
Install-LockedRuntime $PortableRoot $python $profiles
Set-CommonRuntimeBindings $PortableRoot
# Relative .pth entries keep source imports local without global PYTHONPATH or
# a Poetry/system environment. THA3's package link is shipped with the bundle.
$mode=if($Tha3Only){'tha3'}elseif($MouseStudentOnly){'student'}else{'face'}
& $python -I (Join-Path $PSScriptRoot 'probe_portable_runtime.py') --root $PortableRoot --mode $mode --configure-sources
if($LASTEXITCODE -ne 0) { throw 'Cannot write folder-local source paths' }
& $python -I -m pip check
if($LASTEXITCODE -ne 0) { throw "Dependency consistency check failed: $relative" }
& $python -I (Join-Path $PSScriptRoot 'probe_portable_runtime.py') --root $PortableRoot --mode $mode --report (Join-Path $PortableRoot "workspace/diagnostics/runtime-$mode.json")
if($LASTEXITCODE -ne 0) { throw "Local runtime import check failed: $relative" }
Set-Content -LiteralPath (Join-Path $PortableRoot 'workspace/.portable_bootstrap_done') -Value (Get-Date -Format o) -Encoding UTF8
Write-Host "Portable environment ready: $relative; Python base and dependencies stay inside $PortableRoot"

# dep-007 / hotspot #6: do not leak robocopy 1 (successful copy) to callers.
exit 0
