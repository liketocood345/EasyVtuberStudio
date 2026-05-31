# Sync tha4fork-develop -> tha4fork (code, docs, packaging, scripts).
# Preserves fork .git; skips local-only heavy state (venv, runtime, addons payloads, workspace).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\sync_develop_to_fork.ps1

param(
    [string]$DevRoot = "",
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $DevRoot) {
    $DevRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    $DevRoot = (Resolve-Path $DevRoot).Path
}
if (-not $ForkRoot) {
    $ForkRoot = (Resolve-Path (Join-Path $DevRoot "..\tha4fork")).Path
} else {
    $ForkRoot = (Resolve-Path $ForkRoot).Path
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
$copyFiles = @(".gitignore", ".python-version", "README.md", "EasyVtuberStudio.exe", "DEPLOY.bat", "RESET_ADDON.bat")

$excludeDirs = @(
    "__pycache__", ".codegraph", "venv", "runtime", "external_layer_output", "basic_layers",
    "face_puppeteer", "tha3_models", "tha4_training"
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

foreach ($pack in @("face_puppeteer", "tha3_models", "tha4_training")) {
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
