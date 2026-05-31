param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string[]]$PackageIds = @(),
    [switch]$SkipRuntime,
    [switch]$SkipUpstream,
    [switch]$LaunchApp,
    [switch]$Confirmed,
    [switch]$ForceRebuildRuntime,
    [switch]$IncludeTha4Training,
    [switch]$Tha4StudentOnly,
    [switch]$MouseStudentOnly,
    [switch]$ShowMenu
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
. (Join-Path $PSScriptRoot "deploy_common.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$ProgressPreference = "SilentlyContinue"
Initialize-DeploySession $PortableRoot
Write-DeployLog "DEPLOY start: $PortableRoot"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
    Write-DeployLog $Message
}

function Assert-ScriptSucceeded([string]$StepLabel) {
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "$StepLabel failed (exit=$LASTEXITCODE)"
    }
}

function Expand-DeployPackageIds {
    param([string[]]$Ids)
    $expanded = @()
    foreach ($id in @($Ids)) {
        if ([string]::IsNullOrWhiteSpace($id)) { continue }
        if ($id -match ',') {
            $expanded += @($id -split '\s*,\s*' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
        } else {
            $expanded += $id.Trim()
        }
    }
    return @($expanded | Select-Object -Unique)
}

function Resolve-DeployPackageIds {
    if ($PackageIds.Count -gt 0) {
        return Expand-DeployPackageIds $PackageIds
    }
    if ($Tha4StudentOnly -or $MouseStudentOnly) {
        return @("mouse_student")
    }
    if ($ShowMenu -or (-not $Confirmed)) {
        $menuScript = Join-Path $PSScriptRoot "deploy_menu.ps1"
        if (Test-Path $menuScript) {
            return @(& $menuScript -PortableRoot $PortableRoot)
        }
    }
    $ids = @("face_puppeteer", "tha3_models")
    if ($IncludeTha4Training) {
        $ids += "tha4_training"
    }
    return $ids
}

try {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " EasyVtuberStudio - DEPLOY (install tiers)"
    Write-Host " Tiers: basic_run, face_puppeteer, tha3_models, tha4_training"
    Write-Host "============================================================"

    $selected = @(Resolve-DeployPackageIds | Select-Object -Unique)
    if ($selected.Count -eq 0) {
        Write-Host "No packages selected."
        exit 1
    }

    Write-Host ""
    Write-Host "Selected: $($selected -join ', ')"
    Write-DeployLog "Selected: $($selected -join ', ')"

    Ensure-DeployLayoutDirectories $PortableRoot

    $promptScript = Join-Path $PSScriptRoot "deploy_prompts.ps1"
    if (-not $Confirmed -and -not $Tha4StudentOnly -and -not $ShowMenu -and (Test-Path $promptScript)) {
        & $promptScript -PortableRoot $PortableRoot
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($IncludeTha4Training -and ($selected -notcontains "tha4_training")) {
            $selected += "tha4_training"
        }
    }

    New-Item -ItemType Directory -Force -Path (Join-Path $PortableRoot "workspace") | Out-Null

    $fetchScript = Join-Path $PSScriptRoot "fetch_upstream_assets.ps1"
    $bootstrapScript = Join-Path $PSScriptRoot "bootstrap_portable.ps1"
    $reconcileScript = Join-Path $PSScriptRoot "reconcile_portable_layout.ps1"
    $verifyScript = Join-Path $PSScriptRoot "verify_deploy.ps1"
    $verifyTha4StudentScript = Join-Path $PSScriptRoot "verify_tha4_student.ps1"

    if (-not (Test-Path $fetchScript)) {
        throw "Missing packaging\fetch_upstream_assets.ps1 under $PortableRoot"
    }

    $installFace = $selected -contains "face_puppeteer"
    $installMouseStudent = ($selected -contains "mouse_student") -or $MouseStudentOnly.IsPresent
    $installTha3 = $selected -contains "tha3_models"
    $installTha4 = $selected -contains "tha4_training"

    if ($installMouseStudent) {
        if (Test-MouseStudentRuntime -PortableRoot $PortableRoot) {
            Write-Step "mouse student: already installed; skipping runtime bootstrap"
        } else {
            Write-Step "mouse student: minimal Python runtime (workspace\student_venv; torch + wx, no MediaPipe)"
            if (-not (Test-Path $bootstrapScript)) {
                throw "Missing packaging\bootstrap_portable.ps1"
            }
            & $bootstrapScript -PortableRoot $PortableRoot -ForceRebuildRuntime:$ForceRebuildRuntime -MouseStudentOnly
            Assert-ScriptSucceeded "Mouse student runtime bootstrap"
        }
    }

    if ($installFace) {
        Write-Step "face_puppeteer: MediaPipe .task"
        & $fetchScript -PortableRoot $PortableRoot -PackageIds @("mediapipe_task")
        Assert-ScriptSucceeded "MediaPipe task install"

        if (-not $SkipRuntime) {
            Write-Step "face_puppeteer: Python runtime (addons\face_puppeteer\venv)"
            if (-not (Test-Path $bootstrapScript)) {
                throw "Missing packaging\bootstrap_portable.ps1"
            }
            & $bootstrapScript -PortableRoot $PortableRoot -ForceRebuildRuntime:$ForceRebuildRuntime
            Assert-ScriptSucceeded "Runtime bootstrap"
        } else {
            Write-Step "face_puppeteer: Skipped runtime (-SkipRuntime)"
        }
    }

    if ($installTha3 -and -not $SkipUpstream) {
        Write-Step "tha3_models: THA3 portrait weights"
        & $fetchScript -PortableRoot $PortableRoot -PackageIds @("tha3_models")
        Assert-ScriptSucceeded "THA3 models install"
    } elseif ($installTha3) {
        Write-Step "tha3_models: Skipped (-SkipUpstream)"
    }

    if ($installTha4 -and -not $SkipUpstream) {
        Write-Step "tha4_training: teacher weights + pose dataset"
        & $fetchScript -PortableRoot $PortableRoot -PackageIds @("tha4_teacher_training")
        Assert-ScriptSucceeded "THA4 training pack install"
    } elseif ($installTha4) {
        Write-Step "tha4_training: Skipped (-SkipUpstream)"
    }

    Write-Step "Reconcile layout + verification"
    if (Test-Path $reconcileScript) {
        & $reconcileScript -PortableRoot $PortableRoot
    }

    if ($Tha4StudentOnly -or $MouseStudentOnly -or ($installMouseStudent -and -not $installTha3 -and -not $installTha4 -and -not $installFace)) {
        if (-not (Test-Path (Join-Path $PSScriptRoot "verify_mouse_student.ps1"))) {
            throw "Missing packaging\verify_mouse_student.ps1"
        }
        & (Join-Path $PSScriptRoot "verify_mouse_student.ps1") -PortableRoot $PortableRoot -Strict
        Assert-ScriptSucceeded "Mouse student verification"
    } elseif ($installFace -and -not $installTha3 -and -not $installTha4) {
        if (-not (Test-Path $verifyTha4StudentScript)) {
            throw "Missing packaging\verify_tha4_student.ps1"
        }
        & $verifyTha4StudentScript -PortableRoot $PortableRoot -Strict
        Assert-ScriptSucceeded "THA4 student verification"
    } else {
        $verifyArgs = @{
            PortableRoot         = $PortableRoot
            Strict               = $true
            RequireFacePuppeteer = $installFace
            RequireTha3Models    = $installTha3
            IncludeTha4Training  = $installTha4
        }
        & $verifyScript @verifyArgs
        Assert-ScriptSucceeded "Deploy verification"
    }

    $marker = Join-Path $PortableRoot "workspace\.deploy_complete"
    Set-Content -Path $marker -Value ((Get-Date -Format o) + "`npackages=" + ($selected -join ",")) -Encoding UTF8

    Write-Host ""
    Write-Host "DEPLOY complete."
    Write-Host "  Installed: $($selected -join ', ')"
    Write-Host "  Basic (Mouse + Student): EasyVtuberStudio.exe after [1] basic_run or [2] face_puppeteer"
    Write-Host "  Face capture: needs face_puppeteer tier"
    Write-Host "  THA3 portrait:  switch mode in app (needs tha3_models tier)"
    if ($installTha4) {
        Write-Host "  THA4 training:  scripts\launch\THA4Train.exe"
    } else {
        Write-Host "  THA4 training:  run DEPLOY.bat and choose tier [4]"
    }
    Write-Host ""
    Write-DeployLog "DEPLOY complete: $($selected -join ', ')"

    if ($LaunchApp) {
        $exe = Join-Path $PortableRoot "EasyVtuberStudio.exe"
        if (Test-Path $exe) {
            Start-Process -FilePath $exe -WorkingDirectory $PortableRoot
        }
    }
} catch {
    Write-DeployFailure $_
    Write-Host ""
    Write-Host "Log: $(Join-Path $PortableRoot 'workspace\deploy.log')"
    Write-Host "Tips: run DEPLOY.bat from the folder containing EasyVtuberStudio.exe; keep internet on; reserve ~4 GB disk for tier [1]."
    exit 1
}
