# dep-024/025, f-055/056: verify the canonical module path, not legacy data/.
# f-058 / EVS-PERF 3.4 (2026-11-24): on NVIDIA GPUs with compute capability >= 7.5
# also install the hash-locked TensorRT profile 'trt' (TensorRT 10.13 for CUDA 11;
# ~1.2 GB download, ~1.7 GB on disk, one-time). THA4 Student uses it only when the
# NN backend is set to TensorRT. Optional: a failure warns and DirectML/PyTorch stay
# usable. EVS_DEPLOY_SKIP_TENSORRT=1 skips it.
param([Parameter(Mandatory=$true)][string]$PortableRoot)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'addon_paths.ps1')
. (Join-Path $PSScriptRoot 'deploy_common.ps1')
$PortableRoot=Resolve-PortableRoot $PortableRoot
function Install-OptionalTensorRT([string]$Root,[string]$Python) {
    if($env:EVS_DEPLOY_SKIP_TENSORRT -eq '1') { Write-Host '[跳过/SKIP] TensorRT（已设置 EVS_DEPLOY_SKIP_TENSORRT=1） / TensorRT (EVS_DEPLOY_SKIP_TENSORRT=1)'; return }
    if(-not(Test-TensorRTCapableGpu $Python)) { Write-Host '[跳过/SKIP] TensorRT：没有计算能力 >= 7.5 的 NVIDIA 显卡（DirectML 仍可用）'; Write-Host '            TensorRT: no NVIDIA GPU with compute capability >= 7.5 (DirectML stays available)'; return }
    if(Test-TensorRTImport $Python $Root) { Write-Host '[OK] TensorRT 已安装 / TensorRT already installed'; return }
    Write-Host '正在安装 TensorRT 10.13（CUDA 11；下载约 1.2 GB，占用约 1.7 GB；只需一次）...'
    Write-Host 'Installing TensorRT 10.13 for CUDA 11 (~1.2 GB download, ~1.7 GB on disk; one-time) ...'
    try {
        Install-LockedRuntime $Root $Python @('base','output','trt')
        if(Test-TensorRTImport $Python $Root) { Write-Host '[OK] TensorRT 安装完成（NN 后端选 TensorRT 时 THA4 使用）'; Write-Host '     TensorRT installed (used by THA4 when the NN backend is TensorRT)' }
        else { Write-Warning 'TensorRT 已安装但无法导入，THA4 继续使用 PyTorch / TensorRT installed but does not import; THA4 keeps PyTorch' }
    } catch {
        Write-Warning ('TensorRT 未安装 / TensorRT not installed: ' + $_.Exception.Message + '（DirectML/PyTorch 不受影响；重新运行 DEPLOY [6] 可重试 / DirectML/PyTorch unaffected; re-run DEPLOY [6] to retry）')
    }
}
Initialize-DeploySession $PortableRoot
& (Join-Path $PSScriptRoot 'fetch_upstream_assets.ps1') -PortableRoot $PortableRoot -PackageIds @('ezvtb_nn_weights')
if($LASTEXITCODE -ne 0) { throw 'NN 模块完整性校验失败 / NN module integrity verification failed' }
$seen=@{}; $installed=0
foreach($role in @('app','basic_run','face_puppeteer','tha3_models')) {
    $python=Get-ComponentPythonExecutable $PortableRoot $role 'runtime/venvs/common/Scripts/python.exe'
    if(-not(Test-Path -LiteralPath $python) -or $seen.ContainsKey($python.ToLowerInvariant())) { continue }
    $seen[$python.ToLowerInvariant()]=$true
    if(-not(Test-LocalPython $PortableRoot $python)) { throw '拒绝使用本目录以外的 NN 运行环境 / External NN runtime rejected' }
    Install-LockedRuntime $PortableRoot $python @('base','output')
    if(-not(Test-OutputEnhancementPipImports $python) -or -not(Test-OrtHasDirectML $python)) { throw 'NN/DirectML 初始化失败 / NN/DirectML initialization failed' }
    Install-OptionalTensorRT $PortableRoot $python
    $installed++
}
if(-not $installed) { throw '请先安装本地基础运行环境（[1] 或 [3]）再装输出增强 / Install a local base runtime before output enhancement' }
$addonRoot=Join-Path $PortableRoot 'addons/output_enhancement'
Set-Content -LiteralPath (Join-Path $addonRoot '.installed') -Value (Get-Date -Format o) -Encoding UTF8
Write-Host '[OK] NN 附加模块和 DirectML 运行环境校验通过。 / NN canonical addon module and DirectML runtime verified.'
exit 0
