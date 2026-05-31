# Verify dual-repo roles: develop = full 3-module install, fork = GitHub fresh CORE extract.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\verify_repo_roles.ps1

param(
    [string]$DevRoot = "",
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
$here = (Resolve-Path $PSScriptRoot).Path
$repoFromScript = (Resolve-Path (Join-Path $here "..\..")).Path

if (-not $DevRoot -and -not $ForkRoot) {
    if ((Split-Path $repoFromScript -Leaf) -eq "tha4fork") {
        $ForkRoot = $repoFromScript
        $DevRoot = Join-Path (Split-Path $ForkRoot -Parent) "tha4fork-develop"
    } else {
        $DevRoot = $repoFromScript
        $ForkRoot = Join-Path (Split-Path $DevRoot -Parent) "tha4fork"
    }
}
if (-not $DevRoot) { $DevRoot = (Resolve-Path (Join-Path $ForkRoot "..\tha4fork-develop")).Path }
if (-not $ForkRoot) { $ForkRoot = (Resolve-Path (Join-Path $DevRoot "..\tha4fork")).Path }
$DevRoot = (Resolve-Path $DevRoot).Path
$ForkRoot = (Resolve-Path $ForkRoot).Path

Write-Host ""
Write-Host "=== Verify repo roles ==="
Write-Host "  Develop (full install): $DevRoot"
Write-Host "  Fork (fresh extract):   $ForkRoot"
Write-Host ""

$failed = 0

Write-Host "-- fork: fresh CORE extract --"
& (Join-Path $ForkRoot "packaging\verify_fresh_extract.ps1") -PortableRoot $ForkRoot
if ($LASTEXITCODE -ne 0) { $failed++ }

Write-Host ""
Write-Host "-- develop: full 3-module install --"
$fullVerify = Join-Path $DevRoot "packaging\verify_full_install.ps1"
if (-not (Test-Path $fullVerify)) {
    Write-Host "[MISSING] $fullVerify"
    $failed++
} else {
    & $fullVerify -PortableRoot $DevRoot -Strict
    if ($LASTEXITCODE -ne 0) {
        $failed++
        Write-Host ""
        Write-Host "Develop is missing add-on payloads. One-time fix (all four tiers, needs network):"
        Write-Host "  cd /d $DevRoot"
        Write-Host "  DEPLOY.bat"
        Write-Host "  (answer Y to all four questions, or run packaging\deploy_portable.ps1 with all PackageIds)"
    }
}

Write-Host ""
if ($failed -gt 0) {
    Write-Host "Repo role verification failed ($failed check(s))." -ForegroundColor Red
    exit 1
}

Write-Host "Repo role verification passed." -ForegroundColor Green
Write-Host ""
exit 0
