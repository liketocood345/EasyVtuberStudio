param(
    [string]$PortableRoot = "",
    [switch]$Quiet,
    [switch]$ForceRebuildRuntime,
    [switch]$MouseStudentOnly
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
if (-not $PortableRoot) {
    $PortableRoot = Resolve-PortableRoot (Join-Path $PSScriptRoot "..")
} else {
    $PortableRoot = Resolve-PortableRoot $PortableRoot
}

function Write-Step([string]$Message) {
    if (-not $Quiet) {
        Write-Host ""
        Write-Host "==> $Message"
    }
}

function Find-SevenZip {
    @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

function Expand-ArchiveFile([string]$ArchivePath, [string]$ExtractRoot) {
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

function Resolve-ManifestPath {
    $primary = Join-Path $PortableRoot "packaging\assets_manifest.json"
    if (Test-Path $primary) { return $primary }
    $legacy = Join-Path $PortableRoot "assets_manifest.json"
    if (Test-Path $legacy) { return $legacy }
    throw "Missing packaging\assets_manifest.json under $PortableRoot"
}

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

function Ensure-PortableDataLayout {
    $layoutScript = Join-Path $PSScriptRoot "portable_data_layout.ps1"
    if (Test-Path $layoutScript) {
        & $layoutScript -PortableRoot $PortableRoot
        return
    }
    Write-Step "Ensuring portable data layout (legacy)"
    $demoData = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data"
    New-Item -ItemType Directory -Force -Path $demoData | Out-Null

    $repoMediapipe = Join-Path $PortableRoot "data\thirdparty\mediapipe"
    $demoMediapipe = Join-Path $demoData "thirdparty\mediapipe"
    if ((Test-Path $repoMediapipe) -and -not (Test-Path $demoMediapipe)) {
        New-Item -ItemType Directory -Force -Path (Split-Path $demoMediapipe) | Out-Null
        cmd /c mklink /J "$demoMediapipe" "$repoMediapipe" | Out-Null
        if (-not (Test-Path $demoMediapipe)) {
            Copy-Item -Recurse -Force $repoMediapipe $demoMediapipe
        }
    }
}

function Get-TargetVenvPath {
    if ($MouseStudentOnly) {
        return Join-Path $PortableRoot "workspace\student_venv"
    }
    return Get-AddonVenvPath
}

function Test-PortableRuntime {
    Test-Path (Join-Path (Get-TargetVenvPath) "Scripts\python.exe")
}

function Get-AddonVenvPath {
    Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerVenvRelative)
}

function Copy-DevVenvToAddon {
    $targets = @(
        (Join-Path $PortableRoot "workspace\student_venv"),
        (Join-Path $PortableRoot "runtime\venv"),
        (Join-Path $PortableRoot "venv")
    )
    foreach ($source in $targets) {
        $python = Join-Path $source "Scripts\python.exe"
        if (-not (Test-Path $python)) { continue }
        Write-Step "Copying dev venv to addons\face_puppeteer\venv (from $source)"
        $addonVenv = Get-AddonVenvPath
        if (Test-Path $addonVenv) {
            Remove-Item $addonVenv -Recurse -Force
        }
        Ensure-Directory (Split-Path $addonVenv -Parent)
        robocopy $source $addonVenv /E /NFL /NDL /NJH /NJS /NC /NS /NP | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw "robocopy failed copying venv to addons\face_puppeteer\venv"
        }
        Repair-CopiedVenv $addonVenv | Out-Null
        return $true
    }
    return $false
}

function Get-SuitablePythonCandidate {
    return Get-SuitablePythonCandidateSpec -PortableRoot $PortableRoot
}

function Ensure-SuitableSystemPython {
    if (Test-PortableRuntime) { return $true }
    if (Get-SuitablePythonCandidate) { return $true }

    Write-Step "Python 3.10/3.11 not found - installing Python 3.10 for EasyVtuberStudio"
    Write-Host "  (winget / python.org installer / portable embed fallback)"

    $installScript = Join-Path $PSScriptRoot "install_python310.ps1"
    if (-not (Test-Path $installScript)) {
        throw "Missing packaging\install_python310.ps1"
    }
    & $installScript -PortableRoot $PortableRoot -MouseStudentOnly:$MouseStudentOnly
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) {
        throw "Python 3.10 install failed (exit=$LASTEXITCODE)"
    }
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = @($userPath, $machinePath) -join ";"
    return (Test-PortableRuntime -or [bool](Get-SuitablePythonCandidate))
}

function Get-VenvPythonExe([string]$PipOrPythonExe) {
    $dir = Split-Path $PipOrPythonExe
    $python = Join-Path $dir "python.exe"
    if (-not (Test-Path $python)) {
        throw "Missing venv python.exe beside $PipOrPythonExe"
    }
    return $python
}

function Repair-CopiedVenv([string]$VenvRoot) {
    $python = Join-Path $VenvRoot "Scripts\python.exe"
    if (-not (Test-Path $python)) { return $false }
    Write-Step "Repairing copied venv launchers ($VenvRoot)"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $python -m venv --upgrade $VenvRoot 2>&1 | Out-Host
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return $ok
}

function Invoke-PipInstall([string]$PipExe, [string]$ReqPath) {
    if (-not (Test-Path -LiteralPath $ReqPath)) {
        throw "Missing requirements file: $ReqPath`nRun DEPLOY.bat from the extracted repo root."
    }
    $pythonExe = Get-VenvPythonExe $PipExe
    Write-Step "pip install -r $(Split-Path $ReqPath -Leaf)"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $pythonExe -m pip install -r $ReqPath
    $pipExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($pipExit -ne 0) {
        throw "pip install failed for $ReqPath (exit=$pipExit)"
    }
}

function Test-RuntimeHasTorch([string]$PythonExe) {
    if (-not (Test-Path $PythonExe)) { return $false }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $PythonExe -c "import torch" 2>$null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return $ok
}

function Install-TorchPackages([string]$PipExe) {
    $pythonExe = Get-VenvPythonExe $PipExe
    $depsDir = Join-Path $PortableRoot "deps\pip"
    $cu = Join-Path $depsDir "requirements-torch-cu117.txt"
    $cpu = Join-Path $depsDir "requirements-torch-cpu.txt"
    Write-Step "pip install PyTorch (required for EasyVtuberStudio; CUDA build ~2 GB)"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $pythonExe -m pip install -r $cu
    if ($LASTEXITCODE -ne 0) {
        Write-Host "CUDA PyTorch failed; trying CPU build (slower, no GPU)."
        & $pythonExe -m pip install -r $cpu
        if ($LASTEXITCODE -ne 0) {
            $ErrorActionPreference = $prevEap
            throw "PyTorch install failed (CUDA and CPU). Check network and re-run DEPLOY.bat."
        }
    }
    $ErrorActionPreference = $prevEap
}

function Install-RuntimePipPackages([string]$PipExe, [switch]$SkipTorchInstall) {
    $pythonExe = Join-Path (Split-Path $PipExe) "python.exe"
    $depsDir = Join-Path $PortableRoot "deps\pip"
    if ($MouseStudentOnly) {
        Invoke-PipInstall $PipExe (Join-Path $depsDir "requirements-mouse-student.txt")
    } else {
        foreach ($name in @("requirements-shell.txt", "requirements-tha4-student.txt", "requirements-tha3-ort.txt")) {
            Invoke-PipInstall $PipExe (Join-Path $depsDir $name)
        }
    }
    if ($SkipTorchInstall -and (Test-RuntimeHasTorch $pythonExe)) {
        Write-Host "PyTorch already in target venv; skipping torch wheel install."
    } else {
        Install-TorchPackages $PipExe
    }
}

function Test-RuntimeImports([string]$PythonExe) {
    if ($MouseStudentOnly) {
        Write-Step "Verifying runtime imports (torch, wx, matplotlib, tha4) for mouse student mode"
        $demoSrc = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src"
        $env:PYTHONPATH = $demoSrc
        $code = "import torch, wx, matplotlib; from tha4.shion.base.image_util import resize_PIL_image; print('runtime OK', torch.__version__)"
    } else {
        Write-Step "Verifying runtime imports (torch, wx, matplotlib, mediapipe)"
        $demoSrc = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src"
        $env:PYTHONPATH = $demoSrc
        $code = "import torch, wx, matplotlib, mediapipe; print('runtime OK', torch.__version__)"
    }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $PythonExe -c $code 2>&1 | Out-Host
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return $ok
}

function Install-RuntimeWithSystemPython {
    if (-not (Ensure-SuitableSystemPython)) {
        return $false
    }

    if (Test-PortableRuntime) {
        $hint = if ($MouseStudentOnly) { "workspace\student_venv" } else { "addons\face_puppeteer\venv" }
        Write-Step "Target venv already prepared ($hint)"
        return $true
    }

    $candidate = Get-SuitablePythonCandidate
    if (-not $candidate) {
        return $false
    }

    Write-Step "Creating target venv with Python $($candidate.Version) (may take 10-20 minutes)"
    $targetVenv = Get-TargetVenvPath
    Ensure-Directory (Split-Path $targetVenv -Parent)
    $createArgs = @($candidate.Args + @("-m", "venv", $targetVenv))
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $candidate.Command @createArgs 2>&1 | Out-Host
    $createExit = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($createExit -ne 0) {
        throw "Failed to create target venv with Python $($candidate.Version) (exit=$createExit)"
    }
    return $true
}

function Download-ManifestAssets([object]$Manifest) {
    $downloadDir = Join-Path $PortableRoot "workspace\asset_downloads"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $downloaded = $false

    foreach ($asset in $Manifest.assets) {
        $source = [string]$asset.source
        if ($source -eq "upstream") {
            continue
        }
        $url = Get-AssetUrl $asset $Manifest
        if ([string]::IsNullOrWhiteSpace($url)) {
            if ($asset.required) {
                Write-Host "Skip required release asset $($asset.id): no URL configured"
            }
            continue
        }

        $targetFile = Join-Path $downloadDir $asset.filename
        Write-Step "Downloading $($asset.filename)"
        try {
            Invoke-WebRequest -Uri $url -OutFile $targetFile -UseBasicParsing
        } catch {
            Write-Host "Release download failed for $($asset.filename): $($_.Exception.Message)"
            continue
        }

        if (-not (Test-Path $targetFile) -or (Get-Item $targetFile).Length -lt 1024) {
            Write-Host "Release download invalid for $($asset.filename); trying fallbacks."
            continue
        }

        if (-not [string]::IsNullOrWhiteSpace($asset.sha256)) {
            $hash = (Get-FileHash -Path $targetFile -Algorithm SHA256).Hash.ToLowerInvariant()
            if ($hash -ne $asset.sha256.ToLowerInvariant()) {
                throw "SHA256 mismatch for $($asset.filename)"
            }
        }

        $extractRoot = Join-Path $PortableRoot $asset.extract_to
        Write-Step "Extracting $($asset.filename) -> $($asset.extract_to)"
        Expand-ArchiveFile $targetFile $extractRoot
        $downloaded = $true
    }
    return $downloaded
}

function Try-DownloadRuntimeFromGitHubRelease([object]$Manifest) {
    $runtimeAsset = @($Manifest.assets | Where-Object { $_.id -in @("face_puppeteer_runtime", "runtime") } | Select-Object -First 1)
    if (-not $runtimeAsset) { return $false }

    $configuredUrl = Get-AssetUrl $runtimeAsset $Manifest
    if (-not [string]::IsNullOrWhiteSpace($configuredUrl)) {
        return $false
    }

    try {
        $repo = "liketocood345/EasyVtuberStudio"
        $headers = @{ "User-Agent" = "EasyVtuberStudio-Deploy" }
        $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repo/releases/latest" -Headers $headers
        $remoteAsset = @($release.assets | Where-Object { $_.name -like "*Portable-Runtime*" } | Select-Object -First 1)
        if (-not $remoteAsset) {
            Write-Host "No Portable-Runtime asset on latest GitHub Release."
            return $false
        }

        $downloadDir = Join-Path $PortableRoot "workspace\asset_downloads"
        New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
        $targetFile = Join-Path $downloadDir $remoteAsset.name
        Write-Step "Downloading runtime from GitHub Release: $($remoteAsset.name)"
        Invoke-WebRequest -Uri $remoteAsset.browser_download_url -OutFile $targetFile -Headers $headers -UseBasicParsing
        $extractRoot = Resolve-PortableRootPath $PortableRoot "addons/face_puppeteer"
        Expand-ArchiveFile $targetFile $extractRoot
        return (Test-PortableRuntime)
    } catch {
        Write-Host "GitHub Release runtime fetch skipped: $($_.Exception.Message)"
        return $false
    }
}

Write-Step "Portable bootstrap for $PortableRoot"
Ensure-DeployLayoutDirectories $PortableRoot
Ensure-PortableDataLayout
New-Item -ItemType Directory -Force -Path (Join-Path $PortableRoot "workspace") | Out-Null

if ($ForceRebuildRuntime) {
    $targetVenv = Get-TargetVenvPath
    if (Test-Path $targetVenv) {
        Write-Step "Removing existing target venv (deploy overwrite)"
        Remove-Item $targetVenv -Recurse -Force
    }
    if (-not $MouseStudentOnly) {
        Remove-PathForLayout (Join-Path $PortableRoot "runtime\venv")
    }
}

if (-not (Test-PortableRuntime)) {
    $manifestPath = Resolve-ManifestPath
    $manifest = Get-Content $manifestPath -Raw | ConvertFrom-Json
    if (-not $MouseStudentOnly) {
        $downloaded = Download-ManifestAssets $manifest
    } else {
        $downloaded = $false
    }

    if (-not (Test-PortableRuntime) -and -not $downloaded) {
        if (-not $MouseStudentOnly) {
            if (-not (Try-DownloadRuntimeFromGitHubRelease $manifest)) {
                if (-not (Copy-DevVenvToAddon)) {
                    if (-not (Install-RuntimeWithSystemPython)) {
                        throw @"
Could not prepare Python runtime in addons\face_puppeteer\venv.
"@
                    }
                }
            }
        } elseif (-not (Install-RuntimeWithSystemPython)) {
            throw @"
Could not prepare Python runtime in workspace\student_venv.

DEPLOY tried: Python 3.10 auto-install, then pip (torch + wx, no MediaPipe).

Please check network, disk space (~8 GB), and run EasyVtuberStudio.exe again.
"@
        }
    }
}

Ensure-PortableDataLayout

$venvRoot = Get-TargetVenvPath
$python = Join-Path $venvRoot "Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Target venv python.exe still missing after bootstrap ($venvRoot)"
}

$pip = Join-Path $venvRoot "Scripts\pip.exe"
if (-not (Test-Path $pip)) {
    throw "Target venv pip.exe still missing after bootstrap"
}

Install-RuntimePipPackages $pip -SkipTorchInstall
if (-not (Test-RuntimeImports $python)) {
    $hint = if ($MouseStudentOnly) { "workspace\student_venv" } else { "addons\face_puppeteer\venv" }
    throw @"
Runtime verification failed (torch / wx$(if (-not $MouseStudentOnly) { ' / mediapipe' })).

Re-run EasyVtuberStudio.exe or DEPLOY.bat to repair $hint.
See workspace\launch.log after trying again.
"@
}

if (-not $MouseStudentOnly) {
    $mediapipeCandidates = @(
        (Join-Path (Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerMediapipeRelative)) "face_landmarker_v2_with_blendshapes.task"),
        (Join-Path $PortableRoot "data\thirdparty\mediapipe\face_landmarker_v2_with_blendshapes.task"),
        (Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\thirdparty\mediapipe\face_landmarker_v2_with_blendshapes.task")
    )
    $hasMediapipe = @($mediapipeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1)
    if (-not $hasMediapipe) {
        throw @"
MediaPipe face landmarker .task file missing.

Run DEPLOY.bat -> [2] face_puppeteer, or:
  powershell -ExecutionPolicy Bypass -File packaging\fetch_upstream_assets.ps1 -PortableRoot "$PortableRoot" -PackageIds mediapipe_task
"@
    }
    & (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot | Out-Null
}

$marker = Join-Path $PortableRoot "workspace\.portable_bootstrap_done"
Set-Content -Path $marker -Value (Get-Date -Format o) -Encoding UTF8

Write-Step "Portable bootstrap complete"
if (-not $Quiet) {
    Write-Host "You can now launch EasyVtuberStudio.exe"
}
exit 0
