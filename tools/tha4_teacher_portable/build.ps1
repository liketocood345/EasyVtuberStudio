# Maintainer-only thin EXE rebuild. Installation uses the shipped verified EXE.
$ErrorActionPreference='Stop'
$project=Get-Item -LiteralPath $PSScriptRoot
while($project -and -not(Test-Path -LiteralPath (Join-Path $project.FullName 'DEPLOY.bat'))) { $project=$project.Parent }
if(-not $project) { throw 'Teacher must remain inside the EVS project' }
& (Join-Path $project.FullName 'packaging/build_native_launchers.ps1') -RepoRoot $project.FullName -TeacherOnly
if($LASTEXITCODE -ne 0) { throw 'Thin teacher entry build failed' }
