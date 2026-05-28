# Sync planning docs from active dev repo into tha4fork-develop/plans/
$ErrorActionPreference = "Stop"

$SourceRoot = "E:\THA4_bundle_bai_custom"
$DestRoot = $PSScriptRoot
$PlansDir = Join-Path $DestRoot "plans"

if (-not (Test-Path $SourceRoot)) {
    throw "Source not found: $SourceRoot"
}

New-Item -ItemType Directory -Force -Path $PlansDir | Out-Null

$files = @(
    @{ Src = "layer-runtime-replan_3a393fc1.plan.md"; Dst = "layer-runtime-replan_3a393fc1.plan.md" },
    @{ Src = "HANDOVER.md"; Dst = "HANDOVER.md" }
)

foreach ($f in $files) {
    $srcPath = Join-Path $SourceRoot $f.Src
    $dstPath = Join-Path $PlansDir $f.Dst
    if (-not (Test-Path $srcPath)) {
        Write-Warning "Skip missing: $srcPath"
        continue
    }
    Copy-Item -LiteralPath $srcPath -Destination $dstPath -Force
    Write-Host "Copied: $($f.Src) -> plans\$($f.Dst)"
}

$handoverBundle = Join-Path $DestRoot "face-puppeteer-ui-enhancements-ai-code\HANDOVER.md"
Copy-Item -LiteralPath (Join-Path $SourceRoot "HANDOVER.md") -Destination $handoverBundle -Force
Write-Host "Copied: HANDOVER.md -> face-puppeteer-ui-enhancements-ai-code\HANDOVER.md"

Write-Host "Done. Regenerate plans\EXTERNAL_LAYER_INTERFACE.md manually if bridge schema changed."
