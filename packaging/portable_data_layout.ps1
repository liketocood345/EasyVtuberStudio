param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$reconcileScript = Join-Path $PSScriptRoot "reconcile_portable_layout.ps1"
if (-not (Test-Path $reconcileScript)) {
    throw "Missing packaging\reconcile_portable_layout.ps1"
}

& $reconcileScript -PortableRoot $PortableRoot
