# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END
# EVS-DESIGN-AUDIT EVS-A124 BEGIN
# 设计[dep-004] [静态关联 / 删除后重装未测]
# 按 addon ID 重置独立资源；RESET_ADDON 文件名是实现选择。须验证删后识别未安装及可重装，本次不执行删除脚本。
# 历史 bug 热点 #6：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A124 END
param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [Parameter(Mandatory = $true)]
    [string]$AddonId,
    [switch]$Confirmed
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
$record = Get-AddonRecord -Manifest $manifest -AddonId $AddonId
$folder = Get-AddonFolderAbsolute -PortableRoot $PortableRoot -AddonRecord $record

if (-not $Confirmed) {
    Write-Host "Use RESET_ADDON.bat or pass -Confirmed"
    exit 1
}

if (Test-Path $folder) {
    Write-Host "Removing $folder ..."
    Remove-Item -LiteralPath $folder -Recurse -Force
}

& (Join-Path $PSScriptRoot "reconcile_portable_layout.ps1") -PortableRoot $PortableRoot
Write-Host "Reset complete for $AddonId."
exit 0
