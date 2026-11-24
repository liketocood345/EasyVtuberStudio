param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Strict
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
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
Write-Host "鼠标 Student 校验 / Mouse student verification: $PortableRoot"
Write-Host ""

$failed = 0
$failedRef = [ref]$failed

Test-RequiredFile "EasyVtuberStudio.exe" "EasyVtuberStudio.exe" $failedRef | Out-Null
Test-RequiredFile "主程序入口 / load preview entry" "face-puppeteer-ui-enhancements-ai-code/experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py" $failedRef | Out-Null
Test-RequiredFile "bai 学生模型 yaml / bai student yaml" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/character_model.yaml" $failedRef | Out-Null
Test-RequiredFile "bai face_morpher.pt" "data/character_models/baiten_from_project_forlon9/bai_450k/character_model/face_morpher.pt" $failedRef | Out-Null

$python = Get-MouseStudentPythonExe -PortableRoot $PortableRoot
if ($python) {
    Write-Host "[OK] Python 运行环境 / Python runtime -> $python"
} else {
    Write-Host "[缺失/MISSING] Python 运行环境（workspace/student_venv、face_puppeteer 附加组件，或带 torch+wx 的系统 py）"
    Write-Host "               Python runtime (workspace/student_venv, addons face_puppeteer, or system py with torch+wx)"
    $failed++
}

if ($python -and (Test-Path $python)) {
    Write-Host ""
    Write-Host "正在检查 Python 导入 / Checking Python imports (torch, wx, matplotlib, tha4) ..."
    $probeScript = Join-Path $PSScriptRoot "probe_mouse_student_runtime.py"
    if (Test-Path $probeScript) {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $importOut = & $python $probeScript $python $PortableRoot 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] 鼠标 Student 运行环境检测 / Mouse student runtime probe"
        } else {
            Write-Host "[缺失/MISSING] 鼠标 Student 运行环境检测失败 / Mouse student runtime probe failed"
            Write-Host "  $importOut"
            $failed++
        }
        $ErrorActionPreference = $prevEap
    } else {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $importOut = & $python -c "import torch, wx, matplotlib; print(torch.__version__)" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "[OK] Python 导入 / Python imports (torch $($importOut -join ''))"
        } else {
            Write-Host "[缺失/MISSING] Python 导入 / Python imports -> torch/wx/matplotlib"
            Write-Host "  $importOut"
            $failed++
        }
        $ErrorActionPreference = $prevEap
    }
}

Write-Host ""
if ($failed -gt 0) {
    if ($Strict) {
        throw "鼠标 Student 校验失败（缺 $failed 项） / Mouse student verification failed ($failed missing item(s))."
    }
    exit 1
}

Write-Host "鼠标 Student 校验通过（鼠标 + 音频驱动 THA4 Student；不需要 MediaPipe 附加组件）。"
Write-Host "Mouse student verification passed (Mouse + Audio THA4 Student; no MediaPipe add-on required)."
Write-Host ""
exit 0
