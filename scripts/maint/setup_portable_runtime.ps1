param(
    [string]$RepoRoot = "",
    [string]$ExternalVenvSource = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = Join-Path $PSScriptRoot "..\.."
}

. (Join-Path $RepoRoot "packaging\addon_paths.ps1")
$RepoRoot = Resolve-PortableRoot $RepoRoot

$addonVenv = Resolve-PortableRootPath $RepoRoot (Get-FacePuppeteerVenvRelative)
$python = Join-Path $addonVenv "Scripts\python.exe"

if ((Test-Path $python) -and -not $Force) {
    Write-Host "addons\face_puppeteer\venv already exists. Use -Force to rebuild."
    & (Join-Path $RepoRoot "packaging\reconcile_portable_layout.ps1") -PortableRoot $RepoRoot | Out-Null
    exit 0
}

$sources = @()
if ($ExternalVenvSource) {
    $sources += $ExternalVenvSource
}
$sources += @(
    (Join-Path $RepoRoot "workspace\student_venv"),
    (Join-Path $RepoRoot "runtime\venv"),
    (Join-Path $RepoRoot "venv"),
    (Join-Path (Split-Path $RepoRoot -Parent) "THA4_bundle\talking-head-anime-4-demo\venv")
)
$source = $sources | Where-Object { Test-Path (Join-Path $_ "Scripts\python.exe") } | Select-Object -First 1
if (-not $source) {
    throw "No dev venv found. Create venv before preparing portable runtime."
}

Write-Host "Copying $source -> addons\face_puppeteer\venv ..."
Ensure-Directory (Split-Path $addonVenv -Parent)
if (Test-Path $addonVenv) {
    Remove-Item $addonVenv -Recurse -Force
}
robocopy $source $addonVenv /E /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed copying venv to addons\face_puppeteer\venv"
}

& (Join-Path $RepoRoot "packaging\reconcile_portable_layout.ps1") -PortableRoot $RepoRoot | Out-Null
Write-Host "addons\face_puppeteer\venv ready (runtime\venv linked)."
