param([string]$ForkRoot='', [string]$OutputZip='', [string]$StageDir='', [string]$RuntimeSource='', [switch]$IncludeRuntime)
$ErrorActionPreference='Stop'
if($IncludeRuntime -or $RuntimeSource) { throw 'GitHub CORE never contains runtime. Build runtime modules separately.' }
if(-not $ForkRoot) { $ForkRoot=Split-Path $PSScriptRoot -Parent }
$ForkRoot=[IO.Path]::GetFullPath($ForkRoot)
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
Initialize-LocalProcessEnvironment $ForkRoot
$python=Join-Path $ForkRoot 'runtime/python310/python.exe'
if(-not(Test-LocalPython $ForkRoot $python)) { throw 'Run DEPLOY in the build source; system Python is forbidden.' }
if(-not $StageDir) { $StageDir=Join-Path $ForkRoot ('workspace/release/core-'+[Guid]::NewGuid().ToString('N')) }
if(-not $OutputZip) { $OutputZip=Join-Path $ForkRoot 'workspace/release/EasyVtuberStudio-CORE.zip' }
& $python -I (Join-Path $PSScriptRoot 'core_release.py') build --root $ForkRoot --stage $StageDir --output $OutputZip
if($LASTEXITCODE -ne 0) { throw 'CORE build or inventory verification failed' }
