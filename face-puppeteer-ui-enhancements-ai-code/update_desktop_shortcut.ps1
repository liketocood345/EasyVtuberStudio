# Desktop shortcut for Load Preview puppeteer.
# Default: active dev tree next to repo root. Pass -Fork (or -PublishFork) to point at fork repo.
param(
    [switch]$Fork,
    [switch]$PublishFork,
    [string]$ShortcutPath = "",
    [string]$ActiveDevRoot = ""
)

$ErrorActionPreference = "Stop"
$ThisDir = (Resolve-Path $PSScriptRoot).Path
$RepoRoot = (Resolve-Path (Join-Path $ThisDir "..")).Path
$RepoParent = (Resolve-Path (Join-Path $RepoRoot "..")).Path

if (-not $ShortcutPath) {
    $ShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "THA4 Load Preview.lnk"
}

if (-not $ActiveDevRoot) {
    $ActiveDevRoot = $RepoRoot
    $legacyDev = Join-Path $RepoParent "tha4fork-develop"
    $currentDev = Join-Path $RepoParent "easyvtuberstudio-develop"
    if (Test-Path (Join-Path $currentDev "scripts\launch\run_load_preview_puppeteer.bat")) {
        $ActiveDevRoot = $currentDev
    } elseif (Test-Path (Join-Path $legacyDev "scripts\launch\run_load_preview_puppeteer.bat")) {
        $ActiveDevRoot = $legacyDev
    }
}

if ($PublishFork) { $Fork = $true }

if ($Fork) {
    $root = $RepoRoot
    $description = "EasyVtuberStudio (fork)"
} else {
    $root = $ActiveDevRoot
    $description = "EasyVtuberStudio (active dev)"
}

$vbsPath = Join-Path $root "scripts\launch\start_easyvtuberstudio.vbs"
$batPath = Join-Path $root "scripts\launch\run_load_preview_puppeteer.bat"
$workDir = $root
$iconPath = Join-Path $root "assets\branding\app-icon-source.ico"

if (-not (Test-Path $vbsPath) -and -not (Test-Path $batPath)) {
    throw "Cannot find launcher: $vbsPath or $batPath. Use -Fork or set -ActiveDevRoot."
}
if (-not (Test-Path $workDir)) {
    throw "Cannot find working directory: $workDir. Use -Fork or set -ActiveDevRoot."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
if (Test-Path $vbsPath) {
    $shortcut.TargetPath = (Join-Path $env:SystemRoot "System32\wscript.exe")
    $shortcut.Arguments = "`"$vbsPath`""
    $shortcut.WorkingDirectory = $workDir
} else {
    $shortcut.TargetPath = $batPath
    $shortcut.WorkingDirectory = $workDir
    $shortcut.Arguments = ""
}
$shortcut.Description = $description
if (Test-Path $iconPath) {
    $shortcut.IconLocation = "$iconPath,0"
}
$shortcut.Save()

Write-Host "Shortcut updated:"
Write-Host "  Path:   $ShortcutPath"
Write-Host "  Target: $($shortcut.TargetPath)"
Write-Host "  WorkDir:$($shortcut.WorkingDirectory)"
