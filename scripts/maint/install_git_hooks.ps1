# Point easyvtuberstudio-main git hooks at scripts/maint/git-hooks (version-controlled).
# Run once after clone, or after pull that adds git-hooks/.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\install_git_hooks.ps1

param(
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "repo_paths.ps1")
$roots = Resolve-DevelopForkRoots -ForkRoot $ForkRoot
$ForkRoot = $roots.ForkRoot

if (-not (Test-Path (Join-Path $ForkRoot ".git"))) {
    throw "Git repo not found: $ForkRoot"
}

$hooksRel = "scripts/maint/git-hooks"
$hooksDir = Join-Path $ForkRoot ($hooksRel -replace '/', '\')
if (-not (Test-Path (Join-Path $hooksDir "post-push"))) {
    throw "Missing $hooksDir\post-push — sync develop -> fork first."
}

$gitExe = $null
foreach ($c in @($env:EVS_GIT, "git")) {
    if (-not $c) { continue }
    if ($c -match '\.exe$') {
        if (Test-Path $c) { $gitExe = $c; break }
        continue
    }
    $found = Get-Command $c -ErrorAction SilentlyContinue
    if ($found) { $gitExe = $found.Source; break }
}
if (-not $gitExe) {
    $fallbacks = @(
        "C:\Program Files\Git\cmd\git.exe",
        "C:\Program Files (x86)\Git\cmd\git.exe"
    )
    foreach ($p in $fallbacks) {
        if (Test-Path $p) { $gitExe = $p; break }
    }
}
if (-not $gitExe) {
    throw "git not found. Install Git for Windows or set EVS_GIT."
}

Push-Location $ForkRoot
& $gitExe config core.hooksPath $hooksRel
Write-Host "core.hooksPath = $hooksRel"
Write-Host "  Repo: $ForkRoot"
Write-Host "  post-push -> refresh_bug_hotspot_checklist.ps1"
Pop-Location
