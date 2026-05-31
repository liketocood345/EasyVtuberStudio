param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"
$launcherDir = Join-Path $RepoRoot "packaging\launcher"
$icon = Join-Path $RepoRoot "assets\branding\app-icon-source.ico"
$python = Join-Path $RepoRoot "addons\face_puppeteer\venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = Join-Path $RepoRoot "runtime\venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    $python = Join-Path $RepoRoot "workspace\student_venv\Scripts\python.exe"
}
if (-not (Test-Path $python)) {
    throw "Python venv not found under repo root. Install face_puppeteer add-on or run EasyVtuberStudio.exe once for student_venv."
}

& $python -m pip install -q pyinstaller

function Build-Launcher(
    [string]$ScriptName,
    [string]$ExeName,
    [switch]$UseIcon
) {
    $scriptPath = Join-Path $launcherDir $ScriptName
    $distDir = Join-Path $RepoRoot "packaging\launcher\dist"
    $workDir = Join-Path $RepoRoot "packaging\launcher\build\$ExeName"
    New-Item -ItemType Directory -Force -Path $distDir | Out-Null
    if (Test-Path $workDir) { Remove-Item $workDir -Recurse -Force }

    $experimentDir = Join-Path $RepoRoot "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview"
    $args = @(
        "--noconfirm",
        "--onefile",
        "--noconsole",
        "--name", $ExeName,
        "--distpath", $distDir,
        "--workpath", (Join-Path $RepoRoot "packaging\launcher\build"),
        "--specpath", (Join-Path $RepoRoot "packaging\launcher"),
        "--paths", $experimentDir,
        "--hidden-import", "portable_paths",
        "--hidden-import", "portable_bootstrap",
        "--hidden-import", "tha3_paths"
    )
    if ($UseIcon -and (Test-Path $icon)) {
        $args += @("--icon", $icon)
    }
    $args += $scriptPath

    Write-Host "Building $ExeName ..."
    & $python -m PyInstaller @args
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $ExeName" }

    $built = Join-Path $distDir "$ExeName.exe"
    if ($ExeName -eq "THA4Train") {
        $target = Join-Path $RepoRoot "scripts\launch\$ExeName.exe"
    } else {
        $target = Join-Path $RepoRoot "$ExeName.exe"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
    Copy-Item -Force $built $target
    Write-Host "Wrote $target"
}

# Main app: equivalent to 》》》》start《《《《.bat -> run_load_preview_puppeteer.bat
Build-Launcher "launch_face_puppeteer.py" "EasyVtuberStudio" -UseIcon
# Training entry: Distiller UI, utility launcher without custom icon
Build-Launcher "launch_tha4train.py" "THA4Train"
Write-Host "Launcher build complete."
