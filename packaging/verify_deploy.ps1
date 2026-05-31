param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Strict,
    [switch]$IncludeTha4Training,
    [switch]$RequireFacePuppeteer = $true,
    [switch]$RequireTha3Models = $true
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Test-RequiredFile([string]$Label, [string]$RelativePath, [ref]$Failed) {
    $path = Resolve-PortableRootPath $PortableRoot $RelativePath
    if (Test-Path $path) {
        Write-Host "[OK] $Label"
        return $true
    }
    Write-Host "[MISSING] $Label -> $RelativePath"
    $Failed.Value++
    return $false
}

Write-Host ""
Write-Host "Deploy verification: $PortableRoot"
Write-Host ""

$failed = 0
$failedRef = [ref]$failed

Test-RequiredFile "EasyVtuberStudio.exe" "EasyVtuberStudio.exe" $failedRef | Out-Null
Test-RequiredFile "deploy script" "packaging/deploy_portable.ps1" $failedRef | Out-Null
Test-RequiredFile "load preview entry" "face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py" $failedRef | Out-Null

Test-RequiredFile "bai student yaml" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character_model.yaml" $failedRef | Out-Null
Test-RequiredFile "bai face_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai body_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/body_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai character.png" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character.png" $failedRef | Out-Null

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$faceRecord = Get-AddonRecord -Manifest $manifest -AddonId "face_puppeteer"
$tha3Record = Get-AddonRecord -Manifest $manifest -AddonId "tha3_models"
$tha4Record = Get-AddonRecord -Manifest $manifest -AddonId "tha4_training"

$python = $null
if ($RequireFacePuppeteer) {
    if (Test-FacePuppeteerVenv -PortableRoot $PortableRoot) {
        $venvRoot = Get-FacePuppeteerVenvAbsolute -PortableRoot $PortableRoot
        $python = Join-Path $venvRoot "Scripts\python.exe"
        Write-Host "[OK] Python runtime ($venvRoot)"
    } else {
        Write-Host "[MISSING] Python runtime -> addons/face_puppeteer/venv"
        $failed++
    }
    foreach ($rel in @($faceRecord.verify)) {
        Test-RequiredFile "face_puppeteer: $rel" ([string]$rel) $failedRef | Out-Null
    }
} else {
    Write-Host "[SKIP] face_puppeteer add-on"
}

if ($RequireTha3Models) {
    foreach ($rel in @($tha3Record.verify)) {
        Test-RequiredFile "tha3_models: $rel" ([string]$rel) $failedRef | Out-Null
    }
    Test-RequiredFile "THA3 runtime cwd link" "face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/data/models/separable_half/face_morpher.pt" $failedRef | Out-Null
} else {
    Write-Host "[SKIP] tha3_models add-on"
}

if ($IncludeTha4Training) {
    foreach ($rel in @($tha4Record.verify)) {
        Test-RequiredFile "tha4_training: $rel" ([string]$rel) $failedRef | Out-Null
    }
} else {
    Write-Host "[SKIP] tha4_training add-on"
}

if ($python -and (Test-Path $python)) {
    Write-Host ""
    Write-Host "Checking Python imports (torch, wx, mediapipe) ..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $importOut = & $python -c "import torch, wx, mediapipe; print(torch.__version__)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python imports (torch $($importOut -join ''))"
    } else {
        Write-Host "[MISSING] Python imports -> torch/wx/mediapipe (re-run DEPLOY.bat)"
        Write-Host "  $importOut"
        $failed++
    }
    if ($RequireFacePuppeteer -and $LASTEXITCODE -eq 0) {
        Write-Host "Checking face capture UI readiness ..."
        $expDir = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview"
        $demoSrc = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src"
        $probeCode = @"
import sys
sys.path.insert(0, r'$expDir')
from mouse_mocap_driver import MOCAP_INPUT_MODE_MEDIAPIPE
from portable_paths import face_capture_assets_ready
from pathlib import Path
assert MOCAP_INPUT_MODE_MEDIAPIPE == 'mediapipe'
assert face_capture_assets_ready(Path(r'$PortableRoot'))
print('face capture ready')
"@
        $savedPythonPath = $env:PYTHONPATH
        $savedPortableRoot = $env:THA4_PORTABLE_ROOT
        $env:PYTHONPATH = $demoSrc
        $env:THA4_PORTABLE_ROOT = $PortableRoot
        $faceProbeOut = & $python -c $probeCode 2>&1
        $env:PYTHONPATH = $savedPythonPath
        $env:THA4_PORTABLE_ROOT = $savedPortableRoot
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Face capture UI probe"
        } else {
            Write-Host "[MISSING] Face capture UI probe (load preview / portable_paths)"
            Write-Host "  $faceProbeOut"
            $failed++
        }
    }
    $ErrorActionPreference = $prevEap
}

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) {
        throw "Deploy verification failed ($failed missing item(s))."
    }
    Write-Host "Deploy verification: $failed item(s) still missing."
    exit 1
}

Write-Host "Deploy verification passed."
Write-Host ""
exit 0
