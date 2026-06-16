# Reset fork repo to GitHub ZIP / fresh extract state (slim CORE, no add-on payloads).
# Usage (from fork root):
#   powershell -ExecutionPolicy Bypass -File scripts\maint\reset_fork_fresh_extract.ps1

param(
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $ForkRoot) {
    $ForkRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
} else {
    $ForkRoot = (Resolve-Path $ForkRoot).Path
}

function Remove-TreeIfExists([string]$Path) {
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
    }
}

Write-Host ""
Write-Host "Resetting fork to fresh CORE extract: $ForkRoot"
Write-Host ""

foreach ($pack in @("face_puppeteer", "tha3_models", "tha4_training", "output_enhancement")) {
    Remove-TreeIfExists (Join-Path $ForkRoot "addons\$pack")
}

Remove-TreeIfExists (Join-Path $ForkRoot "runtime")
Remove-TreeIfExists (Join-Path $ForkRoot "venv")
Remove-TreeIfExists (Join-Path $ForkRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv")
Remove-TreeIfExists (Join-Path $ForkRoot "talking-head-anime-4-demo\venv")
Remove-TreeIfExists (Join-Path $ForkRoot "workspace\student_venv")
Remove-TreeIfExists (Join-Path $ForkRoot "data\thirdparty\mediapipe")

$workspace = Join-Path $ForkRoot "workspace"
if (Test-Path $workspace) {
    Get-ChildItem $workspace -Force | Where-Object { $_.Name -ne ".gitkeep" } |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
} else {
    New-Item -ItemType Directory -Force -Path $workspace | Out-Null
}
New-Item -ItemType File -Force -Path (Join-Path $workspace ".gitkeep") | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $workspace ".deploy_complete")

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

Write-Host ""
Ensure-Dir (Join-Path $ForkRoot "addons")
$readme = Join-Path $ForkRoot "addons\README.md"
if (-not (Test-Path $readme)) {
    throw "Missing addons\README.md under $ForkRoot"
}

$demoData = Join-Path $ForkRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data"
foreach ($mirror in @("character_models", "models", "thirdparty", "images", "distill_examples")) {
    Remove-TreeIfExists (Join-Path $demoData $mirror)
}
$tha4Teacher = Join-Path $demoData "tha4"
Remove-TreeIfExists $tha4Teacher
Ensure-Dir $tha4Teacher
$placeholder = Join-Path $tha4Teacher "placeholder.txt"
if (-not (Test-Path $placeholder)) {
    Set-Content -Path $placeholder -Value "THA4 teacher weights are downloaded by DEPLOY.bat (optional) or THA4_DownloadTrainingAssets.bat." -Encoding UTF8
}

& (Join-Path $ForkRoot "packaging\reconcile_portable_layout.ps1") -PortableRoot $ForkRoot | Out-Null
& (Join-Path $ForkRoot "packaging\verify_fresh_extract.ps1") -PortableRoot $ForkRoot
exit $LASTEXITCODE
