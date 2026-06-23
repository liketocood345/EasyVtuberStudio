# Stage OpenSeeFace (Binary + models + Licenses) for HF Bucket mirror or local portable.
# Matches layout produced by packaging/fetch_upstream_assets.ps1 Install-OpenSeeFaceZip.
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\import_openseeface_to_hf_mirror.ps1
#   powershell -ExecutionPolicy Bypass -File scripts\maint\import_openseeface_to_hf_mirror.ps1 -MirrorRoot E:\EasyVtuberStudio-hf -SourceRoot F:\EasyVtuber\OpenSeeFace-v1.20.4
#   powershell -ExecutionPolicy Bypass -File scripts\maint\import_openseeface_to_hf_mirror.ps1 -PortableRoot E:\easyvtuberstudio-develop

param(
    [string]$MirrorRoot = "",
    [string]$PortableRoot = "",
    [string]$SourceRoot = "F:\EasyVtuber\OpenSeeFace-v1.20.4"
)

$ErrorActionPreference = "Stop"

$destRoot = $null
if ($PortableRoot) {
    $destRoot = Join-Path (Resolve-Path $PortableRoot).Path "addons\openseeface"
} elseif ($MirrorRoot) {
    $destRoot = Join-Path (Resolve-Path $MirrorRoot).Path "addons\openseeface"
} else {
    $hfMirror = "E:\EasyVtuberStudio-hf"
    if (Test-Path $hfMirror) {
        $destRoot = Join-Path $hfMirror "addons\openseeface"
    } else {
        throw "Pass -MirrorRoot or -PortableRoot (default HF mirror not found: $hfMirror)"
    }
}

if (-not (Test-Path $SourceRoot)) {
    throw "OpenSeeFace source not found: $SourceRoot"
}
$SourceRoot = (Resolve-Path $SourceRoot).Path

$exe = Join-Path $SourceRoot "Binary\facetracker.exe"
if (-not (Test-Path $exe)) {
    throw "Missing facetracker.exe under $SourceRoot\Binary"
}

if (Test-Path $destRoot) {
    Remove-Item $destRoot -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

foreach ($subdir in @("Binary", "models", "Licenses")) {
    $src = Join-Path $SourceRoot $subdir
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $destRoot $subdir) -Recurse -Force
        Write-Host "Copied $subdir/"
    } else {
        Write-Host "Skip missing $subdir/"
    }
}

$marker = Join-Path $destRoot ".installed"
Set-Content -Path $marker -Value ((Get-Date -Format o)) -Encoding UTF8

if (-not (Test-Path (Join-Path $destRoot "Binary\facetracker.exe"))) {
    throw "Import failed: facetracker.exe missing in $destRoot"
}

$sum = (Get-ChildItem $destRoot -Recurse -File | Measure-Object -Property Length -Sum).Sum
Write-Host ""
Write-Host "[OK] OpenSeeFace staged -> $destRoot"
Write-Host ("Size: {0:N2} MB" -f ($sum / 1MB))
Write-Host "Next: sync_develop_to_hf_bucket.ps1 -MirrorRoot <hf-mirror>"
