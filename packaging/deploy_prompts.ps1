param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$Confirmed
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

function Test-DeployOverwriteTargets {
    $targets = @(
        (Join-Path $PortableRoot "addons\face_puppeteer\venv"),
        (Join-Path $PortableRoot "runtime\venv"),
        (Join-Path $PortableRoot "workspace\.deploy_complete"),
        (Join-Path $PortableRoot "workspace\.portable_bootstrap_done")
    )
    return @($targets | Where-Object { Test-Path $_ })
}

function Show-DeployWarning {
    param([string[]]$ExistingPaths)

    Write-Host ""
    Write-Host "============================================================"
    Write-Host " EasyVtuberStudio 部署 / DEPLOY"
    Write-Host "============================================================"
    Write-Host ""
    Write-Host " 可选附加组件装到 addons\，再链接进 CORE 路径。"
    Write-Host " Optional add-ons install to addons\ and link into CORE paths."
    Write-Host ""
    Write-Host " 部署档位（输入编号；直接回车 = 只装 [1]）："
    Write-Host " DEPLOY tiers (enter numbers; Press Enter = [1] only):"
    Write-Host "   [1] basic_run          鼠标 + THA4 Student 运行环境（约 2-4 GB）"
    Write-Host "                          Mouse + THA4 Student runtime (~2-4 GB)"
    Write-Host "   [2] openseeface        OpenSeeFace facetracker + 模型（约 0.2 GB）"
    Write-Host "                          OpenSeeFace facetracker + models (~0.2 GB)"
    Write-Host "   [3] face_puppeteer     摄像头面捕 + MediaPipe（约 3-4 GB）"
    Write-Host "                          Camera face capture + MediaPipe (~3-4 GB)"
    Write-Host "   [4] tha3_models        THA3 模型权重（约 2 GB）"
    Write-Host "                          THA3 portrait weights (~2 GB)"
    Write-Host "   [5] tha4_training      THA4 Teacher + 姿态数据集（约 1.5-3 GB）"
    Write-Host "                          THA4 teacher + pose dataset (~1.5-3 GB)"
    Write-Host "   [6] output_enhancement NN 超分 + RIFE ONNX（约 0.8 GB；NVIDIA 显卡另加 1.7 GB TensorRT）"
    Write-Host "                          NN super-resolution + RIFE ONNX (~0.8 GB; +1.7 GB TensorRT on NVIDIA)"
    Write-Host ""
    Write-Host " 重新运行可能覆盖 addons\face_puppeteer\venv。"
    Write-Host " Re-running may overwrite addons\face_puppeteer\venv."
    Write-Host " 已下载的模型包通常会跳过。"
    Write-Host " Already-downloaded model packs are usually skipped."
    Write-Host ""
    if ($ExistingPaths.Count -gt 0) {
        Write-Host " 检测到已有的部署内容 / Existing deploy artifacts detected:"
        foreach ($rel in $ExistingPaths) {
            $short = $rel.Substring($PortableRoot.Length).TrimStart("\")
            if (-not $short) { $short = $rel }
            Write-Host "   - $short"
        }
        Write-Host ""
    }
    Write-Host " 需要：Windows 10/11 x64、联网、约 15 GB 可用磁盘空间。"
    Write-Host " Requires: Windows 10/11 x64, internet, ~15 GB free disk space."
    Write-Host " 可能需要 10-40 分钟，请不要关闭此窗口。"
    Write-Host " May take 10-40 minutes. Do not close this window."
    Write-Host ""
}

if ($Confirmed) {
    return
}

$existing = Test-DeployOverwriteTargets
Show-DeployWarning -ExistingPaths $existing

Write-Host "现在打开附加组件菜单？输入 Y 并回车（其他任意键取消）。"
$answer = Read-Host "Open add-on menu now? Type Y and press Enter (any other key cancels)"
if ($answer -notmatch '^[Yy]$') {
    Write-Host ""
    Write-Host "已取消，未修改任何文件。 / Cancelled. No files were changed."
    exit 1
}

exit 0
