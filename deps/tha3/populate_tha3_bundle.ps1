# Copy THA3 / EasyVtuber runtime assets into THIS REPO under deps/tha3 (not junctions).
param(
    [string]$SourceRoot = ""
)

$ErrorActionPreference = "Stop"
$BundleRoot = $PSScriptRoot
$RepoRoot = (Resolve-Path (Join-Path $BundleRoot ".." "..")).Path

if (-not $SourceRoot) {
    $candidates = @(
        "F:\EasyVtuber\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1",
        "E:\EasyVtuber\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "tha3")) {
            $SourceRoot = $c
            break
        }
    }
}

if (-not $SourceRoot -or -not (Test-Path $SourceRoot)) {
    throw "Set -SourceRoot to your EasyVtuber install (folder containing tha3/, ezvtuber-rt/, data/)."
}

Write-Host "Repo:   $RepoRoot"
Write-Host "Source: $SourceRoot"
Write-Host "Target: $BundleRoot"

function Copy-Tree([string]$RelativeName, [string]$SourceSub, [string]$DestSub) {
    $src = Join-Path $SourceRoot $SourceSub
    $dst = Join-Path $BundleRoot $DestSub
    if (-not (Test-Path $src)) {
        Write-Warning "Skip missing source: $src"
        return
    }
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    robocopy $src $dst /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed ($RelativeName) exit=$LASTEXITCODE"
    }
    Write-Host "Copied $RelativeName -> $DestSub"
}

Copy-Tree "tha3_src" "tha3" "tha3_src"
Copy-Tree "ezvtuber_rt" "ezvtuber-rt" "ezvtuber_rt"
Copy-Tree "models" "data\models\tha3" "models\tha3"
Copy-Tree "images" "data\images" "images"

Write-Host "THA3 bundle ready under deps/tha3 (repo-relative)."
