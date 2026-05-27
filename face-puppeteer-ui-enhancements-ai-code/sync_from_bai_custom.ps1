# Copy active files from E:\THA4_bundle_bai_custom into this fork root.
$ErrorActionPreference = "Stop"
$srcRoot = "E:\THA4_bundle_bai_custom"
$fork = $PSScriptRoot

$pairs = @(
    @("experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py", "experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py"),
    @("experiments\puppeteer_load_preview\README.txt", "experiments\puppeteer_load_preview\README.txt"),
    @("experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat", "experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat"),
    @("experiments\puppeteer_load_preview\smoke_load_preview.py", "experiments\puppeteer_load_preview\smoke_load_preview.py"),
    @("talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py", "talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py"),
    @("HANDOVER.md", "HANDOVER.md")
)

foreach ($pair in $pairs) {
    $from = Join-Path $srcRoot $pair[0]
    $to = Join-Path $fork $pair[1]
    if (-not (Test-Path $from)) {
        Write-Warning "Skip missing: $from"
        continue
    }
    $dir = Split-Path $to -Parent
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    Copy-Item -LiteralPath $from -Destination $to -Force
    Write-Host "Copied $($pair[0])"
}

$packSrc = Join-Path $srcRoot "packaged\bai_450k"
$packDst = Join-Path $fork "packaged\bai_450k"
if (Test-Path $packSrc) {
    New-Item -ItemType Directory -Force -Path $packDst | Out-Null
    Copy-Item -Path (Join-Path $packSrc "*") -Destination $packDst -Recurse -Force
    Write-Host "Copied packaged/bai_450k/"
}

Write-Host "Done. Fork root updated from bai_custom."
