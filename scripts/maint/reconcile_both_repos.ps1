# One-shot: develop = full 3-module install, fork = GitHub fresh extract; sync code + verify both.
# Usage (from either repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\maint\reconcile_both_repos.ps1

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
if (-not $DevRoot) {
    $DevRoot = (Resolve-Path (Join-Path $ForkRoot "..\tha4fork-develop")).Path
}
if (-not $ForkRoot) {
    $ForkRoot = (Resolve-Path (Join-Path $DevRoot "..\tha4fork")).Path
}
$DevRoot = (Resolve-Path $DevRoot).Path
$ForkRoot = (Resolve-Path $ForkRoot).Path

Write-Host ""
Write-Host "=== Reconcile both repos ==="
Write-Host "  Develop (full install): $DevRoot"
Write-Host "  Fork (fresh extract):   $ForkRoot"
Write-Host ""

$syncDevToFork = Join-Path $DevRoot "scripts\maint\sync_develop_to_fork.ps1"
if (-not (Test-Path $syncDevToFork)) {
    $syncDevToFork = Join-Path $ForkRoot "scripts\maint\sync_develop_to_fork.ps1"
}
& $syncDevToFork -DevRoot $DevRoot -ForkRoot $ForkRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Remove duplicate reset when sync_develop_to_fork already ran reset_fork_fresh_extract.
$resetFork = Join-Path $ForkRoot "scripts\maint\reset_fork_fresh_extract.ps1"
if (-not (Test-Path $resetFork)) {
    Write-Warning "reset_fork_fresh_extract.ps1 not found; fork may not match fresh extract."
}

$setupDevelop = Join-Path $DevRoot "scripts\maint\setup_develop_full_install.ps1"
& $setupDevelop -RepoRoot $DevRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$verifyPaths = Join-Path $ForkRoot "scripts\maint\verify_path_refs.ps1"
if (Test-Path $verifyPaths) {
    & $verifyPaths | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "verify_path_refs reported issues (non-fatal; see above)."
    }
}

$verifyRoles = Join-Path $ForkRoot "scripts\maint\verify_repo_roles.ps1"
if (Test-Path $verifyRoles) {
    & $verifyRoles -DevRoot $DevRoot -ForkRoot $ForkRoot
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "verify_repo_roles reported issues (see above)."
    }
}

Write-Host ""
Write-Host "=== Reconcile complete ==="
Write-Host "  develop: full install OK"
Write-Host "  fork:    fresh CORE extract OK"
Write-Host ""
exit 0
