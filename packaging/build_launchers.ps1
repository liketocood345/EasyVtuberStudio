# dep-007 / hotspot #6: native thin entries use the installation's Python.
# PythonExe is retained for command-line compatibility; no runtime is bundled.
param([string]$RepoRoot=(Split-Path $PSScriptRoot -Parent),[string]$PythonExe='')
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'build_native_launchers.ps1') -RepoRoot $RepoRoot -MainAndCompatOnly
if($LASTEXITCODE -ne 0) { throw 'Native launcher build failed' }
