param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Strict
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
Write-Host "THA4 student verification: $PortableRoot"
Write-Host ""

$failed = 0
$failedRef = [ref]$failed

Test-RequiredFile "EasyVtuberStudio.exe" "EasyVtuberStudio.exe" $failedRef | Out-Null
Test-RequiredFile "load preview entry" "face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py" $failedRef | Out-Null
Test-RequiredFile "bai student yaml" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character_model.yaml" $failedRef | Out-Null
Test-RequiredFile "bai face_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai body_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/body_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai character.png" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character.png" $failedRef | Out-Null

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$faceRecord = Get-AddonRecord -Manifest $manifest -AddonId "face_puppeteer"
foreach ($rel in @($faceRecord.verify)) {
    Test-RequiredFile "face_puppeteer" ([string]$rel) $failedRef | Out-Null
}

$python = $null
if (Test-FacePuppeteerVenv -PortableRoot $PortableRoot) {
    $venvRoot = Get-FacePuppeteerVenvAbsolute -PortableRoot $PortableRoot
    $python = Join-Path $venvRoot "Scripts\python.exe"
    Write-Host "[OK] Python runtime ($venvRoot)"
} else {
    Write-Host "[MISSING] Python runtime -> addons/face_puppeteer/venv"
    $failed++
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
        Write-Host "[MISSING] Python imports -> torch/wx/mediapipe"
        Write-Host "  $importOut"
        $failed++
    }
    $ErrorActionPreference = $prevEap
}

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) {
        throw "THA4 student verification failed ($failed missing item(s))."
    }
    Write-Host "THA4 student verification: $failed item(s) still missing."
    exit 1
}

Write-Host "THA4 student verification passed. EasyVtuberStudio.exe is ready for face puppeteer."
Write-Host ""
exit 0
