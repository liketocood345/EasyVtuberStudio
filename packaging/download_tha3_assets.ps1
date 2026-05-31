param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$helper = Join-Path $PSScriptRoot "download_portable_assets.ps1"
if (-not (Test-Path $helper)) {
    throw "Missing download_portable_assets.ps1"
}

& $helper -PortableRoot $PortableRoot -OnlyAssetIds @("tha3_models")
