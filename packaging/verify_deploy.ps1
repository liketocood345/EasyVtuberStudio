param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Strict,
    [switch]$IncludeTha4Training,
    [switch]$RequireFacePuppeteer = $true,
    [switch]$RequireTha3Models = $true,
    [switch]$RequireOutputEnhancement = $false
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
. (Join-Path $PSScriptRoot "portable_environment.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Test-RequiredFile([string]$Label, [string]$RelativePath, [ref]$Failed) {
    $path = Resolve-PortableRootPath $PortableRoot $RelativePath
    if (Test-Path $path) {
        Write-Host "[OK] $Label"
        return $true
    }
    Write-Host "[缺失/MISSING] $Label -> $RelativePath"
    $Failed.Value++
    return $false
}

Write-Host ""
Write-Host "部署校验 / Deploy verification: $PortableRoot"
Write-Host ""

$failed = 0
$failedRef = [ref]$failed

Test-RequiredFile "EasyVtuberStudio.exe" "EasyVtuberStudio.exe" $failedRef | Out-Null
Test-RequiredFile "部署脚本 / deploy script" "packaging/deploy_portable.ps1" $failedRef | Out-Null
Test-RequiredFile "主程序入口 / load preview entry" "face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py" $failedRef | Out-Null

Test-RequiredFile "bai 学生模型 yaml / bai student yaml" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character_model.yaml" $failedRef | Out-Null
Test-RequiredFile "bai face_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai body_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/body_morpher.pt" $failedRef | Out-Null
Test-RequiredFile "bai character.png" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character.png" $failedRef | Out-Null

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$faceRecord = Get-AddonRecord -Manifest $manifest -AddonId "face_puppeteer"
$tha3Record = Get-AddonRecord -Manifest $manifest -AddonId "tha3_models"
$tha4Record = Get-AddonRecord -Manifest $manifest -AddonId "tha4_training"

$python = $null
if ($RequireFacePuppeteer) {
    if (Test-FacePuppeteerVenv -PortableRoot $PortableRoot) {
        $venvRoot = Get-FacePuppeteerVenvAbsolute -PortableRoot $PortableRoot
        $python = Join-Path $venvRoot "Scripts\python.exe"
        Write-Host "[OK] Python 运行环境 / Python runtime ($venvRoot)"
    } else {
        Write-Host "[缺失/MISSING] Python 运行环境 / Python runtime -> runtime/venvs/common (bound face_puppeteer)"
        $failed++
    }
    foreach ($rel in @($faceRecord.verify)) {
        Test-RequiredFile "face_puppeteer: $rel" ([string]$rel) $failedRef | Out-Null
    }
} else {
    Write-Host "[跳过/SKIP] face_puppeteer 附加组件 / add-on"
}

if ($RequireTha3Models) {
    foreach($relative in @('addons/tha3_models/venv','workspace/student_venv')) {
        $component=if($relative -eq 'workspace/student_venv') {'basic_run'} else {'tha3_models'}
        $localPython=Get-ComponentPythonExecutable $PortableRoot $component ($relative+'/Scripts/python.exe')
        if(-not(Test-LocalPython $PortableRoot $localPython)) { Write-Host "[缺失/MISSING] 本地环境 / local environment: $relative"; $failed++ }
    }

    foreach ($rel in @($tha3Record.verify)) {
        Test-RequiredFile "tha3_models: $rel" ([string]$rel) $failedRef | Out-Null
    }
    Test-RequiredFile "THA3 运行目录链接 / THA3 runtime cwd link" "face-puppeteer-ui-enhancements-ai-code/talking-head-anime-4-demo/data/models/separable_half/face_morpher.pt" $failedRef | Out-Null
} else {
    Write-Host "[跳过/SKIP] tha3_models 附加组件 / add-on"
}

if ($IncludeTha4Training) {
    $teacher=Join-Path $PortableRoot 'addons/tha4_training'
    $bindings=Get-Content -LiteralPath (Join-Path $PortableRoot 'runtime/bindings/components.json') -Raw | ConvertFrom-Json
        $teacherPython=Join-Path $PortableRoot $bindings.components.tha4_training.python
    foreach($relative in @('THA4Train.exe','app/worker.py','src/tha4/distiller/distiller_config.py','data/tha4/face_morpher.pt','data/tha4/body_morpher.pt','data/tha4/eyebrow_decomposer.pt','data/tha4/eyebrow_morphing_combiner.pt','data/tha4/upscaler.pt','data/pose_dataset.pt')) {
        if(-not(Test-Path -LiteralPath (Join-Path $teacher $relative))) { Write-Host "[缺失/MISSING] 独立 Teacher / standalone teacher: $relative"; $failed++ }
    }
    if(-not(Test-LocalPython $PortableRoot $teacherPython)) { Write-Host '[缺失/MISSING] Teacher 的本地 Python / folder-local teacher Python'; $failed++ }
} else { Write-Host '[跳过/SKIP] 独立 THA4 Teacher / standalone THA4 teacher' }

if ($RequireOutputEnhancement) {
    $enhRecord = Get-AddonRecord -Manifest $manifest -AddonId "output_enhancement"
    foreach ($rel in @($enhRecord.verify)) {
        Test-RequiredFile "output_enhancement: $rel" ([string]$rel) $failedRef | Out-Null
    }
    $enhPython = Get-MouseStudentPythonExe -PortableRoot $PortableRoot
    if ($enhPython -and (Test-Path $enhPython)) {
        Write-Host ""
        Write-Host "正在检查 output_enhancement 导入 / Checking output_enhancement imports (onnxruntime, pyanime4k) ..."
        if (Test-OutputEnhancementPipImports -PythonExe $enhPython) {
            Write-Host "[OK] output_enhancement pip 导入 / pip imports"
        } else {
            Write-Host "[缺失/MISSING] output_enhancement pip 导入（先装 [1] 或 [3]，再重新运行 DEPLOY [6]）"
            Write-Host "               output_enhancement pip imports (re-run DEPLOY [6] after [1] or [3])"
            $failed++
        }
        # f-058: TensorRT is optional (NVIDIA, compute capability >= 7.5); report only.
        if (Test-TensorRTCapableGpu -PythonExe $enhPython) {
            if (Test-TensorRTImport -PythonExe $enhPython -PortableRoot $PortableRoot) { Write-Host "[OK] TensorRT（NN 后端 = TensorRT 时供 THA4 Student 使用 / THA4 Student when NN backend = TensorRT）" }
            else { Write-Host "[警告/WARN] TensorRT 未安装（可选；重新运行 DEPLOY [6]） / TensorRT not installed (optional; re-run DEPLOY [6])" }
        } else { Write-Host "[跳过/SKIP] TensorRT：没有计算能力 >= 7.5 的 NVIDIA 显卡 / no NVIDIA GPU with compute capability >= 7.5" }
    } else {
        Write-Host "[缺失/MISSING] output_enhancement 运行环境（请先装 [1] basic_run 或 [3] face_puppeteer）"
        Write-Host "               output_enhancement runtime (install [1] basic_run or [3] face_puppeteer first)"
        $failed++
    }
} else {
    Write-Host "[跳过/SKIP] output_enhancement 附加组件 / add-on"
}

if ($python -and (Test-Path $python)) {
    Write-Host ""
    Write-Host "正在检查 Python 导入 / Checking Python imports (torch, wx, mediapipe) ..."
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $importOut = & $python -c "import torch, wx, mediapipe; print(torch.__version__)" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Python 导入 / Python imports (torch $($importOut -join ''))"
    } else {
        Write-Host "[缺失/MISSING] Python 导入 / Python imports -> torch/wx/mediapipe（重新运行 DEPLOY.bat / re-run DEPLOY.bat）"
        Write-Host "  $importOut"
        $failed++
    }
    if ($RequireFacePuppeteer -and $LASTEXITCODE -eq 0) {
        Write-Host "正在检查面捕界面是否就绪 / Checking face capture UI readiness ..."
        $expDir = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview"
        $demoSrc = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src"
        $probeCode = @"
import sys
sys.path.insert(0, r'$expDir')
from mouse_mocap_driver import MOCAP_INPUT_MODE_MEDIAPIPE
from portable_paths import face_capture_assets_ready
from pathlib import Path
assert MOCAP_INPUT_MODE_MEDIAPIPE == 'mediapipe'
assert face_capture_assets_ready(Path(r'$PortableRoot'))
print('face capture ready')
"@
        $savedPythonPath = $env:PYTHONPATH
        $savedPortableRoot = $env:THA4_PORTABLE_ROOT
        $env:PYTHONPATH = $demoSrc
        $env:THA4_PORTABLE_ROOT = $PortableRoot
        $faceProbeOut = & $python -c $probeCode 2>&1
        $env:PYTHONPATH = $savedPythonPath
        $env:THA4_PORTABLE_ROOT = $savedPortableRoot
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] 面捕界面检测 / Face capture UI probe"
        } else {
            Write-Host "[缺失/MISSING] 面捕界面检测 / Face capture UI probe (load preview / portable_paths)"
            Write-Host "  $faceProbeOut"
            $failed++
        }
    }
    $ErrorActionPreference = $prevEap
}

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) {
        throw "部署校验失败（缺 $failed 项） / Deploy verification failed ($failed missing item(s))."
    }
    Write-Host "部署校验：仍缺 $failed 项 / Deploy verification: $failed item(s) still missing."
    exit 1
}

Write-Host "部署校验通过 / Deploy verification passed."
Write-Host ""
exit 0
