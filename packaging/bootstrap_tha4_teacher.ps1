# dep-007: independent teacher inside the installation; no training.
param([Parameter(Mandatory=$true)][string]$PortableRoot,[string]$TeacherRoot='')
$ErrorActionPreference='Stop'
& (Join-Path $PSScriptRoot 'install_teacher_in_root.ps1') -PortableRoot $PortableRoot -TeacherRoot $TeacherRoot
if($LASTEXITCODE -ne 0) { throw 'Root-local teacher installation failed' }

# dep-007 / hotspot #6: do not leak robocopy 1 (successful copy) to callers.
exit 0
