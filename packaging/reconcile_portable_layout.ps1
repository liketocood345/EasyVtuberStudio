param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot

function Ensure-DemoDataLink {
    param(
        [string]$RepoSubPath,
        [string]$DemoSubPath
    )
    $repoPath = Resolve-PortableRootPath $PortableRoot $RepoSubPath
    $demoPath = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\$DemoSubPath"
    if (-not (Test-Path $repoPath)) {
        Remove-PathForLayout $demoPath
        return
    }
    Ensure-JunctionLink -LinkPath $demoPath -TargetPath $repoPath | Out-Null
}

function Ensure-Tha3PythonPackageLink {
    $src = Join-Path $PortableRoot "deps\tha3\tha3_src"
    $link = Join-Path $PortableRoot "deps\tha3\tha3"
    if (-not (Test-Path $src)) { return }
    Ensure-JunctionLink -LinkPath $link -TargetPath $src | Out-Null
}

Write-Host ""
Write-Host "Reconciling portable layout: $PortableRoot"
Write-Host ""

$faceRecord = Get-AddonRecord -Manifest $manifest -AddonId "face_puppeteer"
$tha3Record = Get-AddonRecord -Manifest $manifest -AddonId "tha3_models"
$tha4Record = Get-AddonRecord -Manifest $manifest -AddonId "tha4_training"

$faceInstalled = Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $faceRecord
$tha3Installed = Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $tha3Record
$tha4Installed = Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $tha4Record

# --- face_puppeteer ---
$venvTarget = Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerVenvRelative)
$mediapipeTarget = Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerMediapipeRelative)
$runtimeVenvLink = Join-Path $PortableRoot "runtime\venv"
$repoMediapipeLink = Resolve-PortableRootPath $PortableRoot "data/thirdparty/mediapipe"

if ($faceInstalled) {
    Ensure-JunctionLink -LinkPath $runtimeVenvLink -TargetPath $venvTarget | Out-Null
    Ensure-JunctionLink -LinkPath $repoMediapipeLink -TargetPath $mediapipeTarget | Out-Null
    Write-Host "[OK] face_puppeteer links -> runtime\venv, data\thirdparty\mediapipe"
} else {
    Remove-PathForLayout $runtimeVenvLink
    $runtimeRoot = Join-Path $PortableRoot "runtime"
    if (Test-Path $runtimeRoot) {
        $remaining = Get-ChildItem $runtimeRoot -Force -ErrorAction SilentlyContinue
        if (-not $remaining) { Remove-PathForLayout $runtimeRoot }
    }
    Remove-PathForLayout $repoMediapipeLink
    Ensure-Directory (Join-Path $PortableRoot "data\thirdparty")
    Write-Host "[OK] face_puppeteer removed -> cleared runtime/mediapipe links"
}

# --- tha3_models ---
$tha3Target = Get-AddonFolderAbsolute -PortableRoot $PortableRoot -AddonRecord $tha3Record
$depsModelsLink = Join-Path $PortableRoot "deps\tha3\models"
if ($tha3Installed) {
    Ensure-JunctionLink -LinkPath $depsModelsLink -TargetPath $tha3Target | Out-Null
    Write-Host "[OK] tha3_models link -> deps\tha3\models"
} else {
    Remove-PathForLayout $depsModelsLink
    Restore-Tha3ModelsReadme -PortableRoot $PortableRoot
    Write-Host "[OK] tha3_models removed -> deps\tha3\models README restored"
}

# --- tha4_training ---
$tha4AddonRoot = Get-AddonFolderAbsolute -PortableRoot $PortableRoot -AddonRecord $tha4Record
$demoTha4Link = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4"
$demoPoseLink = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\pose_dataset.pt"
$tha4Target = Join-Path $tha4AddonRoot "tha4"
$poseTarget = Join-Path $tha4AddonRoot "pose_dataset.pt"

if ($tha4Installed) {
    Ensure-JunctionLink -LinkPath $demoTha4Link -TargetPath $tha4Target | Out-Null
    Ensure-FileJunctionLink -LinkPath $demoPoseLink -TargetPath $poseTarget | Out-Null
    Write-Host "[OK] tha4_training links -> demo\data\tha4, pose_dataset.pt"
} else {
    Remove-PathForLayout $demoTha4Link
    Remove-PathForLayout $demoPoseLink
    Restore-Tha4TrainingPlaceholder -PortableRoot $PortableRoot
    Write-Host "[OK] tha4_training removed -> demo placeholder restored"
}

# --- CORE demo mirrors (character_models, images, distill_examples) ---
$demoData = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data"
Ensure-Directory $demoData
Ensure-DemoDataLink "data/character_models" "character_models"
Ensure-DemoDataLink "data/images" "images"
Ensure-DemoDataLink "data/distill_examples" "distill_examples"

if ($tha3Installed) {
    Ensure-DemoDataLink "addons/tha3_models" "models"
} else {
    Remove-PathForLayout (Join-Path $demoData "models")
}

if ($faceInstalled) {
    Ensure-DemoDataLink "data/thirdparty/mediapipe" "thirdparty\mediapipe"
} else {
    Remove-PathForLayout (Join-Path $demoData "thirdparty")
}

Ensure-Tha3PythonPackageLink

Write-Host ""
Write-Host "Layout reconcile complete."
Write-Host ""
