# Verify dual-repo roles: develop = full 3-module install, fork = GitHub fresh CORE extract.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\verify_repo_roles.ps1

param(
    [string]$DevRoot = "",
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "repo_paths.ps1")
$here = (Resolve-Path $PSScriptRoot).Path
$repoFromScript = (Resolve-Path (Join-Path $here "..\..")).Path
$repoLeaf = Split-Path $repoFromScript -Leaf

if (-not $DevRoot -and -not $ForkRoot) {
    if ($repoLeaf -in $script:ForkDirCandidates) {
        $ForkRoot = $repoFromScript
    } else {
        $DevRoot = $repoFromScript
    }
}
$roots = Resolve-DevelopForkRoots -DevRoot $DevRoot -ForkRoot $ForkRoot
$DevRoot = $roots.DevRoot
$ForkRoot = $roots.ForkRoot

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
