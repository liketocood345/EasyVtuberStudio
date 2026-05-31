param(
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$OutputDir = "",
    [switch]$IncludeTha3Models,
    [switch]$WriteManifestHashes
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $RepoRoot "packaging\release_assets"
}
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Find-SevenZip {
    @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Compress-Asset(
    [string]$Name,
    [string]$SourcePath,
    [string]$ArchiveName
) {
    if (-not (Test-Path $SourcePath)) {
        Write-Warning "Skip $ArchiveName - missing source: $SourcePath"
        return $null
    }
    $sevenZip = Find-SevenZip
    if (-not $sevenZip) {
        throw "7-Zip not found. Install 7-Zip before building release assets."
    }
    $archivePath = Join-Path $OutputDir $ArchiveName
    if (Test-Path $archivePath) {
        Remove-Item $archivePath -Force
    }
    Write-Host "Creating $ArchiveName from $SourcePath ..."
    & $sevenZip a -t7z -mx=5 $archivePath $SourcePath | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "7-Zip failed for $ArchiveName"
    }
    $hash = (Get-FileHash -Path $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [PSCustomObject]@{
        id = $Name
        filename = $ArchiveName
        path = $archivePath
        sha256 = $hash
        size_mb = [math]::Round((Get-Item $archivePath).Length / 1MB, 1)
    }
}

$demoRoot = Join-Path $RepoRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
$results = @()

$runtimeSource = Join-Path $RepoRoot "addons\face_puppeteer\venv"
if (-not (Test-Path (Join-Path $runtimeSource "Scripts\python.exe"))) {
    $runtimeSource = Join-Path $RepoRoot "runtime\venv"
}
if (-not (Test-Path (Join-Path $runtimeSource "Scripts\python.exe"))) {
    $runtimeSource = Join-Path $RepoRoot "venv"
}
$results += Compress-Asset "face_puppeteer_runtime" $runtimeSource "EasyVtuberStudio-Portable-Runtime.7z"

$tha4Training = Join-Path $RepoRoot "addons\tha4_training"
if (-not (Test-Path $tha4Training)) {
    $tha4Training = Join-Path $demoRoot "data"
}
$results += Compress-Asset "tha4_teacher_training" $tha4Training "EasyVtuberStudio-THA4-Training.7z"

if ($IncludeTha3Models) {
    $tha3Models = Join-Path $RepoRoot "addons\tha3_models"
    if (-not (Test-Path $tha3Models)) {
        $tha3Models = Join-Path $RepoRoot "deps\tha3\models"
    }
    $results += Compress-Asset "tha3_models" $tha3Models "EasyVtuberStudio-THA3-Models.7z"
}

$results = $results | Where-Object { $_ -ne $null }
if ($results.Count -eq 0) {
    throw "No release assets were built. Populate runtime/venv and demo/data first."
}

$summaryPath = Join-Path $OutputDir "release_assets_summary.json"
$results | ConvertTo-Json -Depth 4 | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host ""
Write-Host "Built $($results.Count) archive(s) in $OutputDir"
foreach ($item in $results) {
    Write-Host "  $($item.filename)  $($item.size_mb) MB  sha256=$($item.sha256)"
}

if ($WriteManifestHashes) {
    $manifestPath = Join-Path $RepoRoot "packaging\assets_manifest.json"
    if (-not (Test-Path $manifestPath)) {
        throw "Missing assets_manifest.json"
    }
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    foreach ($asset in $manifest.assets) {
        $built = $results | Where-Object { $_.id -eq $asset.id } | Select-Object -First 1
        if ($built) {
            $asset.sha256 = $built.sha256
        }
    }
    $manifest | ConvertTo-Json -Depth 6 | Set-Content -Path $manifestPath -Encoding UTF8
    Write-Host "Updated SHA256 hashes in assets_manifest.json (URLs still need Release upload)."
}

Write-Host ""
Write-Host "Next: upload *.7z to GitHub Release, fill assets_manifest.json url fields, push."
