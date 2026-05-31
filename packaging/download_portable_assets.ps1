param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string[]]$OnlyAssetIds = @()
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$manifestPath = Join-Path $PortableRoot "packaging\assets_manifest.json"
if (-not (Test-Path $manifestPath)) {
    $manifestPath = Join-Path $PortableRoot "assets_manifest.json"
}
if (-not (Test-Path $manifestPath)) {
    throw "Missing assets_manifest.json under $PortableRoot\packaging"
}

$manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
$fetchUpstream = Join-Path $PSScriptRoot "fetch_upstream_assets.ps1"

function Get-AssetUrl($asset, $manifest) {
    if (-not [string]::IsNullOrWhiteSpace($asset.url)) {
        return $asset.url
    }
    if (-not [string]::IsNullOrWhiteSpace($manifest.release_base_url)) {
        $base = [string]$manifest.release_base_url
        if (-not $base.EndsWith("/")) { $base += "/" }
        return $base + $asset.filename
    }
    return ""
}

function Invoke-UpstreamAsset([string]$PackageId) {
    if (-not (Test-Path $fetchUpstream)) {
        throw "Missing fetch_upstream_assets.ps1"
    }
    & $fetchUpstream -PortableRoot $PortableRoot -PackageIds @($PackageId)
    if ($LASTEXITCODE -ne 0) {
        throw "Upstream fetch failed for $PackageId (exit=$LASTEXITCODE)"
    }
}

$assets = @($manifest.assets)
if ($OnlyAssetIds.Count -gt 0) {
    $filter = @($OnlyAssetIds)
    $assets = @($assets | Where-Object { $filter -contains $_.id })
    if ($assets.Count -eq 0) {
        throw "No manifest assets matched: $($filter -join ', ')"
    }
}

$releaseAssets = @()
$upstreamAssets = @()
foreach ($asset in $assets) {
    $source = [string]$asset.source
    if ($source -eq "upstream" -or -not [string]::IsNullOrWhiteSpace([string]$asset.upstream_package)) {
        $upstreamAssets += $asset
    } else {
        $releaseAssets += $asset
    }
}

foreach ($asset in $upstreamAssets) {
    $packageId = [string]$asset.upstream_package
    if ([string]::IsNullOrWhiteSpace($packageId)) {
        $packageId = [string]$asset.id
    }
    Write-Host ""
    Write-Host "Fetching upstream package: $packageId"
    Invoke-UpstreamAsset $packageId
}

if ($releaseAssets.Count -eq 0) {
    if ($upstreamAssets.Count -gt 0) {
        Write-Host ""
        Write-Host "Upstream download complete."
        Write-Host ""
        exit 0
    }
    throw "No assets selected."
}

$missing = @()
foreach ($asset in $releaseAssets) {
    $url = Get-AssetUrl $asset $manifest
    if ($asset.required -and [string]::IsNullOrWhiteSpace($url)) {
        $missing += $asset.id
    }
}
if ($missing.Count -gt 0) {
    Write-Host ""
    Write-Host "Portable release assets are not published yet for this release."
    Write-Host "Missing download URLs for: $($missing -join ', ')"
    Write-Host ""
    Write-Host "Maintainer: upload Release 7z files, then fill assets_manifest.json URLs + sha256."
    Write-Host ""
    exit 2
}

$downloadDir = Join-Path $PortableRoot "workspace\asset_downloads"
New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
$downloadedAny = $false

foreach ($asset in $releaseAssets) {
    $url = Get-AssetUrl $asset $manifest
    if ([string]::IsNullOrWhiteSpace($url)) {
        Write-Host "Skip optional release asset (no URL): $($asset.id)"
        continue
    }
    $targetFile = Join-Path $downloadDir $asset.filename
    Write-Host "Downloading $($asset.filename) ..."
    Invoke-WebRequest -Uri $url -OutFile $targetFile -UseBasicParsing

    if (-not [string]::IsNullOrWhiteSpace($asset.sha256)) {
        $hash = (Get-FileHash -Path $targetFile -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($hash -ne $asset.sha256.ToLowerInvariant()) {
            throw "SHA256 mismatch for $($asset.filename)"
        }
    }

    $extractRoot = Join-Path $PortableRoot $asset.extract_to
    New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
    Write-Host "Extracting to $extractRoot ..."
    $sevenZip = @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($sevenZip) {
        & $sevenZip x $targetFile "-o$extractRoot" -y | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "7-Zip failed for $($asset.filename)"
        }
    } else {
        throw "7-Zip not found. Install 7-Zip to extract $($asset.filename)."
    }
    $downloadedAny = $true
}

if (-not $downloadedAny -and $upstreamAssets.Count -eq 0) {
    Write-Host ""
    Write-Host "No addon assets were downloaded (Release URLs not configured yet)."
    Write-Host "Fill packaging\assets_manifest.json release_base_url or per-asset url."
    Write-Host ""
    exit 2
}

Write-Host ""
Write-Host "Download complete."
Write-Host ""
