# Copy easyvtuberstudio-develop -> easyvtuberstudio-main (Load Preview experiment subtree).
# Does NOT overwrite local runtime state (ui state, layer json, external_layer_output).
# Usage (from develop root):
#   powershell -ExecutionPolicy Bypass -File sync_to_fork.ps1
# Optional: -ForkRoot "E:\easyvtuberstudio-main"

param(
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "repo_paths.ps1")
$roots = Resolve-DevelopForkRoots -ForkRoot $ForkRoot
$DevRoot = $roots.DevRoot
$ForkRoot = $roots.ForkRoot
if (-not (Test-Path (Join-Path $ForkRoot "docs\DEPLOY.md"))) {
    throw "Fork root not found or invalid: $ForkRoot"
}

$DevExp = Join-Path $DevRoot "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview"
$ForkExp = Join-Path $ForkRoot "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview"
if (-not (Test-Path $DevExp)) {
    throw "Develop experiment dir missing: $DevExp"
}

$excludeDirs = @("__pycache__", "external_layer_output", "basic_layers")
$roboArgs = @($DevExp, $ForkExp, "/E", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP", "/XF", "load_preview_ui_state.json")
foreach ($d in $excludeDirs) {
    $roboArgs += "/XD"
    $roboArgs += $d
}
robocopy @roboArgs | Out-Null
if ($LASTEXITCODE -ge 8) {
    throw "robocopy failed with exit code $LASTEXITCODE"
}

Write-Host "Synced Load Preview experiment: develop -> fork (robocopy exit $LASTEXITCODE)"
Write-Host "Skipped runtime: $($excludeDirs -join ', '), load_preview_ui_state.json"
Write-Host "Fork: $ForkRoot"
