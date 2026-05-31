param(
    [string]$PortableRoot = "",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
if (-not $PortableRoot) {
    $PortableRoot = Resolve-PortableRoot (Join-Path $PSScriptRoot "..")
} else {
    $PortableRoot = Resolve-PortableRoot $PortableRoot
}

function Move-IfRealContent {
    param(
        [string]$Source,
        [string]$Dest
    )
    if (-not (Test-Path $Source)) { return }
    if (Test-IsReparsePoint $Source) {
        Write-Host "[SKIP] $Source is a junction link"
        return
    }
    if ($DryRun) {
        Write-Host "[DRY] Would move $Source -> $Dest"
        return
    }
    Ensure-Directory (Split-Path $Dest -Parent)
    if (Test-Path $Dest) {
        Remove-Item -LiteralPath $Dest -Recurse -Force
    }
    Move-Item -LiteralPath $Source $Dest -Force
    Write-Host "[OK] Moved $Source -> $Dest"
}

Write-Host ""
Write-Host "Migrating legacy layout to addons/ under: $PortableRoot"
Write-Host ""

$faceVenvDest = Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerVenvRelative)
$faceMpDest = Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerMediapipeRelative)
$legacyVenv = Join-Path $PortableRoot "runtime\venv"
$legacyMp = Join-Path $PortableRoot "data\thirdparty\mediapipe"

Move-IfRealContent $legacyVenv $faceVenvDest
if (Test-Path $legacyMp) {
    if (-not (Test-IsReparsePoint $legacyMp)) {
        Move-IfRealContent $legacyMp $faceMpDest
    }
}

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot

$tha3Dest = Get-AddonFolderAbsolute -PortableRoot $PortableRoot -AddonRecord (Get-AddonRecord -Manifest $manifest -AddonId "tha3_models")
$legacyTha3 = Join-Path $PortableRoot "deps\tha3\models"
if (Test-Path $legacyTha3) {
    $hasPt = Get-ChildItem $legacyTha3 -Recurse -Filter "*.pt" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($hasPt -and -not (Test-IsReparsePoint $legacyTha3)) {
        Move-IfRealContent $legacyTha3 $tha3Dest
    }
}

$tha4Record = Get-AddonRecord -Manifest $manifest -AddonId "tha4_training"
$tha4AddonRoot = Get-AddonFolderAbsolute -PortableRoot $PortableRoot -AddonRecord $tha4Record
$demoTha4 = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4"
$demoPose = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\pose_dataset.pt"

if (Test-Path $demoTha4) {
    if (-not (Test-IsReparsePoint $demoTha4)) {
        $teacher = Join-Path $demoTha4 "face_morpher.pt"
        if (Test-Path $teacher) {
            Move-IfRealContent $demoTha4 (Join-Path $tha4AddonRoot "tha4")
        }
    }
}
if ((Test-Path $demoPose) -and -not (Test-IsReparsePoint $demoPose)) {
    Move-IfRealContent $demoPose (Join-Path $tha4AddonRoot "pose_dataset.pt")
}

if (-not $DryRun) {
    & (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot
}

Write-Host ""
Write-Host "Migration complete."
Write-Host ""
