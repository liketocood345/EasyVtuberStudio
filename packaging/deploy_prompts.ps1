param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Confirmed
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Test-DeployOverwriteTargets {
    $targets = @(
        (Join-Path $PortableRoot "addons\face_puppeteer\venv"),
        (Join-Path $PortableRoot "runtime\venv"),
        (Join-Path $PortableRoot "workspace\.deploy_complete"),
        (Join-Path $PortableRoot "workspace\.portable_bootstrap_done")
    )
    return @($targets | Where-Object { Test-Path $_ })
}

function Show-DeployWarning {
    param([string[]]$ExistingPaths)

    Write-Host ""
    Write-Host "============================================================"
    Write-Host " EasyVtuberStudio - DEPLOY"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host " Optional add-ons install to addons\ and link into CORE paths."
    Write-Host ""
    Write-Host " DEPLOY tiers (enter numbers; Press Enter = [1] only):"
    Write-Host "   [1] basic_run        - Mouse + THA4 Student runtime (~2-4 GB)"
    Write-Host "   [2] openseeface      - OpenSeeFace facetracker + models (~0.2 GB)"
    Write-Host "   [3] face_puppeteer   - Camera face capture + MediaPipe (~3-4 GB)"
    Write-Host "   [4] tha3_models      - THA3 portrait weights (~2 GB)"
    Write-Host "   [5] tha4_training    - THA4 teacher + pose dataset (~1.5-3 GB)"
    Write-Host "   [6] output_enhancement - NN super-resolution + RIFE ONNX (~0.8 GB+)"
    Write-Host ""
    Write-Host " Re-running may overwrite addons\face_puppeteer\venv."
    Write-Host " Already-downloaded model packs are usually skipped."
    Write-Host ""
    if ($ExistingPaths.Count -gt 0) {
        Write-Host " Existing deploy artifacts detected:"
        foreach ($rel in $ExistingPaths) {
            $short = $rel.Substring($PortableRoot.Length).TrimStart("\")
            if (-not $short) { $short = $rel }
            Write-Host "   - $short"
        }
        Write-Host ""
    }
    Write-Host " Requires: Windows 10/11 x64, internet, ~15 GB free disk space."
    Write-Host " May take 10-40 minutes. Do not close this window."
    Write-Host ""
}

if ($Confirmed) {
    return
}

$existing = Test-DeployOverwriteTargets
Show-DeployWarning -ExistingPaths $existing

$answer = Read-Host "Open add-on menu now? Type Y and press Enter (any other key cancels)"
if ($answer -notmatch '^[Yy]$') {
    Write-Host ""
    Write-Host "Cancelled. No files were changed."
    exit 1
}

exit 0
