# Restore develop full 3-module install from local caches (no re-download when possible).
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\restore_develop_full_install.ps1

param(
    [string]$RepoRoot = "",
    [string]$BundleRoot = "E:\THA4_bundle",
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = Join-Path $PSScriptRoot "..\.."
}

. (Join-Path $RepoRoot "packaging\addon_paths.ps1")
$RepoRoot = Resolve-PortableRoot $RepoRoot

$downloads = Join-Path $RepoRoot "workspace\upstream_downloads"
$tha3Staging = Join-Path $downloads "staging_talking-head-anime-3-models_zip"
$tha4Staging = Join-Path $downloads "staging_tha4-models_zip"
$poseSrc = Join-Path $downloads "pose_dataset.pt"

$bundleVenv = Join-Path $BundleRoot "talking-head-anime-4-demo\venv"
$bundleMp = Join-Path $BundleRoot "talking-head-anime-4-demo\data\thirdparty\mediapipe\face_landmarker_v2_with_blendshapes.task"

function Copy-Tree([string]$Source, [string]$Dest) {
    if (-not (Test-Path $Source)) {
        throw "Missing source: $Source"
    }
    Ensure-Directory (Split-Path $Dest -Parent)
    if (Test-Path $Dest) {
        Remove-Item -LiteralPath $Dest -Recurse -Force
    }
    robocopy $Source $Dest /E /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed: $Source -> $Dest (exit=$LASTEXITCODE)"
    }
}

Write-Host ""
Write-Host "Restoring develop full install: $RepoRoot"
Write-Host ""

# --- face_puppeteer: venv + mediapipe ---
$faceRoot = Resolve-PortableRootPath $RepoRoot "addons/face_puppeteer"
$faceVenv = Join-Path $faceRoot "venv"
$faceMpDir = Join-Path $faceRoot "mediapipe"
$faceMpTask = Join-Path $faceMpDir "face_landmarker_v2_with_blendshapes.task"

if (-not (Test-Path (Join-Path $faceVenv "Scripts\python.exe"))) {
    Write-Host "[1/3] face_puppeteer venv <- $bundleVenv"
    Copy-Tree $bundleVenv $faceVenv
} else {
    Write-Host "[1/3] face_puppeteer venv already present"
}

if (-not (Test-Path $faceMpTask)) {
    if (-not (Test-Path $bundleMp)) {
        throw "Missing MediaPipe task: $bundleMp"
    }
    Write-Host "[1/3] mediapipe task <- $bundleMp"
    Ensure-Directory $faceMpDir
    Copy-Item -Force $bundleMp $faceMpTask
} else {
    Write-Host "[1/3] mediapipe task already present"
}

# --- tha3_models ---
$tha3Dest = Resolve-PortableRootPath $RepoRoot "addons/tha3_models"
$tha3Ok = (Test-Path (Join-Path $tha3Dest "separable_half\face_morpher.pt")) -and
    (Test-Path (Join-Path $tha3Dest "separable_half\editor.pt"))
if (-not $tha3Ok) {
    if (-not (Test-Path $tha3Staging)) {
        throw "Missing THA3 staging cache: $tha3Staging`nRun DEPLOY tier [3] once with network."
    }
    Write-Host "[2/3] tha3_models <- $tha3Staging"
    Ensure-Directory $tha3Dest
    foreach ($variant in @("separable_float", "separable_half", "standard_float", "standard_half")) {
        $src = Join-Path $tha3Staging $variant
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $tha3Dest $variant
        Copy-Tree $src $dst
    }
} else {
    Write-Host "[2/3] tha3_models already present"
}

# --- tha4_training ---
$tha4Root = Resolve-PortableRootPath $RepoRoot "addons/tha4_training"
$tha4Teacher = Join-Path $tha4Root "tha4"
$tha4Pose = Join-Path $tha4Root "pose_dataset.pt"
$tha4Ok = (Test-Path (Join-Path $tha4Teacher "face_morpher.pt")) -and (Test-Path $tha4Pose)

if (-not $tha4Ok) {
    if (-not (Test-Path $tha4Staging)) {
        throw "Missing THA4 staging cache: $tha4Staging`nRun DEPLOY tier [4] once with network."
    }
    Write-Host "[3/3] tha4_training teacher <- $tha4Staging"
    Ensure-Directory $tha4Teacher
    foreach ($name in @(
            "face_morpher.pt", "body_morpher.pt", "eyebrow_decomposer.pt",
            "eyebrow_morphing_combiner.pt", "upscaler.pt"
        )) {
        $src = Join-Path $tha4Staging $name
        if (-not (Test-Path $src)) {
            $found = Get-ChildItem $tha4Staging -Recurse -Filter $name -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { $src = $found.FullName }
        }
        if (Test-Path $src) {
            Copy-Item -Force $src (Join-Path $tha4Teacher $name)
        }
    }
    if (-not (Test-Path $poseSrc)) {
        $poseAlt = Join-Path $BundleRoot "talking-head-anime-4-demo\data\pose_dataset.pt"
        if (Test-Path $poseAlt) { $poseSrc = $poseAlt }
    }
    if (-not (Test-Path $poseSrc)) {
        throw "Missing pose_dataset.pt in $downloads or $BundleRoot"
    }
    Write-Host "[3/3] pose_dataset.pt <- $poseSrc"
    Ensure-Directory $tha4Root
    Copy-Item -Force $poseSrc $tha4Pose
} else {
    Write-Host "[3/3] tha4_training already present"
}

Write-Host ""
Write-Host "Reconciling layout ..."
& (Join-Path $RepoRoot "packaging\reconcile_portable_layout.ps1") -PortableRoot $RepoRoot | Out-Null

if ($SkipVerify) {
    Write-Host "Restore complete (verify skipped)."
    exit 0
}

Write-Host ""
Write-Host "Verifying full install ..."
& (Join-Path $RepoRoot "packaging\verify_full_install.ps1") -PortableRoot $RepoRoot -Strict
exit $LASTEXITCODE
