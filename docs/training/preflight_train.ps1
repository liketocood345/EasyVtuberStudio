# Run before training in an external terminal.
$ErrorActionPreference = "Stop"
$demo = "E:\THA4_bundle_bai_custom\talking-head-anime-4-demo"
$bundle = "E:\THA4_bundle_bai_custom"
$prefix = "E:\THA4_bundle\distill_outputs\bai"
$failed = 0

function Assert-Check([string]$name, [scriptblock]$test) {
    try {
        if (& $test) { Write-Host "[OK] $name" -ForegroundColor Green }
        else { Write-Host "[FAIL] $name" -ForegroundColor Red; $script:failed++ }
    } catch {
        Write-Host "[FAIL] $name - $_" -ForegroundColor Red
        $script:failed++
    }
}

Write-Host "THA4_bundle_bai_custom preflight" -ForegroundColor Cyan

Assert-Check "no training process" {
    -not (Get-CimInstance Win32_Process -EA SilentlyContinue |
        Where-Object { $_.CommandLine -match 'distill_body_morpher' })
}

Assert-Check "pose_dataset hardlink/file" {
    $p = Get-Item "$demo\data\pose_dataset.pt" -Force
    -not ($p.Attributes -band [IO.FileAttributes]::Directory)
}

Assert-Check "snapshot exists" { Test-Path "$prefix\body_morpher\snapshot\module_module.pt" }
Assert-Check "face 0010 exists" { Test-Path "$prefix\face_morpher\checkpoint\0010\module_module.pt" }

$env:PYTHONPATH = "$demo\src"
Push-Location $demo
try {
    $py = & ".\venv\Scripts\python.exe" "..\preflight_config_check.py" 2>&1 | Out-String
    $exit = $LASTEXITCODE
} finally {
    Pop-Location
}
if ($exit -ne 0 -or $py -notmatch 'ok') {
    Write-Host "[FAIL] Python config load" -ForegroundColor Red
    Write-Host $py
    $failed++
} else {
    Write-Host "[OK] Python config (800k target, ckpt 0045@450k, 0080@800k)" -ForegroundColor Green
}

$snap = Get-Content "$prefix\body_morpher\snapshot\examples_seen_so_far.txt"
Write-Host "     snapshot steps: $snap"

if ($failed -gt 0) {
    Write-Host "`nPreflight FAILED ($failed)." -ForegroundColor Red
    exit 1
}
Write-Host "`nPreflight passed." -ForegroundColor Green
Write-Host "  Full:  $bundle\run_body_train.bat"
Write-Host "  450k:  $bundle\run_body_train_450k.bat"
