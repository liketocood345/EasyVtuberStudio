param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$IncludeTha3Models,
    [switch]$BuildLaunchers,
    [switch]$BuildReleaseAssets,
    [switch]$WriteManifestHashes
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path

Write-Host "=== Prepare portable release ==="
Write-Host "Repo: $RepoRoot"

& (Join-Path $RepoRoot "scripts\maint\setup_portable_runtime.ps1") -RepoRoot $RepoRoot -Force
& (Join-Path $RepoRoot "packaging\bootstrap_portable.ps1") -PortableRoot $RepoRoot -Quiet

if ($BuildLaunchers) {
    & (Join-Path $RepoRoot "packaging\build_launchers.ps1") -RepoRoot $RepoRoot
}

if ($BuildReleaseAssets) {
    $args = @("-RepoRoot", $RepoRoot)
    if ($IncludeTha3Models) { $args += "-IncludeTha3Models" }
    if ($WriteManifestHashes) { $args += "-WriteManifestHashes" }
    & (Join-Path $RepoRoot "packaging\build_release_assets.ps1") @args
}

& (Join-Path $RepoRoot "packaging\verify_portable.ps1") -PortableRoot $RepoRoot -Strict

Write-Host ""
Write-Host "Portable tree ready."
Write-Host "Next: upload packaging\release_assets\*.7z to GitHub Release,"
Write-Host "      fill packaging\assets_manifest.json release_base_url + sha256,"
Write-Host "      then scripts\maint\sync_develop_to_fork.ps1 and push."
