param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string]$TierInput = "",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$DeployTierCatalog = @(
    @{ Number = 1; PackageId = "mouse_student"; Label = "basic_run        - Minimal runtime for Mouse + THA4 Student (PyTorch + wx)" },
    @{ Number = 2; PackageId = "openseeface"; Label = "openseeface      - OpenSeeFace face capture (facetracker + models)" },
    @{ Number = 3; PackageId = "face_puppeteer"; Label = "face_puppeteer   - MediaPipe face capture (includes full Python runtime)" },
    @{ Number = 4; PackageId = "tha3_models"; Label = "tha3_models      - THA3 portrait weights" },
    @{ Number = 5; PackageId = "tha4_training"; Label = "tha4_training    - THA4 teacher + pose dataset (training / distill)" },
    @{ Number = 6; PackageId = "output_enhancement"; Label = "output_enhancement - NN super-resolution + RIFE (onnxruntime)" }
)

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

function Test-TierInputHasSeparator {
    param([string]$Text)
    foreach ($ch in @(' ', "`t", ',', ';')) {
        if ($Text.Contains($ch)) {
            return $true
        }
    }
    return $false
}

function Split-TierInputTokens {
    param([string]$Text)
    $out = @()
    $chunks = $Text -split '\s+'
    foreach ($chunk in $chunks) {
        if ([string]::IsNullOrWhiteSpace($chunk)) { continue }
        foreach ($piece in ($chunk -split ',')) {
            if ([string]::IsNullOrWhiteSpace($piece)) { continue }
            foreach ($sub in ($piece -split ';')) {
                if (-not [string]::IsNullOrWhiteSpace($sub)) {
                    $out += $sub.Trim()
                }
            }
        }
    }
    return $out
}

function Parse-DeployTierNumbers {
    param(
        [string]$Raw,
        [int]$MaxTier
    )
    if ([string]::IsNullOrWhiteSpace($Raw)) {
        return @(1)
    }

    $trimmed = $Raw.Trim()
    $numbers = @()

    if (Test-TierInputHasSeparator $trimmed) {
        $parts = Split-TierInputTokens $trimmed
        foreach ($part in $parts) {
            if ($part -notmatch '^\d+$') {
                throw "Invalid tier token: $part"
            }
            $numbers += [int]$part
        }
    } elseif ($trimmed -match '^\d+$') {
        $remaining = $trimmed
        while ($remaining.Length -gt 0) {
            if ($remaining.Length -ge 2 -and $remaining.StartsWith("10")) {
                $numbers += 10
                $remaining = $remaining.Substring(2)
            } else {
                $numbers += [int]$remaining.Substring(0, 1)
                $remaining = $remaining.Substring(1)
            }
        }
    } else {
        throw "Invalid tier input: $trimmed"
    }

    $invalid = @($numbers | Where-Object { $_ -lt 1 -or $_ -gt $MaxTier })
    if ($invalid.Count -gt 0) {
        throw "Unknown tier number(s): $($invalid -join ', ') (valid: 1-$MaxTier)"
    }

    return @($numbers | Select-Object -Unique)
}

function Map-TierNumbersToPackageIds {
    param([int[]]$TierNumbers)

    $byNumber = @{}
    foreach ($tier in $DeployTierCatalog) {
        $byNumber[[int]$tier.Number] = [string]$tier.PackageId
    }

    $selected = @()
    foreach ($n in @($TierNumbers)) {
        $selected += $byNumber[$n]
    }
    return @($selected | Where-Object { $_ } | Select-Object -Unique)
}

function Read-DeployTierChoices {
    $maxTier = [int]$DeployTierCatalog[-1].Number

    Write-Host ""
    Write-Host "Select install tiers (enter numbers; up to $maxTier tiers):"
    Write-Host ""
    foreach ($tier in $DeployTierCatalog) {
        Write-Host ("  [{0}] {1}" -f $tier.Number, $tier.Label)
    }
    Write-Host ""
    Write-Host "  Face capture: install [2] OR [3] (either enables camera face tracking)."
    Write-Host ""
    Write-Host "  Examples: 1  |  2  |  1 3 6  |  136  (each digit is a tier number)"
    Write-Host "  Press Enter without typing = install [1] basic_run only."
    Write-Host ""

    $rawInput = $TierInput
    if (-not $NonInteractive) {
        $rawInput = Read-Host "Tier numbers to install"
    } elseif ([string]::IsNullOrWhiteSpace($rawInput)) {
        $rawInput = ""
    }

    $tierNumbers = Parse-DeployTierNumbers -Raw $rawInput -MaxTier $maxTier
    $selected = Map-TierNumbersToPackageIds -TierNumbers $tierNumbers

    if ($selected.Count -eq 0) {
        Write-Host ""
        Write-Host "Nothing selected. At least [1] basic_run or a face-capture tier ([2]/[3]) is required."
        Write-Host "Re-run DEPLOY.bat and enter 1 (or press Enter for default)."
        exit 1
    }

    $hasBasic = $tierNumbers -contains 1
    $hasFace = $tierNumbers -contains 3
    $hasTha3 = $tierNumbers -contains 4
    $hasTha4 = $tierNumbers -contains 5

    Write-Host ""
    Write-Host "Selected tiers: $($tierNumbers -join ', ') -> $($selected -join ', ')"

    if (-not $hasBasic -and -not $hasFace -and ($hasTha3 -or $hasTha4)) {
        Write-Host ""
        Write-Host "Warning: THA3/THA4 packs need basic_run or face_puppeteer for Python runtime."
        Write-Host "Continuing anyway; install may fail verification."
        Write-Host ""
    }

    return @($selected)
}

Show-AddonStatus
return @(Read-DeployTierChoices)
