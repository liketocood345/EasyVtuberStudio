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
    $ActiveDevRoot = Join-Path $RepoParent "THA4_bundle_bai_custom"
}

if ($PublishFork) { $Fork = $true }

if ($Fork) {
    $batPath = Join-Path $RepoRoot "run_load_preview_puppeteer.bat"
    $workDir = $RepoRoot
    $description = "THA4 Load Preview (fork)"
} else {
    $batPath = Join-Path $ActiveDevRoot "experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat"
    $workDir = Join-Path $ActiveDevRoot "experiments\puppeteer_load_preview"
    $description = "THA4 Load Preview (active dev)"
}

if (-not (Test-Path $batPath)) {
    throw "Cannot find launcher bat: $batPath. Use -Fork or set -ActiveDevRoot."
}
if (-not (Test-Path $workDir)) {
    throw "Cannot find working directory: $workDir. Use -Fork or set -ActiveDevRoot."
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($ShortcutPath)
$shortcut.TargetPath = $batPath
$shortcut.WorkingDirectory = $workDir
$shortcut.Arguments = ""
$shortcut.Description = $description
$shortcut.Save()

Write-Host "Shortcut updated:"
Write-Host "  Path:   $ShortcutPath"
Write-Host "  Target: $($shortcut.TargetPath)"
Write-Host "  WorkDir:$($shortcut.WorkingDirectory)"
