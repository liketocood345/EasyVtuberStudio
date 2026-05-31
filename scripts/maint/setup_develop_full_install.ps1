# One-shot: migrate legacy layout (if needed), reconcile, verify all 3 add-ons.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\maint\setup_develop_full_install.ps1

param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

$migrate = Join-Path $RepoRoot "packaging\migrate_to_addons_layout.ps1"
$verify = Join-Path $RepoRoot "packaging\verify_full_install.ps1"

if (Test-Path $migrate) {
    & $migrate -PortableRoot $RepoRoot
}

if (-not (Test-Path $verify)) {
    throw "Missing packaging\verify_full_install.ps1"
}

& $verify -PortableRoot $RepoRoot -Strict
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Develop full install incomplete. Install all optional packs once (needs network):"
    Write-Host "  DEPLOY.bat  -> answer Y to all four tiers"
    Write-Host "  or: powershell -ExecutionPolicy Bypass -File packaging\deploy_portable.ps1 -PortableRoot `"$RepoRoot`" -PackageIds mouse_student,face_puppeteer,tha3_models,tha4_training -Confirmed"
}
exit $LASTEXITCODE
