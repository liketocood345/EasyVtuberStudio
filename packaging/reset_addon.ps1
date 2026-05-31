param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [Parameter(Mandatory = $true)]
    [string]$AddonId,
    [switch]$Confirmed
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$record = Get-AddonRecord -Manifest $manifest -AddonId $AddonId
$folder = Get-AddonFolderAbsolute -PortableRoot $PortableRoot -AddonRecord $record

if (-not $Confirmed) {
    Write-Host "Use RESET_ADDON.bat or pass -Confirmed"
    exit 1
}

if (Test-Path $folder) {
    Write-Host "Removing $folder ..."
    Remove-Item -LiteralPath $folder -Recurse -Force
}

& (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot
Write-Host "Reset complete for $AddonId."
exit 0
