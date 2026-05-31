param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$failed = 0

Write-Host ""
Write-Host "Full install verification (all add-ons): $PortableRoot"
Write-Host ""

foreach ($addon in @($manifest.addons)) {
    if (Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $addon) {
        Write-Host "[OK] $($addon.id)"
    } else {
        Write-Host "[MISSING] $($addon.id)"
        $failed++
    }
}

& (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot | Out-Null

$verifyArgs = @{
    PortableRoot         = $PortableRoot
    Strict               = $true
    RequireFacePuppeteer = $true
    RequireTha3Models    = $true
    IncludeTha4Training  = $true
}
& (Join-Path $PSScriptRoot "verify_deploy.ps1") @verifyArgs
if ($LASTEXITCODE -ne 0) { $failed++ }

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) {
        throw "Full install verification failed."
    }
    exit 1
}

Write-Host "Full install verification passed (develop / full portable)."
Write-Host ""
exit 0
