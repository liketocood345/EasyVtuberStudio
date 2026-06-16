# Import NN ONNX subset (rife / waifu2x / Real-ESRGAN) into data/ezvtb_nn/.
# Usage:
#   powershell -ExecutionPolicy Bypass -File scripts\maint\import_ezvtb_nn_weights.ps1 -PortableRoot .
#   powershell -ExecutionPolicy Bypass -File scripts\maint\import_ezvtb_nn_weights.ps1 -PortableRoot . -ZipPath D:\downloads\ezvtuber_data.zip

param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string]$ZipPath = "",
    [string]$SourceRoot = "",
    [switch]$SkipDownload
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "repo_paths.ps1")
$PortableRoot = (Resolve-Path $PortableRoot).Path

$nnSubdirs = @("rife", "waifu2x", "Real-ESRGAN")
$destRoot = Join-Path $PortableRoot "data\ezvtb_nn"
New-Item -ItemType Directory -Force -Path $destRoot | Out-Null

function Copy-NnSubtree {
    param([string]$SourceRoot)
    foreach ($sub in $nnSubdirs) {
        $src = Join-Path $SourceRoot $sub
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $destRoot $sub
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Get-ChildItem -Path $src -Filter "*.onnx" -File -ErrorAction SilentlyContinue |
            Copy-Item -Force -Destination $dst
    }
}

function Test-NnBundleReady {
    $required = @(
        "rife\rife_x2_fp32.onnx",
        "waifu2x\noise0_scale2x_fp32.onnx",
        "Real-ESRGAN\exported_256_fp32.onnx"
    )
    foreach ($rel in $required) {
        if (-not (Test-Path (Join-Path $destRoot $rel))) { return $false }
    }
    return $true
}

if (Test-NnBundleReady) {
    Write-Host "[OK] data/ezvtb_nn already has required fp32 ONNX; skipping import."
    exit 0
}

if ($SourceRoot) {
    $SourceRoot = (Resolve-Path $SourceRoot).Path
    if (-not (Test-Path (Join-Path $SourceRoot "rife"))) {
        throw "SourceRoot missing rife/: $SourceRoot"
    }
    Copy-NnSubtree -SourceRoot $SourceRoot
    if (-not (Test-NnBundleReady)) {
        throw "Copy from SourceRoot finished but required fp32 ONNX still missing."
    }
    Write-Host "[OK] Copied NN ONNX from $SourceRoot -> data/ezvtb_nn/"
    Get-ChildItem -Path $destRoot -Recurse -Filter "*.onnx" | ForEach-Object {
        Write-Host "  $($_.FullName.Substring($PortableRoot.Length).TrimStart('\'))  ($([math]::Round($_.Length / 1MB, 1)) MB)"
    }
    exit 0
}

$staging = Join-Path $PortableRoot "workspace\_ezvtb_import"
New-Item -ItemType Directory -Force -Path $staging | Out-Null

if (-not $ZipPath) {
    $ZipPath = Join-Path $staging "ezvtuber_data.zip"
}

if (-not (Test-Path -LiteralPath $ZipPath)) {
    if ($SkipDownload) {
        throw "Zip not found: $ZipPath (pass -ZipPath or remove -SkipDownload)"
    }
    $python = $null
    foreach ($candidate in @(
            (Join-Path $PortableRoot "addons\face_puppeteer\venv\Scripts\python.exe"),
            (Join-Path $PortableRoot "workspace\student_venv\Scripts\python.exe"),
            "python")) {
        if ($candidate -eq "python" -or (Test-Path -LiteralPath $candidate)) {
            $python = $candidate
            break
        }
    }
    if (-not $python) { throw "Python not found for gdown download." }
    Write-Host "Downloading ezvtuber-rt data pack (Google Drive)..."
    & $python -m pip install -q gdown
    & $python -c "import gdown; gdown.download(id='1pWKIpjWeqfpa3Rub185FVvxDr5H09pOi', output=r'$ZipPath', fuzzy=True)"
    if (-not (Test-Path -LiteralPath $ZipPath)) {
        throw "Download failed: $ZipPath"
    }
}

$extractRoot = Join-Path $staging "extract"
if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractRoot -Force

$dataRoot = $null
foreach ($candidate in @(
        (Join-Path $extractRoot "data"),
        $extractRoot)) {
    if (Test-Path (Join-Path $candidate "rife")) {
        $dataRoot = $candidate
        break
    }
}
if (-not $dataRoot) {
    throw "Could not find rife/ in archive. Check zip layout."
}

Copy-NnSubtree -SourceRoot $dataRoot

if (-not (Test-NnBundleReady)) {
    throw "Import finished but required fp32 ONNX still missing under data/ezvtb_nn/"
}

Write-Host "[OK] Imported NN ONNX into data/ezvtb_nn/"
Get-ChildItem -Path $destRoot -Recurse -Filter "*.onnx" | ForEach-Object {
    Write-Host "  $($_.FullName.Substring($PortableRoot.Length).TrimStart('\'))  ($([math]::Round($_.Length / 1MB, 1)) MB)"
}
