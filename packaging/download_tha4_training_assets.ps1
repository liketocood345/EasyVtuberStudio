param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$helper = Join-Path $PSScriptRoot "bootstrap_tha4_teacher.ps1"
if (-not (Test-Path $helper)) {
    throw "Missing bootstrap_tha4_teacher.ps1"
}

& $helper -PortableRoot $PortableRoot
