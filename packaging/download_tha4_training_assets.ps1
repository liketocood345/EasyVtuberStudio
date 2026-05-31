param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$helper = Join-Path $PSScriptRoot "fetch_upstream_assets.ps1"
if (-not (Test-Path $helper)) {
    throw "Missing fetch_upstream_assets.ps1"
}

& $helper -PortableRoot $PortableRoot -PackageIds @("tha4_teacher_training")
