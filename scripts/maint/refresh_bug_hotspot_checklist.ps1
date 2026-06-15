# Regenerate bug hotspot ranking from e:\record\labeled_prompt.md
# Writes: record index + develop/main docs\BUG_HOTSPOT_CHECKLIST.md
# Called by: git post-push hook, sync_develop_to_fork.ps1

param(
    [switch]$Quiet
)

$ErrorActionPreference = "Continue"
$BuildScript = "e:\record\_build_bug_feedback_index.py"

if (-not (Test-Path $BuildScript)) {
    if (-not $Quiet) {
        Write-Warning "Bug hotspot build script not found: $BuildScript"
    }
    exit 0
}

$pythonCmd = $null
$candidates = @(
    $env:EVS_PYTHON,
    "C:\Users\WXH\AppData\Local\Programs\Python\Python310\python.exe",
    "python",
    "python3",
    "py"
)
foreach ($c in $candidates) {
    if (-not $c) { continue }
    if ($c -match '\.exe$') {
        if (Test-Path $c) { $pythonCmd = $c; break }
        continue
    }
    $found = Get-Command $c -ErrorAction SilentlyContinue
    if ($found) { $pythonCmd = $found.Source; break }
}

if (-not $pythonCmd) {
    if (-not $Quiet) {
        Write-Warning "Python not found; skip bug hotspot refresh."
    }
    exit 0
}

& $pythonCmd $BuildScript
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    if (-not $Quiet) {
        Write-Warning "Bug hotspot refresh failed (exit $exitCode)."
    }
    exit 0
}

if (-not $Quiet) {
    Write-Host "Bug hotspot checklist refreshed (develop + main + e:\record)."
}
exit 0
