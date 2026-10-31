param([Parameter(Mandatory=$true)][string]$PortableRoot,[switch]$MouseStudentOnly)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
$python=Get-LocalPythonBase ([IO.Path]::GetFullPath($PortableRoot))
@{command=$python;source='portable'} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $PortableRoot 'workspace/.python310_cmd.json') -Encoding UTF8
Write-Host "Folder-local Python ready: $python"
