param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Strict,
    [switch]$RequireRuntime
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Resolve-PortablePath([string]$RelativePath) {
    return Join-Path $PortableRoot ($RelativePath -replace "/", "\")
}

function Test-RequiredFile([string]$Label, [string]$RelativePath, [ref]$Failed) {
    $path = Resolve-PortablePath $RelativePath
    if (Test-Path $path) {
        Write-Host "[OK] $Label"
        return $true
    }
    Write-Host "[MISSING] $Label -> $RelativePath"
    $Failed.Value++
    return $false
}

function Test-MustNotExist([string]$Label, [string]$RelativePath, [ref]$Failed) {
    $path = Resolve-PortablePath $RelativePath
    if (-not (Test-Path $path)) {
        Write-Host "[OK] not bundled: $Label"
        return $true
    }
    Write-Host "[UNEXPECTED] $Label -> $RelativePath"
    $Failed.Value++
    return $false
}

Write-Host ""
Write-Host "Portable ZIP verification: $PortableRoot"
Write-Host ""

$failed = 0
$failedRef = [ref]$failed

Test-RequiredFile "EasyVtuberStudio.exe" "EasyVtuberStudio.exe" $failedRef | Out-Null
Test-RequiredFile "DEPLOY.bat" "DEPLOY.bat" $failedRef | Out-Null
Test-RequiredFile "deploy script" "packaging\deploy_portable.ps1" $failedRef | Out-Null
Test-RequiredFile "load preview entry" "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py" $failedRef | Out-Null

Test-RequiredFile "bai student yaml" "data\character_models\baiten_from_project_forlon9\bai_450k\character_model\character_model.yaml" $failedRef | Out-Null
Test-RequiredFile "bai face_morpher.pt" "data\character_models\baiten_from_project_forlon9\bai_450k\character_model\face_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai body_morpher.pt" "data\character_models\baiten_from_project_forlon9\bai_450k\character_model\body_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai character.png" "data\character_models\baiten_from_project_forlon9\bai_450k\character_model\character.png" $failedRef | Out-Null

if ($RequireRuntime) {
    if (Test-FacePuppeteerVenv -PortableRoot $PortableRoot) {
        Write-Host "[OK] Python runtime (face_puppeteer add-on)"
    } else {
        Test-RequiredFile "Python runtime" "addons/face_puppeteer/venv/Scripts/python.exe" $failedRef | Out-Null
    }
    $mpAddon = "addons/face_puppeteer/mediapipe/face_landmarker_v2_with_blendshapes.task"
    if (-not (Test-Path (Resolve-PortablePath $mpAddon))) {
        Test-RequiredFile "MediaPipe task" $mpAddon $failedRef | Out-Null
    } else {
        Write-Host "[OK] MediaPipe task"
    }
} else {
Test-MustNotExist "runtime venv" "runtime/venv/Scripts/python.exe" $failedRef | Out-Null
Test-MustNotExist "face_puppeteer venv in ZIP" "addons/face_puppeteer/venv/Scripts/python.exe" $failedRef | Out-Null
Test-MustNotExist "MediaPipe in ZIP" "addons/face_puppeteer/mediapipe/face_landmarker_v2_with_blendshapes.task" $failedRef | Out-Null
Test-MustNotExist "legacy MediaPipe in ZIP" "data/thirdparty/mediapipe/face_landmarker_v2_with_blendshapes.task" $failedRef | Out-Null
}

Test-MustNotExist "THA3 repo weights" "deps\tha3\models\separable_half\face_morpher.pt" $failedRef | Out-Null
Test-MustNotExist "THA4 teacher face_morpher" "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4\face_morpher.pt" $failedRef | Out-Null
Test-MustNotExist "THA4 pose_dataset.pt" "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\pose_dataset.pt" $failedRef | Out-Null

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) {
        throw "Portable ZIP verification failed ($failed issue(s))."
    }
    Write-Host "Portable ZIP verification: $failed issue(s)."
    exit 1
}

Write-Host "Portable ZIP verification passed."
if ($RequireRuntime) {
    Write-Host "  Extract -> double-click EasyVtuberStudio.exe -> THA4 student ready (no runtime download)"
    Write-Host "  THA3 portrait: run DEPLOY.bat when needed"
} else {
    Write-Host "  Slim code ZIP: run DEPLOY.bat or first exe launch to install runtime"
}
Write-Host ""
exit 0
