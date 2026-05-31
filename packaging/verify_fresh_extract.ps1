param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$failures = @()

function Assert-Missing {
    param([string]$RelativePath, [string]$Message)
    $full = Resolve-PortableRootPath $PortableRoot $RelativePath
    if (Test-Path $full) {
        $failures += "$Message (found: $RelativePath)"
    }
}

function Assert-Present {
    param([string]$RelativePath, [string]$Message)
    $full = Resolve-PortableRootPath $PortableRoot $RelativePath
    if (-not (Test-Path $full)) {
        $failures += "$Message (missing: $RelativePath)"
    }
}

Write-Host ""
Write-Host "Verifying fresh CORE extract: $PortableRoot"
Write-Host ""

# CORE must include student model
Assert-Present "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt" "CORE should include THA4 student (bai_450k)"

# Upstream author lambda students must not ship
foreach ($legacy in @("lambda_00", "lambda_01")) {
    Assert-Missing "data/character_models/$legacy" "Upstream lambda student removed ($legacy)"
    Assert-Missing "data/distill_examples/$legacy" "Upstream lambda distill example removed ($legacy)"
}
foreach ($legacyImage in @("lambda_00.png", "lambda_01.png", "lambda_00_face_mask.png", "lambda_01_face_mask.png")) {
    Assert-Missing "data/images/$legacyImage" "Upstream lambda image removed ($legacyImage)"
    Assert-Missing "deps/tha3/images/$legacyImage" "Upstream lambda THA3 sample removed ($legacyImage)"
}

# Optional add-ons must NOT be present in fresh extract
foreach ($addon in @($manifest.addons)) {
    $folderRel = Get-AddonFolderRelative -AddonRecord $addon
    foreach ($verifyRel in @($addon.verify)) {
        $verifyRel = [string]$verifyRel
        if ($verifyRel.StartsWith("addons/")) {
            Assert-Missing $verifyRel "Fresh extract should not include $($addon.id)"
        }
    }
    $addonRoot = Resolve-PortableRootPath $PortableRoot $folderRel
    if ((Test-Path $addonRoot) -and $addon.id -ne "face_puppeteer") {
        $hasContent = Get-ChildItem $addonRoot -Force -ErrorAction SilentlyContinue
        if ($hasContent) {
            $failures += "Fresh extract should not populate $folderRel ($($addon.id))"
        }
    }
}

# Legacy runtime paths should not exist until add-on installed
Assert-Missing "runtime/venv/Scripts/python.exe" "Fresh extract should not include runtime venv"
Assert-Missing "venv/Scripts/python.exe" "Fresh extract should not include legacy repo-root venv"
Assert-Missing "workspace/student_venv/Scripts/python.exe" "Fresh extract should not include student_venv until first launch"
Assert-Missing "face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/venv/Scripts/python.exe" "Fresh extract should not include legacy demo venv"
Assert-Missing "deps/tha3/models/separable_half/face_morpher.pt" "Fresh extract should not include THA3 weights"

$demoTha4 = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4\teacher"
if (Test-Path $demoTha4) {
    $failures += "Fresh extract should not include THA4 teacher weights (demo/data/tha4/teacher)"
}

# Reconcile should succeed on CORE-only tree
& (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot | Out-Null

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "VERIFY FAILED ($($failures.Count) issue(s)):" -ForegroundColor Red
    foreach ($f in $failures) {
        Write-Host "  - $f" -ForegroundColor Red
    }
    exit 1
}

Write-Host "VERIFY OK: layout matches slim CORE extract expectations." -ForegroundColor Green
Write-Host ""
exit 0
