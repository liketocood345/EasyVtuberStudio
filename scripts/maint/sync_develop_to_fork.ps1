# Sync easyvtuberstudio-develop -> easyvtuberstudio-main (code, docs, packaging, scripts).
# Preserves main .git; skips local-only heavy state (venv, runtime, addons payloads, workspace).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_fork.ps1

param(
    [string]$DevRoot = "",
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "repo_paths.ps1")
$roots = Resolve-DevelopForkRoots -DevRoot $DevRoot -ForkRoot $ForkRoot
$DevRoot = $roots.DevRoot
$ForkRoot = $roots.ForkRoot

$refreshHotspots = Join-Path $DevRoot "scripts\maint\refresh_bug_hotspot_checklist.ps1"
if (Test-Path $refreshHotspots) {
    & $refreshHotspots -Quiet
}

if (-not (Test-Path (Join-Path $ForkRoot ".git"))) {
    throw "Fork git repo not found: $ForkRoot"
}

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

$copyDirs = @(
    "addons", "assets", "bin", "data", "deps", "distiller-ui-doc", "docs", "face-puppeteer-ui-enhancements-ai-code",
    "packaging", "plans", "poetry", "scripts", "src", "tools"
)
# Root README.md: edit only on easyvtuberstudio-main; never copied develop -> fork (GitHub gets it via push).
$copyFiles = @(".gitignore", ".python-version", "EasyVtuberStudio.exe", "DEPLOY.bat", "RESET_ADDON.bat")

$excludeDirs = @(
    "__pycache__", ".codegraph", "venv", "runtime", "external_layer_output", "basic_layers",
    "face_puppeteer", "tha3_models", "tha4_training", "output_enhancement"
)

foreach ($dir in $copyDirs) {
    $src = Join-Path $DevRoot $dir
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $ForkRoot $dir
    $args = @(
        $src, $dst, "/E", "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP",
        "/XD"
    ) + $excludeDirs
    robocopy @args | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for $dir exit $LASTEXITCODE"
    }
}

foreach ($file in $copyFiles) {
    $src = Join-Path $DevRoot $file
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $ForkRoot $file)
    }
}

Ensure-Dir (Join-Path $ForkRoot "workspace")
$gitkeep = Join-Path $ForkRoot "workspace\.gitkeep"
if (-not (Test-Path $gitkeep)) {
    New-Item -ItemType File -Force -Path $gitkeep | Out-Null
}

foreach ($pack in @("face_puppeteer", "tha3_models", "tha4_training", "output_enhancement")) {
    $path = Join-Path $ForkRoot "addons\$pack"
    if (Test-Path $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction SilentlyContinue
    }
}
$addonsReadme = Join-Path $DevRoot "addons\README.md"
if (Test-Path $addonsReadme) {
    Ensure-Dir (Join-Path $ForkRoot "addons")
    Copy-Item -Force $addonsReadme (Join-Path $ForkRoot "addons\README.md")
}

& (Join-Path $DevRoot "scripts\maint\restructure_repo.ps1") -RepoRoot $ForkRoot -ForkLayoutOnly

$resetFork = Join-Path $ForkRoot "scripts\maint\reset_fork_fresh_extract.ps1"
if (Test-Path $resetFork) {
    & $resetFork -ForkRoot $ForkRoot
    if ($LASTEXITCODE -ne 0) {
        throw "reset_fork_fresh_extract failed."
    }
} else {
    Write-Warning "reset_fork_fresh_extract.ps1 not found; fork layout may not match fresh extract."
}

Write-Host "Synced develop -> fork (code only; fork = fresh CORE extract)"
Write-Host "  Dev:  $DevRoot"
Write-Host "  Fork: $ForkRoot"
