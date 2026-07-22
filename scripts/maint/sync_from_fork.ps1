# Overwrite easyvtuberstudio-develop from easyvtuberstudio-main release tree, preserving dev-only paths.
# Root README.md is maintained only on main; not mirrored fork -> develop.
# Usage (from develop repo root):
#   powershell -ExecutionPolicy Bypass -File scripts\maint\sync_from_fork.ps1

param(
    [string]$ForkRoot = ""
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "repo_paths.ps1")
$roots = Resolve-DevelopForkRoots -ForkRoot $ForkRoot
$DevRoot = $roots.DevRoot
$ForkRoot = $roots.ForkRoot
if (-not (Test-Path (Join-Path $ForkRoot "docs\DEPLOY.md"))) {
    throw "Fork root not found or invalid: $ForkRoot"
}

$PreserveRelative = @(
    "plans",
    ".codegraph"
)

# Per-directory mirror (same code roots as sync_develop_to_fork.ps1, reversed).
$CopyDirs = @(
    "addons", "assets", "bin", "data", "deps", "distiller-ui-doc", "docs",
    "face-puppeteer-ui-enhancements-ai-code", "packaging", "poetry", "scripts", "src", "tools"
)
$CopyFiles = @(
    ".gitignore", ".python-version", "EasyVtuberStudio.exe", "DEPLOY.bat", "RESET_ADDON.bat"
)

# /XJ: do not follow junctions (runtime\venv -> face_puppeteer\venv, demo\data\tha4, etc.).
# Without /XJ a local sync can walk multi-GB addon trees for hours.
$RoboExclude = @(
    "__pycache__", ".codegraph", "venv", "runtime", "external_layer_output", "basic_layers",
    "face_puppeteer", "tha3_models", "tha4_training", "output_enhancement"
)
$ExtraDirExclude = @{
    "face-puppeteer-ui-enhancements-ai-code" = @(
        # Junction targets under demo\data; reconcile_portable_layout.ps1 recreates them.
        "talking-head-anime-4-demo\data"
    )
}
$RoboFlags = @(
    "/E", "/MIR", "/XJ", "/R:2", "/W:1", "/MT:8",
    "/NFL", "/NDL", "/NJH", "/NJS", "/NC", "/NS", "/NP"
)

$stamp = Get-Date -Format "yyyyMMddHHmmss"
$backup = Join-Path $DevRoot "_sync_preserve_$stamp"
$sw = [Diagnostics.Stopwatch]::StartNew()

function Remove-BrokenDemoDataTha4Stub {
    param([string]$RepoRoot)
    $stub = Join-Path $RepoRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4"
    if (-not (Test-Path -LiteralPath $stub)) { return }
    $item = Get-Item -LiteralPath $stub -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) { return }
    if ($item.LinkType) { return }
    if ($item.Target -and $item.Target.Count -gt 0) { return }
  # Empty/broken directory left from a partial sync; blocks robocopy on the fork tree.
    Remove-Item -LiteralPath $stub -Recurse -Force -ErrorAction SilentlyContinue
}

Remove-BrokenDemoDataTha4Stub -RepoRoot $ForkRoot

New-Item -ItemType Directory -Force -Path $backup | Out-Null

try {
    foreach ($rel in $PreserveRelative) {
        $src = Join-Path $DevRoot $rel
        if (Test-Path $src) {
            Copy-Item -Recurse -Force $src (Join-Path $backup $rel)
            Write-Host "Backed up $rel"
        }
    }

    foreach ($dir in $CopyDirs) {
        $src = Join-Path $ForkRoot $dir
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $DevRoot $dir
        $dirExclude = @($RoboExclude)
        if ($ExtraDirExclude.ContainsKey($dir)) {
            $dirExclude += $ExtraDirExclude[$dir]
        }
        $args = @($src, $dst) + $RoboFlags + @("/XD") + $dirExclude
        robocopy @args | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed for $dir exit $LASTEXITCODE"
        }
        Write-Host "Mirrored $dir"
    }

    foreach ($file in $CopyFiles) {
        $src = Join-Path $ForkRoot $file
        if (Test-Path $src) {
            Copy-Item -Force $src (Join-Path $DevRoot $file)
        }
    }
    Write-Host "Mirrored root files (README.md stays main-only)"

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

$sw.Stop()
Write-Host ("Done in {0:N1}s. Fork: {1}" -f $sw.Elapsed.TotalSeconds, $ForkRoot)
Write-Host "Develop protected: README.md (main-only), addons payloads, runtime/, workspace/, $($PreserveRelative -join ', ')"
