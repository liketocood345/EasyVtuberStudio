param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string[]]$PackageIds = @()
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$ProgressPreference = "SilentlyContinue"
Ensure-DeployLayoutDirectories $PortableRoot

$configPath = Join-Path $PSScriptRoot "upstream_assets.json"
if (-not (Test-Path $configPath)) {
    throw "Missing upstream_assets.json beside fetch_upstream_assets.ps1"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json
$packages = @($config.packages)
if ($PackageIds.Count -gt 0) {
    $filter = @($PackageIds)
    $packages = @($packages | Where-Object { $filter -contains $_.id })
    if ($packages.Count -eq 0) {
        throw "No upstream packages matched: $($filter -join ', ')"
    }
}

function Find-SevenZip {
    @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Get-DirectDownloadUrl([string]$Url) {
    if ($Url -match "dropbox\.com") {
        if ($Url -match "[?&]dl=") {
            return ($Url -replace "(?<=dl=)[01]", "1")
        }
        if ($Url -match "\?") { return "$Url&dl=1" }
        return "$Url?dl=1"
    }
    return $Url
}

function Download-RemoteFile([string]$Url, [string]$DestPath) {
    $direct = Get-DirectDownloadUrl $Url
    Write-Host "Downloading $($DestPath | Split-Path -Leaf) ..."
    Write-Host "  from $direct"
    New-Item -ItemType Directory -Force -Path (Split-Path $DestPath) | Out-Null
    try {
        Invoke-WebRequest -Uri $direct -OutFile $DestPath -UseBasicParsing
    } catch {
        throw "Download failed: $direct`n$($_.Exception.Message)"
    }
    if (-not (Test-Path $DestPath) -or (Get-Item $DestPath).Length -lt 1024) {
        throw "Download looks invalid (missing or too small): $DestPath"
    }
}

function Expand-ArchiveTo([string]$ArchivePath, [string]$ExtractRoot) {
    New-Item -ItemType Directory -Force -Path $ExtractRoot | Out-Null
    $sevenZip = Find-SevenZip
    if ($sevenZip) {
        & $sevenZip x $ArchivePath "-o$ExtractRoot" -y | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "7-Zip failed for $ArchivePath"
        }
        return
    }
    if ($ArchivePath -like "*.zip") {
        Expand-Archive -Path $ArchivePath -DestinationPath $ExtractRoot -Force
        return
    }
    throw "7-Zip not found. Install 7-Zip to extract $ArchivePath"
}

function Resolve-PortablePath([string]$RelativePath) {
    return Join-Path $PortableRoot ($RelativePath -replace "/", "\")
}

function Find-DirectoryContaining([string]$Root, [string]$ChildName) {
    $direct = Join-Path $Root $ChildName
    if (Test-Path $direct) { return $Root }
    foreach ($dir in Get-ChildItem $Root -Directory -ErrorAction SilentlyContinue) {
        if (Test-Path (Join-Path $dir.FullName $ChildName)) {
            return $dir.FullName
        }
    }
    return $null
}

function Install-Tha3OfficialPytorch([string]$StagingDir, [string]$DestRelative) {
    $variantDirs = @("separable_float", "separable_half", "standard_float", "standard_half")
    $sourceRoot = Find-DirectoryContaining $StagingDir "separable_half"
    if (-not $sourceRoot) {
        $modelsRoot = Find-DirectoryContaining $StagingDir "models"
        if ($modelsRoot) {
            $nested = Join-Path $modelsRoot "models"
            if (Test-Path $nested) { $modelsRoot = $nested }
            $sourceRoot = Find-DirectoryContaining $modelsRoot "separable_half"
        }
    }
    if (-not $sourceRoot) {
        throw "Could not locate THA3 variant folders (separable_half, ...) in extracted archive."
    }

    $destRoot = Resolve-PortablePath $DestRelative
    New-Item -ItemType Directory -Force -Path $destRoot | Out-Null
    $installed = 0
    foreach ($name in $variantDirs) {
        $src = Join-Path $sourceRoot $name
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $destRoot $name
        if (Test-Path $dst) { Remove-Item $dst -Recurse -Force }
        Copy-Item $src $dst -Recurse -Force
        Write-Host "Installed THA3 variant -> $dst"
        $installed++
    }
    if ($installed -eq 0) {
        throw "No THA3 variant directories were copied from $sourceRoot"
    }

    $license = Get-ChildItem $StagingDir -Recurse -Filter "LICENSE.txt" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($license) {
        Copy-Item $license.FullName (Join-Path $destRoot "LICENSE.txt") -Force
    }
}

function Get-Tha3PytorchWeightNames {
    return @(
        "editor.pt",
        "eyebrow_decomposer.pt",
        "eyebrow_morphing_combiner.pt",
        "face_morpher.pt",
        "two_algo_face_body_rotator.pt"
    )
}

function Get-Tha3PytorchVariantNames {
    return @("separable_float", "separable_half", "standard_float", "standard_half")
}

function Install-Tha3HfPytorch($installSpec) {
    $repoId = [string]$installSpec.repo_id
    if ([string]::IsNullOrWhiteSpace($repoId)) {
        throw "tha3_hf_pytorch requires install.repo_id"
    }
    $revision = [string]$installSpec.revision
    if ([string]::IsNullOrWhiteSpace($revision)) { $revision = "main" }
    $destRelative = [string]$installSpec.dest

    $destRoot = Resolve-PortablePath $destRelative
    New-Item -ItemType Directory -Force -Path $destRoot | Out-Null
    $installed = 0

    foreach ($variant in (Get-Tha3PytorchVariantNames)) {
        $variantDest = Join-Path $destRoot $variant
        New-Item -ItemType Directory -Force -Path $variantDest | Out-Null
        $variantOk = $true
        foreach ($name in (Get-Tha3PytorchWeightNames)) {
            $repoPath = "$variant/$name"
            $url = "https://huggingface.co/$repoId/resolve/$revision/$repoPath"
            $destFile = Join-Path $variantDest $name
            try {
                Download-RemoteFile $url $destFile
            } catch {
                $variantOk = $false
                Write-Warning "Skip $repoPath : $($_.Exception.Message)"
                break
            }
        }
        if ($variantOk) {
            Write-Host "Installed THA3 variant (HF) -> $variantDest"
            $installed++
        } elseif (Test-Path $variantDest) {
            Remove-Item $variantDest -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    if ($installed -eq 0) {
        throw "No THA3 variants installed from Hugging Face repo $repoId"
    }
}

function Install-Tha4TeacherZip([string]$StagingDir, [string]$DestRelative) {
    $required = @(
        "face_morpher.pt",
        "body_morpher.pt",
        "eyebrow_decomposer.pt",
        "eyebrow_morphing_combiner.pt",
        "upscaler.pt"
    )

    $destRoot = Resolve-PortablePath $DestRelative
    New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

    $sourceRoot = $null
    foreach ($name in $required) {
        $found = Get-ChildItem $StagingDir -Recurse -Filter $name -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $sourceRoot = $found.DirectoryName
            break
        }
    }
    if (-not $sourceRoot) {
        throw "Could not locate THA4 teacher .pt files in extracted tha4-models.zip"
    }

    foreach ($name in $required) {
        $src = Join-Path $sourceRoot $name
        if (-not (Test-Path $src)) {
            $found = Get-ChildItem $StagingDir -Recurse -Filter $name -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) { $src = $found.FullName }
        }
        if (-not (Test-Path $src)) {
            Write-Warning "Skip missing THA4 weight: $name"
            continue
        }
        Copy-Item $src (Join-Path $destRoot $name) -Force
        Write-Host "Installed THA4 weight -> $name"
    }
}

function Install-OpenSeeFaceZip([string]$StagingDir, [string]$DestRelative) {
    $destRoot = Resolve-PortablePath $DestRelative
    if (Test-Path $destRoot) {
        Remove-Item $destRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

    $exe = Get-ChildItem $StagingDir -Recurse -Filter "facetracker.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $exe) {
        throw "Could not locate facetracker.exe in OpenSeeFace archive."
    }

    $releaseRoot = $exe.Directory.Parent.FullName
    if ((Split-Path $releaseRoot -Leaf) -ieq "Binary") {
        $releaseRoot = Split-Path $releaseRoot -Parent
    }

    $binarySrc = Join-Path $releaseRoot "Binary"
    if (-not (Test-Path $binarySrc)) {
        $binarySrc = $exe.Directory.FullName
    }
    $binaryDest = Join-Path $destRoot "Binary"
    Copy-Item $binarySrc $binaryDest -Recurse -Force

    $modelsSrc = Join-Path $releaseRoot "models"
    if (Test-Path $modelsSrc) {
        Copy-Item $modelsSrc (Join-Path $destRoot "models") -Recurse -Force
    }

    $licensesSrc = Join-Path $releaseRoot "Licenses"
    if (Test-Path $licensesSrc) {
        Copy-Item $licensesSrc (Join-Path $destRoot "Licenses") -Recurse -Force
    }

    $marker = Join-Path $destRoot ".installed"
    Set-Content -Path $marker -Value ((Get-Date -Format o)) -Encoding UTF8
    Write-Host "Installed OpenSeeFace -> $destRoot"
}

function Install-CopyFile([string]$SourcePath, [string]$DestRelative) {
    $destPath = Resolve-PortablePath $DestRelative
    New-Item -ItemType Directory -Force -Path (Split-Path $destPath) | Out-Null
    Copy-Item $SourcePath $destPath -Force
    Write-Host "Installed file -> $destPath"
}

function Get-HfBucketHelperPath {
    return Join-Path $PSScriptRoot "fetch_hf_bucket.py"
}

function Invoke-HfBucketHelper {
    param([string[]]$HelperArgs)
    $helper = Get-HfBucketHelperPath
    if (-not (Test-Path $helper)) {
        throw "Missing fetch_hf_bucket.py beside fetch_upstream_assets.ps1"
    }
    & python $helper @HelperArgs
    if ($LASTEXITCODE -ne 0) {
        throw "fetch_hf_bucket.py failed (exit $LASTEXITCODE)"
    }
}

function Install-BucketCopyFile($installSpec) {
    $bucketId = [string]$installSpec.bucket_id
    $bucketPath = [string]$installSpec.bucket_path
    $destRelative = [string]$installSpec.dest
    if ([string]::IsNullOrWhiteSpace($bucketId) -or [string]::IsNullOrWhiteSpace($bucketPath)) {
        throw "bucket_copy_file requires install.bucket_id and install.bucket_path"
    }
    $destPath = Resolve-PortablePath $destRelative
    Write-Host "Downloading from HF bucket $bucketId : $bucketPath"
    Invoke-HfBucketHelper @(
        "download-file",
        "--bucket", $bucketId,
        "--remote", $bucketPath,
        "--local", $destPath
    )
    Write-Host "Installed bucket file -> $destPath"
}

function Install-BucketCopyTree($installSpec) {
    $bucketId = [string]$installSpec.bucket_id
    $bucketPath = [string]$installSpec.bucket_path
    $destRelative = [string]$installSpec.dest
    if ([string]::IsNullOrWhiteSpace($bucketId) -or [string]::IsNullOrWhiteSpace($bucketPath)) {
        throw "bucket_copy_tree requires install.bucket_id and install.bucket_path"
    }
    $destRoot = Resolve-PortablePath $destRelative
    if (Test-Path $destRoot) {
        Remove-Item $destRoot -Recurse -Force
    }
    Write-Host "Downloading tree from HF bucket $bucketId : $bucketPath"
    Invoke-HfBucketHelper @(
        "download-tree",
        "--bucket", $bucketId,
        "--remote", $bucketPath,
        "--local", $destRoot
    )
    Write-Host "Installed bucket tree -> $destRoot"
}

function Invoke-InstallHandler($fileSpec, [string]$localPath, [string]$stagingDir) {
    $handler = [string]$fileSpec.install.handler
    $dest = [string]$fileSpec.install.dest
    switch ($handler) {
        "tha3_official_pytorch" {
            Install-Tha3OfficialPytorch $stagingDir $dest
        }
        "tha3_hf_pytorch" {
            Install-Tha3HfPytorch $fileSpec.install
        }
        "tha4_teacher_zip" {
            Install-Tha4TeacherZip $stagingDir $dest
        }
        "openseeface_zip" {
            Install-OpenSeeFaceZip $stagingDir $dest
        }
        "copy_file" {
            Install-CopyFile $localPath $dest
        }
        "bucket_copy_file" {
            Install-BucketCopyFile $fileSpec.install
        }
        "bucket_copy_tree" {
            Install-BucketCopyTree $fileSpec.install
        }
        default {
            throw "Unknown install handler: $handler"
        }
    }
}

function Test-PackageVerified($package) {
    foreach ($rel in @($package.verify)) {
        $path = Resolve-PortablePath ([string]$rel)
        if (-not (Test-Path $path)) {
            return $false
        }
    }
    return $true
}

function Ensure-PortableDemoDataLayout {
    $reconcileScript = Join-Path $PSScriptRoot "reconcile_portable_layout.ps1"
    if (Test-Path $reconcileScript) {
        & $reconcileScript -PortableRoot $PortableRoot | Out-Null
        return
    }
    $layoutScript = Join-Path $PSScriptRoot "portable_data_layout.ps1"
    if (Test-Path $layoutScript) {
        & $layoutScript -PortableRoot $PortableRoot | Out-Null
    }
}

function Install-PackagePrimaryFiles($package, [string]$DownloadRoot) {
    foreach ($fileSpec in @($package.files)) {
        $kind = [string]$fileSpec.kind
        if ($kind -eq "huggingface_bucket") {
            Invoke-InstallHandler $fileSpec $null $null
            continue
        }
        if ($kind -eq "huggingface_repo") {
            Install-PackageFallbackSource $fileSpec $DownloadRoot
            continue
        }

        $filename = [string]$fileSpec.filename
        $localPath = Join-Path $DownloadRoot $filename
        $stagingDir = Join-Path $DownloadRoot ("staging_" + ($filename -replace '[^\w\-]+', '_'))

        if (Test-Path $stagingDir) {
            Remove-Item $stagingDir -Recurse -Force
        }

        Download-RemoteFile ([string]$fileSpec.url) $localPath

        $kind = [string]$fileSpec.kind
        if ($kind -eq "zip") {
            Expand-ArchiveTo $localPath $stagingDir
            Invoke-InstallHandler $fileSpec $localPath $stagingDir
        } elseif ($kind -eq "file") {
            Invoke-InstallHandler $fileSpec $localPath $stagingDir
        } else {
            throw "Unknown file kind: $kind"
        }
    }
}

function Install-PackageFallbackSource($fallbackSpec, [string]$DownloadRoot) {
    $kind = [string]$fallbackSpec.kind
    if ($kind -eq "huggingface_bucket") {
        Invoke-InstallHandler $fallbackSpec $null $null
        return
    }
    if ($kind -eq "huggingface_repo") {
        Invoke-InstallHandler @{ install = $fallbackSpec.install } $null $null
        return
    }
    if ($kind -eq "zip" -or $kind -eq "file") {
        $filename = [string]$fallbackSpec.filename
        if ([string]::IsNullOrWhiteSpace($filename)) {
            throw "Fallback source requires filename for kind $kind"
        }
        $localPath = Join-Path $DownloadRoot $filename
        $stagingDir = Join-Path $DownloadRoot ("staging_" + ($filename -replace '[^\w\-]+', '_'))
        if (Test-Path $stagingDir) {
            Remove-Item $stagingDir -Recurse -Force
        }
        Download-RemoteFile ([string]$fallbackSpec.url) $localPath
        if ($kind -eq "zip") {
            Expand-ArchiveTo $localPath $stagingDir
            Invoke-InstallHandler $fallbackSpec $localPath $stagingDir
        } else {
            Invoke-InstallHandler $fallbackSpec $localPath $stagingDir
        }
        return
    }
    throw "Unknown fallback source kind: $kind"
}

function Write-PackageVerifyStatus($package) {
    Write-Host ""
    Write-Host "Verification failed for package $($package.id). Expected:"
    foreach ($rel in @($package.verify)) {
        $path = Resolve-PortablePath ([string]$rel)
        $mark = if (Test-Path $path) { "OK" } else { "MISSING" }
        Write-Host "  [$mark] $rel"
    }
}

$downloadRoot = Join-Path $PortableRoot "workspace\upstream_downloads"
New-Item -ItemType Directory -Force -Path $downloadRoot | Out-Null

foreach ($package in $packages) {
    Write-Host ""
    Write-Host "=== $($package.label) ($($package.id)) ==="
    if (Test-PackageVerified $package) {
        Write-Host "Already installed; skipping download."
        continue
    }

    $installed = $false
    $lastError = $null

    try {
        Install-PackagePrimaryFiles $package $downloadRoot
        Ensure-PortableDemoDataLayout
        if (Test-PackageVerified $package) {
            $installed = $true
        }
    } catch {
        $lastError = $_
        Write-Warning "Primary source failed: $($_.Exception.Message)"
    }

    if (-not $installed -and $package.fallback_sources) {
        foreach ($fallbackSpec in @($package.fallback_sources)) {
            $label = [string]$fallbackSpec.label
            if ([string]::IsNullOrWhiteSpace($label)) { $label = [string]$fallbackSpec.kind }
            Write-Host ""
            Write-Host "Trying fallback source: $label"
            try {
                Install-PackageFallbackSource $fallbackSpec $downloadRoot
                Ensure-PortableDemoDataLayout
                if (Test-PackageVerified $package) {
                    $installed = $true
                    break
                }
                throw "Verification failed after fallback install"
            } catch {
                $lastError = $_
                Write-Warning "Fallback source failed ($label): $($_.Exception.Message)"
            }
        }
    }

    if (-not $installed) {
        Write-PackageVerifyStatus $package
        if ($lastError) {
            throw "Upstream install incomplete for $($package.id). Last error: $($lastError.Exception.Message)"
        }
        throw "Upstream install incomplete for $($package.id)"
    }

    Write-Host "Package $($package.id) installed successfully."
}

Write-Host ""
Write-Host "Upstream asset install complete."
& (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot | Out-Null
Write-Host ""
exit 0
