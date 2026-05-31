param(
    [string]$ForkRoot = "",
    [string]$OutputZip = "",
    [string]$StageDir = "",
    [string]$RuntimeSource = "",
    [switch]$IncludeRuntime
)

$ErrorActionPreference = "Stop"

if (-not $ForkRoot) {
    $ForkRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
} else {
    $ForkRoot = (Resolve-Path $ForkRoot).Path
}

if (-not $PSBoundParameters.ContainsKey("IncludeRuntime")) {
    $IncludeRuntime = $false
}

if (-not $RuntimeSource) {
    $developRoot = Join-Path (Split-Path $ForkRoot -Parent) "tha4fork-develop"
    $venvCandidates = @(
        (Join-Path $developRoot "addons\face_puppeteer\venv"),
        (Join-Path $developRoot "runtime\venv"),
        (Join-Path $ForkRoot "addons\face_puppeteer\venv"),
        (Join-Path $ForkRoot "runtime\venv")
    )
    foreach ($candidate in $venvCandidates) {
        if (Test-Path (Join-Path $candidate "Scripts\python.exe")) {
            $RuntimeSource = $candidate
            break
        }
    }
}

function Get-RuntimeVenvSourcePath {
    param([string]$Source)
    if (-not $Source) { return $null }
    if (Test-Path (Join-Path $Source "Scripts\python.exe")) {
        return $Source
    }
    $nested = Join-Path $Source "venv"
    if (Test-Path (Join-Path $nested "Scripts\python.exe")) {
        return $nested
    }
    return $null
}

$stagingRoot = if ($StageDir) {
    (Resolve-Path $StageDir).Path
} else {
    Join-Path (Split-Path $ForkRoot -Parent) "deploy-zip-staging"
}

$stageRoot = Join-Path $stagingRoot "EasyVtuberStudio-manual"
if (-not $OutputZip) {
    $OutputZip = Join-Path $stagingRoot "EasyVtuberStudio-github-sim.zip"
}

$copyDirs = @(
    "addons", "assets", "bin", "data", "deps", "distiller-ui-doc", "docs",
    "face-puppeteer-ui-enhancements-ai-code", "packaging", "plans", "poetry", "scripts", "src", "tools"
)
$copyFiles = @(".gitignore", ".python-version", "README.md", "EasyVtuberStudio.exe", "DEPLOY.bat", "RESET_ADDON.bat")

function Remove-TreeIfExists([string]$Path) {
    if (Test-Path $Path) {
        Remove-Item $Path -Recurse -Force
    }
}

function Remove-FilesByPattern([string]$Root, [string[]]$Includes) {
    if (-not (Test-Path $Root)) { return }
    Get-ChildItem $Root -Recurse -Include $Includes -File -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Find-SevenZip {
    @(
        "${env:ProgramFiles}\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
}

Write-Host "Building portable ZIP from: $ForkRoot"
Write-Host "IncludeRuntime: $IncludeRuntime"
if ($IncludeRuntime) {
    Write-Host "RuntimeSource: $RuntimeSource"
}

Remove-TreeIfExists $stageRoot
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

foreach ($dirName in $copyDirs) {
    $src = Join-Path $ForkRoot $dirName
    if (-not (Test-Path $src)) { continue }
    $dst = Join-Path $stageRoot $dirName
    robocopy $src $dst /E /NFL /NDL /NJH /NJS /NC /NS /NP `
        /XD __pycache__ .codegraph venv runtime .git workspace upstream_downloads basic_layers |
        Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed for $dirName (exit=$LASTEXITCODE)"
    }
}

foreach ($fileName in $copyFiles) {
    $src = Join-Path $ForkRoot $fileName
    if (Test-Path $src) {
        Copy-Item -Force $src (Join-Path $stageRoot $fileName)
    }
}

New-Item -ItemType Directory -Force -Path (Join-Path $stageRoot "workspace") | Out-Null
New-Item -ItemType File -Force -Path (Join-Path $stageRoot "workspace\.gitkeep") | Out-Null

$demoData = Join-Path $stageRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data"

# Never ship upstream-only weights in the portable bundle.
Remove-FilesByPattern (Join-Path $stageRoot "deps\tha3\models") @("*.pt", "*.onnx")
Remove-FilesByPattern (Join-Path $demoData "tha4") @("*.pt")
Remove-FilesByPattern $demoData @("pose_dataset.pt")

foreach ($mirror in @("character_models", "models", "thirdparty", "images", "distill_examples")) {
    Remove-TreeIfExists (Join-Path $demoData $mirror)
}

foreach ($addonPack in @("face_puppeteer", "tha3_models", "tha4_training")) {
    Remove-TreeIfExists (Join-Path $stageRoot "addons\$addonPack")
}
New-Item -ItemType Directory -Force -Path (Join-Path $stageRoot "addons") | Out-Null
$addonsReadme = Join-Path $ForkRoot "addons\README.md"
if (Test-Path $addonsReadme) {
    Copy-Item -Force $addonsReadme (Join-Path $stageRoot "addons\README.md")
}

$tha4Dir = Join-Path $demoData "tha4"
New-Item -ItemType Directory -Force -Path $tha4Dir | Out-Null
$placeholder = Join-Path $tha4Dir "placeholder.txt"
if (-not (Test-Path $placeholder)) {
    Set-Content -Path $placeholder -Value "THA4 teacher weights are downloaded by DEPLOY.bat (optional) or THA4_DownloadTrainingAssets.bat." -Encoding UTF8
}

$mediapipeTask = Join-Path $stageRoot "data\thirdparty\mediapipe\face_landmarker_v2_with_blendshapes.task"
if ($IncludeRuntime) {
    if (-not (Test-Path $mediapipeTask)) {
        Write-Host "MediaPipe task missing; fetching ..."
        & (Join-Path $PSScriptRoot "fetch_upstream_assets.ps1") -PortableRoot $stageRoot -PackageIds @("mediapipe_task")
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to fetch MediaPipe task for portable bundle."
        }
    }
} else {
    Remove-TreeIfExists (Join-Path $stageRoot "data\thirdparty\mediapipe")
}

if ($IncludeRuntime) {
    $venvSource = Get-RuntimeVenvSourcePath $RuntimeSource
    if (-not $venvSource) {
        throw "IncludeRuntime requires venv at addons\face_puppeteer\venv or runtime\venv (e.g. tha4fork-develop full install)."
    }
    Write-Host "Copying bundled runtime into addons\face_puppeteer\venv (this may take a few minutes) ..."
    Write-Host "  Source: $venvSource"
    $runtimeDest = Join-Path $stageRoot "addons\face_puppeteer\venv"
    New-Item -ItemType Directory -Force -Path (Split-Path $runtimeDest -Parent) | Out-Null
    robocopy $venvSource $runtimeDest /E /NFL /NDL /NJH /NJS /NC /NS /NP /XD __pycache__ |
        Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "robocopy failed copying runtime (exit=$LASTEXITCODE)"
    }
    if (Test-Path $mediapipeTask) {
        $addonMp = Join-Path $stageRoot "addons\face_puppeteer\mediapipe"
        New-Item -ItemType Directory -Force -Path $addonMp | Out-Null
        Copy-Item -Force $mediapipeTask (Join-Path $addonMp "face_landmarker_v2_with_blendshapes.task")
        Remove-TreeIfExists (Join-Path $stageRoot "data\thirdparty\mediapipe")
    }
}

& (Join-Path $PSScriptRoot "portable_data_layout.ps1") -PortableRoot $stageRoot

Write-Host ""
Write-Host "Running portable ZIP verification ..."
if ($IncludeRuntime) {
    $verifyArgs = @{
        PortableRoot    = $stageRoot
        Strict          = $true
        RequireRuntime  = $true
    }
    & (Join-Path $PSScriptRoot "verify_github_zip.ps1") @verifyArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Portable ZIP verification failed."
    }
    & (Join-Path $PSScriptRoot "verify_tha4_student.ps1") -PortableRoot $stageRoot -Strict
    if ($LASTEXITCODE -ne 0) {
        throw "THA4 student readiness verification failed."
    }
} else {
    & (Join-Path $PSScriptRoot "verify_fresh_extract.ps1") -PortableRoot $stageRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Fresh CORE extract verification failed."
    }
    & (Join-Path $PSScriptRoot "verify_github_zip.ps1") -PortableRoot $stageRoot -Strict
    if ($LASTEXITCODE -ne 0) {
        throw "Portable ZIP verification failed."
    }
}

if (Test-Path $OutputZip) {
    Remove-Item $OutputZip -Force
}

$sevenZip = Find-SevenZip
if ($sevenZip) {
    Write-Host "Compressing with 7-Zip (large bundle, may take several minutes) ..."
    Push-Location $stageRoot
    try {
        & $sevenZip a -tzip $OutputZip "*" -mx=1 | Out-Host
        if ($LASTEXITCODE -ne 0) {
            throw "7-Zip failed (exit=$LASTEXITCODE)"
        }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "7-Zip not found; using Compress-Archive (slow for large bundles) ..."
    Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $OutputZip -Force
}

$sizeMb = [math]::Round((Get-Item $OutputZip).Length / 1MB, 1)
Write-Host ""
Write-Host "ZIP ready: $OutputZip ($sizeMb MB)"
Write-Host "Stage dir: $stageRoot"
