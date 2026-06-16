param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
. (Join-Path $PSScriptRoot "deploy_common.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
Initialize-DeploySession $PortableRoot

Write-Host ""
Write-Host "==> output_enhancement: NN SR/RIFE runtime + data layout"

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$addonRecord = Get-AddonRecord -Manifest $manifest -AddonId "output_enhancement"

function Test-EzvtbNnWeightsReady {
    param([string]$Root)
    $required = @(
        "data\ezvtb_nn\rife\rife_x2_fp32.onnx",
        "data\ezvtb_nn\waifu2x\noise0_scale2x_fp32.onnx",
        "data\ezvtb_nn\Real-ESRGAN\exported_256_fp32.onnx"
    )
    foreach ($rel in $required) {
        if (-not (Test-Path (Join-Path $Root $rel))) { return $false }
    }
    return $true
}

if (-not (Test-EzvtbNnWeightsReady $PortableRoot)) {
    $fetchScript = Join-Path $PSScriptRoot "fetch_upstream_assets.ps1"
    if (Test-Path $fetchScript) {
        Write-Host "Fetching data\ezvtb_nn from HF Bucket (primary) ..."
        & $fetchScript -PortableRoot $PortableRoot -PackageIds @("ezvtb_nn_weights")
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "HF Bucket fetch for ezvtb_nn failed; trying Google Drive import fallback."
        }
    }
}

if (-not (Test-EzvtbNnWeightsReady $PortableRoot)) {
    $importScript = Join-Path $PortableRoot "scripts\maint\import_ezvtb_nn_weights.ps1"
    if (Test-Path $importScript) {
        Write-Host "Fallback: import_ezvtb_nn_weights.ps1 ..."
        & $importScript -PortableRoot $PortableRoot
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "import_ezvtb_nn_weights.ps1 failed (exit $LASTEXITCODE)."
        }
    }
}

$addonRoot = Join-Path $PortableRoot "addons\output_enhancement"
$dataRoot = Join-Path $addonRoot "ezvtb_data"
New-Item -ItemType Directory -Force -Path $addonRoot | Out-Null
foreach ($sub in @("rife", "waifu2x", "Real-ESRGAN")) {
    New-Item -ItemType Directory -Force -Path (Join-Path $dataRoot $sub) | Out-Null
}

if (Sync-BundledEzvtbNnWeights -PortableRoot $PortableRoot -AddonDataRoot $dataRoot) {
    Write-Host "[OK] Copied bundled NN ONNX from data\ezvtb_nn -> addons\output_enhancement\ezvtb_data"
} elseif (-not (Test-EzvtbNnWeightsReady $PortableRoot)) {
    Write-Host "NOTE: data\ezvtb_nn still missing after Bucket + import fallback; NN tier [5] layout only."
}

$layoutReady = Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $addonRecord

$pythonExe = $null
$studentVenv = Join-Path $PortableRoot "workspace\student_venv\Scripts\python.exe"
$faceVenv = Join-Path $PortableRoot "addons\face_puppeteer\venv\Scripts\python.exe"
if (Test-Path $studentVenv) { $pythonExe = $studentVenv }
elseif (Test-Path $faceVenv) { $pythonExe = $faceVenv }

$pipReady = $false
if ($pythonExe) {
    $pipReady = Test-OutputEnhancementPipImports -PythonExe $pythonExe
}

if ($layoutReady -and $pipReady) {
    Write-Host "[OK] output_enhancement already installed; skipping pip (re-run is safe)."
    Set-Content -Path (Join-Path $addonRoot ".installed") -Value (Get-Date -Format o) -Encoding UTF8
    Write-Host "[OK] output_enhancement layout at addons\output_enhancement"
    exit 0
}

if ($pythonExe) {
    try {
        Invoke-PipUpgradePackages -PythonExe $pythonExe -Packages @(
            "onnxruntime-gpu>=1.16", "pyanime4k>=2.5") -Label "Installing onnxruntime-gpu + pyanime4k"
    } catch {
        Write-Host "onnxruntime-gpu failed; trying onnxruntime (CPU)..."
        Invoke-PipUpgradePackages -PythonExe $pythonExe -Packages @(
            "onnxruntime>=1.16", "pyanime4k>=2.5") -Label "Installing onnxruntime (CPU) + pyanime4k"
    }
    Write-Host "Optional: TensorRT wheel (NVIDIA GPU only)..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $trtOut = & $pythonExe -m pip install --upgrade "tensorrt" 2>&1
    foreach ($line in @($trtOut)) {
        if ($line -is [System.Management.Automation.ErrorRecord]) { Write-Host $line.ToString() }
        else { Write-Host $line }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "TensorRT not installed; SR/RIFE will use ONNX Runtime only."
    }
    $ErrorActionPreference = $prevEap
    $pipReady = Test-OutputEnhancementPipImports -PythonExe $pythonExe
    if (-not $pipReady) {
        Write-Host "WARNING: pip finished but onnxruntime/pyanime4k import check failed."
        Write-Host "         Re-run DEPLOY [5] after [1] basic_run or [2] face_puppeteer succeeds."
    }
} else {
    Write-Host "WARNING: No student/face venv yet. Install [1] basic_run or [2] face_puppeteer first, then re-run [5]."
    Write-Host "         Layout folders were created; pip packages will install on the next [5] run."
}

$readme = @"
# output_enhancement (DEPLOY tier [5])

ONNX weights for NN super-resolution and RIFE frame interpolation.

Expected layout under ``ezvtb_data/``:

- ``rife/rife_x2_fp32.onnx``, ``rife_x3_fp32.onnx``, ``rife_x4_fp32.onnx`` (+ optional fp16)
- ``waifu2x/noise0_scale2x_fp32.onnx`` (+ fp16)
- ``Real-ESRGAN/exported_256_fp32.onnx`` (+ fp16)

DEPLOY downloads ONNX from HF Bucket ``data/ezvtb_nn/`` (primary) or ``import_ezvtb_nn_weights.ps1`` (fallback), then copies into ``ezvtb_data/``.
anime4k uses OpenCL via pyanime4k (no ONNX file required).

TensorRT engines cache under ``workspace/ezvtb_engines/`` (generated locally).
"@
Set-Content -Path (Join-Path $addonRoot "README.md") -Value $readme -Encoding UTF8
Set-Content -Path (Join-Path $addonRoot ".installed") -Value (Get-Date -Format o) -Encoding UTF8

Write-Host "[OK] output_enhancement layout at addons\output_enhancement"
