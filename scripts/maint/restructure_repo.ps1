param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path,
    [switch]$ForkLayoutOnly
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path $RepoRoot).Path

$docsFiles = @(
    "BACKUP.md", "CHANGELOG.md", "DEPLOY.md", "FORK_ROOT.md", "HANDOVER.md",
    "HARDWARE_REQUIREMENTS.md", "oid.md", "README-detail.md", "README-EN.md",
    "READMEfrom-main.md", "SOFTWARE_REQUIREMENTS_PLAN.md", "TROUBLESHOOTING_QA.md"
)
$launchFiles = @(
    "run_load_preview_puppeteer.bat", "EasyVtuberStudio.bat", "THA4Train.bat",
    "THA4_Distill.bat", "THA4_DownloadAssets.bat", "THA3_DownloadModels.bat",
    "THA4_DownloadTrainingAssets.bat", "》》》》start《《《《.bat"
)
$scriptFiles = @("activate-venv.bat", "build_launchers.bat", "run.bat")
$maintFiles = @(
    "migrate_from_bai_custom.ps1", "sync_from_fork.ps1",
    "sync_plans_from_bai_custom.ps1", "sync_to_fork.ps1"
)
$packagingFiles = @("assets_manifest.json", "PORTABLE_VERSION.txt")

function Ensure-Dir([string]$Path) {
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

Ensure-Dir (Join-Path $RepoRoot "docs")
Ensure-Dir (Join-Path $RepoRoot "scripts\launch")
Ensure-Dir (Join-Path $RepoRoot "scripts\maint")
Ensure-Dir (Join-Path $RepoRoot "packaging")

foreach ($name in $docsFiles) {
    $src = Join-Path $RepoRoot $name
    if (Test-Path $src) {
        Move-Item -Force $src (Join-Path $RepoRoot "docs\$name")
    }
}
foreach ($name in $launchFiles) {
    $src = Join-Path $RepoRoot $name
    $dest = Join-Path $RepoRoot "scripts\launch\$name"
    if (Test-Path $src) {
        if ((Test-Path $dest) -and ((Get-Item $src).FullName -ne (Get-Item $dest).FullName)) {
            Remove-Item -Force $src
        } else {
            Move-Item -Force $src $dest
        }
    }
}
foreach ($name in $scriptFiles) {
    $src = Join-Path $RepoRoot $name
    if (Test-Path $src) {
        Move-Item -Force $src (Join-Path $RepoRoot "scripts\$name")
    }
}
foreach ($name in $maintFiles) {
    $src = Join-Path $RepoRoot $name
    if (Test-Path $src) {
        $dest = Join-Path $RepoRoot "scripts\maint\$name"
        if (-not (Test-Path $dest)) {
            Move-Item -Force $src $dest
        }
    }
}
foreach ($name in $packagingFiles) {
    $src = Join-Path $RepoRoot $name
    if (Test-Path $src) {
        Move-Item -Force $src (Join-Path $RepoRoot "packaging\$name")
    }
}

$trainExe = Join-Path $RepoRoot "THA4Train.exe"
if (Test-Path $trainExe) {
    Move-Item -Force $trainExe (Join-Path $RepoRoot "scripts\launch\THA4Train.exe")
}

foreach ($log in Get-ChildItem $RepoRoot -Filter "run_load_preview_runtime*.log" -File -ErrorAction SilentlyContinue) {
    Remove-Item -Force $log.FullName
}

if ($ForkLayoutOnly) {
    foreach ($item in Get-ChildItem $RepoRoot -File -Force) {
        $name = $item.Name
        if ($name -eq "README.md" -or $name -eq "EasyVtuberStudio.exe" -or $name -eq "DEPLOY.bat") { continue }
        if ($name.StartsWith(".")) { continue }
        if ($name -eq "LICENSE") {
            Move-Item -Force $item.FullName (Join-Path $RepoRoot "docs\LICENSE")
            continue
        }
        $targetDocs = Join-Path $RepoRoot "docs\$name"
        $targetScripts = Join-Path $RepoRoot "scripts\$name"
        $targetLaunch = Join-Path $RepoRoot "scripts\launch\$name"
        if ($name -match "\.(md|txt)$") {
            Move-Item -Force $item.FullName $targetDocs
        } elseif ($name -match "\.(bat|exe)$") {
            if ($name -eq "THA4Train.exe") {
                Move-Item -Force $item.FullName $targetLaunch
            } else {
                Move-Item -Force $item.FullName $targetLaunch
            }
        } elseif ($name -match "\.ps1$") {
            Ensure-Dir (Join-Path $RepoRoot "scripts\maint")
            Move-Item -Force $item.FullName (Join-Path $RepoRoot "scripts\maint\$name")
        }
    }
}

Write-Host "Restructured $RepoRoot"
