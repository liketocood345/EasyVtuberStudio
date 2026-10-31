# dep-007 / hotspot #6: complete private baseline; merge experiments follow separately.
param([Parameter(Mandatory=$true)][string]$PortableRoot,[string]$TeacherRoot='')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
$PortableRoot=[IO.Path]::GetFullPath($PortableRoot).TrimEnd('\')
if(-not $TeacherRoot) { $TeacherRoot=Join-Path $PortableRoot 'addons/tha4_training' }
$TeacherRoot=Assert-LocalChild $PortableRoot $TeacherRoot
if($TeacherRoot -ne (Join-Path $PortableRoot 'addons/tha4_training')) { throw 'Teacher must use addons/tha4_training within this installation' }
$active=@(Get-CimInstance Win32_Process | Where-Object { ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($TeacherRoot+'\',[StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.Contains($TeacherRoot+'\app\')) })
if($active.Count) { throw 'Close this installation teacher before updating it' }
$kit=Join-Path $PortableRoot 'tools/tha4_teacher_portable'
New-Item -ItemType Directory -Force -Path $TeacherRoot | Out-Null
# Never copy runtime, jobs or caches from a source kit/old standalone installation.
& robocopy.exe $kit $TeacherRoot /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD workspace runtime src _internal release __pycache__ /XF '*.pyc' | Out-Host
if($LASTEXITCODE -ge 8) { throw 'Cannot install teacher shell sources' }
$teacherSrc=Join-Path $TeacherRoot 'src/tha4'
New-Item -ItemType Directory -Force -Path $teacherSrc | Out-Null
& robocopy.exe (Join-Path $PortableRoot 'src/tha4') $teacherSrc /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD __pycache__ /XF '*.pyc' | Out-Host
if($LASTEXITCODE -ge 8) { throw 'Cannot bind teacher THA4 source' }
$bindingsPath=Join-Path $PortableRoot 'runtime/bindings/components.json'
Set-CommonRuntimeBindings $PortableRoot
# Source kit and weights use one versioned module contract. This also repairs
# partially installed teacher assets before adding its optional shared extras.
& (Join-Path $PSScriptRoot 'fetch_upstream_assets.ps1') -PortableRoot $PortableRoot -PackageIds @('tha4_teacher_training')
if($LASTEXITCODE -ne 0) { throw 'Teacher resource contract failed' }
& (Join-Path $TeacherRoot 'setup.ps1') -SkipAssets
if($LASTEXITCODE -ne 0) { throw 'Teacher shared environment setup failed' }
if(-not(Test-Path -LiteralPath (Join-Path $TeacherRoot 'THA4Train.exe'))) { throw 'Teacher entry absent' }
$bindings=Get-Content -LiteralPath $bindingsPath -Raw | ConvertFrom-Json
$python=Join-Path $PortableRoot $bindings.components.tha4_training.python
if(-not(Test-LocalPython $PortableRoot $python)) { throw 'Teacher interpreter escaped installation' }
& $python -I (Join-Path $TeacherRoot 'app/check_runtime.py') --root $TeacherRoot --report (Join-Path $PortableRoot 'workspace/tools/tha4_training/install_probe.json')
if($LASTEXITCODE -ne 0) { throw 'Teacher installation probe failed' }
Write-Host "Root-local teacher ready: $TeacherRoot\THA4Train.exe (no training started)"

# dep-007 / hotspot #6: do not leak robocopy 1 (successful copy) to callers.
exit 0
