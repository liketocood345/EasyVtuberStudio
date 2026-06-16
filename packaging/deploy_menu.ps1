param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Show-AddonStatus {
    $manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
    $mouseReady = $false
    try {
        $mouseReady = Test-MouseStudentRuntime -PortableRoot $PortableRoot
    } catch {
        Write-Host ""
        Write-Host "  (Could not probe system Python yet; DEPLOY will install if needed.)"
    }
    Write-Host ""
    Write-Host "Current status:"
    $basicMark = if ($mouseReady) { "YES" } else { "NO " }
    Write-Host "  [$basicMark] basic_run (Mouse + THA4 Student) - workspace\student_venv or face runtime"
    foreach ($addon in @($manifest.addons)) {
        $installed = Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $addon
        $mark = if ($installed) { "YES" } else { "NO " }
        $folder = Get-AddonFolderRelative -AddonRecord $addon
        Write-Host "  [$mark] $($addon.id) - $($addon.label)"
        Write-Host "        folder: $folder"
    }
    Write-Host ""
}

function Read-YesNoPrompt {
    param(
        [string]$Prompt,
        [bool]$DefaultYes = $false
    )
    if ($NonInteractive) {
        return $DefaultYes
    }
    $hint = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    $answer = Read-Host "$Prompt $hint"
    if ([string]::IsNullOrWhiteSpace($answer)) {
        return $DefaultYes
    }
    return ($answer -match '^[Yy]')
}

function Read-DeployTierChoices {
    Write-Host ""
    Write-Host "Select install tiers (Y/N for each; press Enter = default in brackets):"
    Write-Host ""
    Write-Host "  [1] basic_run     - Minimal runtime for Mouse + THA4 Student (PyTorch + wx)"
    Write-Host "  [2] face_puppeteer - Camera face capture (MediaPipe; includes full runtime)"
    Write-Host "  [3] tha3_models    - THA3 portrait weights"
    Write-Host "  [4] tha4_training  - THA4 teacher + pose dataset (training / distill)"
    Write-Host "  [5] output_enhancement - NN super-resolution + RIFE (onnxruntime)"
    Write-Host ""

    $basic = Read-YesNoPrompt -Prompt "Install [1] basic_run (Mouse + THA4 Student)?" -DefaultYes $true
    $face = Read-YesNoPrompt -Prompt "Install [2] face_puppeteer (camera face capture)?" -DefaultYes $false
    $tha3 = Read-YesNoPrompt -Prompt "Install [3] tha3_models (THA3 portrait)?" -DefaultYes $false
    $tha4 = Read-YesNoPrompt -Prompt "Install [4] tha4_training (THA4 training pack)?" -DefaultYes $false
    $enhance = Read-YesNoPrompt -Prompt "Install [5] output_enhancement (NN SR + RIFE)?" -DefaultYes $false

    $selected = @()
    if ($basic) { $selected += "mouse_student" }
    if ($face) { $selected += "face_puppeteer" }
    if ($tha3) { $selected += "tha3_models" }
    if ($tha4) { $selected += "tha4_training" }
    if ($enhance) { $selected += "output_enhancement" }

    if ($selected.Count -eq 0) {
        Write-Host ""
        Write-Host "Nothing selected. At least [1] basic_run or [2] face_puppeteer is required to run EasyVtuberStudio."
        Write-Host "Re-run DEPLOY.bat and press Enter on the first question for defaults (basic_run only)."
        exit 1
    }

    if (-not $basic -and -not $face -and ($tha3 -or $tha4)) {
        Write-Host ""
        Write-Host "Warning: THA3/THA4 packs need basic_run or face_puppeteer for Python runtime."
        Write-Host "Continuing anyway; install may fail verification."
        Write-Host ""
    }

    return @($selected | Select-Object -Unique)
}

Show-AddonStatus
return @(Read-DeployTierChoices)
