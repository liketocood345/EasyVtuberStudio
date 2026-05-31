param(
    [string]$PortableRoot = Resolve-PortableRoot (Join-Path $PSScriptRoot ".."),
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Get-AssetUrl($asset, $manifest) {
    if (-not [string]::IsNullOrWhiteSpace($asset.url)) {
        return $asset.url
    }
    if (-not [string]::IsNullOrWhiteSpace($manifest.release_base_url)) {
        $base = [string]$manifest.release_base_url
        if (-not $base.EndsWith("/")) { $base += "/" }
        return $base + $asset.filename
    }
    return ""
}

Write-Host "Portable verify: $PortableRoot"
$checks = @(
    @{ Name = "assets_manifest.json"; Path = Join-Path $PortableRoot "packaging\assets_manifest.json" },
    @{ Name = "bootstrap_portable.ps1"; Path = Join-Path $PortableRoot "packaging\bootstrap_portable.ps1" },
    @{ Name = "EasyVtuberStudio.exe"; Path = Join-Path $PortableRoot "EasyVtuberStudio.exe" },
    @{ Name = "THA4Train.exe"; Path = Join-Path $PortableRoot "scripts\launch\THA4Train.exe" },
    @{ Name = "load preview script"; Path = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py" },
    @{ Name = "demo run.bat"; Path = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\bin\run.bat" },
    @{ Name = "app icon"; Path = Join-Path $PortableRoot "assets\branding\app-icon-source.ico" }
)

$failed = 0
foreach ($check in $checks) {
    if (Test-Path $check.Path) {
        Write-Host "[OK] $($check.Name)"
    } else {
        Write-Host "[MISSING] $($check.Name) -> $($check.Path)"
        $failed++
    }
}

$mediapipeCandidates = @(
    Join-Path $PortableRoot "addons\face_puppeteer\mediapipe\face_landmarker_v2_with_blendshapes.task",
    Join-Path $PortableRoot "data\thirdparty\mediapipe\face_landmarker_v2_with_blendshapes.task"
)
$mediapipe = $mediapipeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($mediapipe) {
    Write-Host "[OK] mediapipe task -> $mediapipe"
} else {
    Write-Host "[MISSING] mediapipe task"
    $failed++
}

$python = $null
if (Test-FacePuppeteerVenv -PortableRoot $PortableRoot) {
    $venvRoot = Get-FacePuppeteerVenvAbsolute -PortableRoot $PortableRoot
    $python = Join-Path $venvRoot "Scripts\python.exe"
    Write-Host "[OK] python runtime -> $python"
} elseif ($Strict) {
    Write-Host "[MISSING] python runtime (addons\face_puppeteer\venv or runtime junction)"
    $failed++
} else {
    Write-Host "[WARN] python runtime missing (expected on fresh GitHub extract before DEPLOY)"
}

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) { exit 1 }
}
exit 0
