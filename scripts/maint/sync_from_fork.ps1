# Overwrite tha4fork-develop code from tha4fork release tree, preserving dev-only paths and full install payloads.
# Usage (from develop repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\maint\sync_from_fork.ps1

param(
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
$DevRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if (-not $ForkRoot) {
    $ForkRoot = (Resolve-Path (Join-Path $DevRoot "..\tha4fork")).Path
}
if (-not (Test-Path (Join-Path $ForkRoot "docs\DEPLOY.md"))) {
    throw "Fork root not found or invalid: $ForkRoot"
}

$PreserveRelative = @(
    "plans",
    ".codegraph"
)

$ExcludeFromMirror = @(
    ".git",
    "plans",
    ".codegraph",
    "runtime",
    "workspace",
    "addons\face_puppeteer",
    "addons\tha3_models",
    "addons\tha4_training"
)

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$backup = Join-Path $DevRoot "_sync_preserve_$stamp"
New-Item -ItemType Directory -Force -Path $backup | Out-Null

try {
    foreach ($rel in $PreserveRelative) {
        $src = Join-Path $DevRoot $rel
        if (Test-Path $src) {
            Copy-Item -Recurse -Force $src (Join-Path $backup $rel)
            Write-Host "Backed up $rel"
        }
    }

    $excludeDirs = @((Split-Path $backup -Leaf)) + $ExcludeFromMirror
    $roboArgs = @($ForkRoot, $DevRoot, "/MIR", "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP")
    foreach ($d in $excludeDirs) {
        $roboArgs += "/XD"
        $roboArgs += $d
    }
    robocopy @roboArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }
    Write-Host "Mirrored fork -> develop (preserved full install under addons/, runtime/, workspace/)"

    foreach ($rel in $PreserveRelative) {
        $bak = Join-Path $backup $rel
        $dst = Join-Path $DevRoot $rel
        if (Test-Path $bak) {
            if (Test-Path $dst) { Remove-Item -Recurse -Force $dst }
            Copy-Item -Recurse -Force $bak $dst
            Write-Host "Restored $rel"
        }
    }

    $reconcile = Join-Path $DevRoot "packaging\reconcile_portable_layout.ps1"
    if (Test-Path $reconcile) {
        & $reconcile -PortableRoot $DevRoot | Out-Null
        Write-Host "Reconciled develop layout after sync"
    }
}
finally {
    if (Test-Path $backup) {
        Remove-Item -Recurse -Force $backup
    }
}

Write-Host "Done. Fork: $ForkRoot"
Write-Host "Develop protected: addons payloads, runtime/, workspace/, $($PreserveRelative -join ', ')"
