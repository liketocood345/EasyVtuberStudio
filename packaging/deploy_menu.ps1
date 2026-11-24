# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END
# EVS-DESIGN-AUDIT EVS-A122 BEGIN
# 设计[dep-003, dep-025] [静态符合（菜单）；部署未执行]
# 六档数字输入，Enter 只选基础；历史四档 Y/N 不再作为当前验收。安装幂等性、网络失败恢复和英文覆盖提醒需实际干净环境测试。
# 历史 bug 热点 #6：仅为回归关联，非声称本次故障已复现。
# EVS-DESIGN-AUDIT EVS-A122 END
param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string]$TierInput = "",
    [switch]$NonInteractive
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot

$DeployTierCatalog = @(
    @{ Number = 1; PackageId = "mouse_student"; Name = "basic_run"; Zh = "基础运行：鼠标 + THA4 Student 的最小运行环境（PyTorch + wx）"; En = "Minimal runtime for Mouse + THA4 Student (PyTorch + wx)" },
    @{ Number = 2; PackageId = "openseeface"; Name = "openseeface"; Zh = "OpenSeeFace 面捕（facetracker + 模型）"; En = "OpenSeeFace face capture (facetracker + models)" },
    @{ Number = 3; PackageId = "face_puppeteer"; Name = "face_puppeteer"; Zh = "MediaPipe 面捕（含完整 Python 运行环境）"; En = "MediaPipe face capture (includes full Python runtime)" },
    @{ Number = 4; PackageId = "tha3_models"; Name = "tha3_models"; Zh = "THA3 模型权重"; En = "THA3 portrait weights" },
    @{ Number = 5; PackageId = "tha4_training"; Name = "tha4_training"; Zh = "THA4 Teacher + 姿态数据集（训练 / 蒸馏）"; En = "THA4 teacher + pose dataset (training / distill)" },
    @{ Number = 6; PackageId = "output_enhancement"; Name = "output_enhancement"; Zh = "NN 超分 + RIFE 补帧（DirectML ONNX Runtime）；NVIDIA 显卡另装 TensorRT"; En = "NN super-resolution + RIFE (DirectML ONNX Runtime) + TensorRT on NVIDIA" }
)

# Chinese names for addons_manifest.json entries (the manifest keeps English labels).
$AddonLabelZh = @{
    face_puppeteer     = "面捕运行环境（PyTorch + wx + MediaPipe）"
    openseeface        = "OpenSeeFace facetracker 程序 + 模型"
    tha3_models        = "THA3 PyTorch 模型（约 2 GB）"
    tha4_training      = "THA4 独立 Teacher：外壳、源码、五个权重和姿态数据（装在本目录内）"
    output_enhancement = "输出增强（NN 超分 + RIFE ONNX + onnxruntime；NVIDIA 显卡另装 TensorRT）"
}

function Show-AddonStatus {
    $manifest = Get-AddonsManifest -ScriptRoot $PSScriptRoot
    $mouseReady = $false
    try {
        $mouseReady = Test-MouseStudentRuntime -PortableRoot $PortableRoot
    } catch {
        Write-Host ""
        Write-Host "  （暂时无法检测 Python；需要时 DEPLOY 会自动安装。）"
        Write-Host "  (Could not probe system Python yet; DEPLOY will install if needed.)"
    }
    Write-Host ""
    Write-Host "当前状态 / Current status:"
    $basicMark = if ($mouseReady) { "已装 YES" } else { "未装 NO " }
    Write-Host "  [$basicMark] basic_run - 鼠标 + THA4 Student / Mouse + THA4 Student"
    Write-Host "                  workspace\student_venv 或面捕运行环境 / or face runtime"
    foreach ($addon in @($manifest.addons)) {
        $installed = Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $addon
        $mark = if ($installed) { "已装 YES" } else { "未装 NO " }
        $folder = Get-AddonFolderRelative -AddonRecord $addon
        $labelZh = [string]$AddonLabelZh[[string]$addon.id]
        Write-Host "  [$mark] $($addon.id) - $(if ($labelZh) { $labelZh } else { $addon.label })"
        if ($labelZh) { Write-Host "                  $($addon.label)" }
        Write-Host "                  目录 / folder: $folder"
    }
    Write-Host ""
}

function Test-TierInputHasSeparator {
    param([string]$Text)
    foreach ($ch in @(' ', "`t", ',', ';')) {
        if ($Text.Contains($ch)) {
            return $true
        }
    }
    return $false
}

function Split-TierInputTokens {
    param([string]$Text)
    $out = @()
    $chunks = $Text -split '\s+'
    foreach ($chunk in $chunks) {
        if ([string]::IsNullOrWhiteSpace($chunk)) { continue }
        foreach ($piece in ($chunk -split ',')) {
            if ([string]::IsNullOrWhiteSpace($piece)) { continue }
            foreach ($sub in ($piece -split ';')) {
                if (-not [string]::IsNullOrWhiteSpace($sub)) {
                    $out += $sub.Trim()
                }
            }
        }
    }
    return $out
}

function Parse-DeployTierNumbers {
    param(
        [string]$Raw,
        [int]$MaxTier
    )
    if ([string]::IsNullOrWhiteSpace($Raw)) {
        return @(1)
    }

    $trimmed = $Raw.Trim()
    $numbers = @()

    if (Test-TierInputHasSeparator $trimmed) {
        $parts = Split-TierInputTokens $trimmed
        foreach ($part in $parts) {
            if ($part -notmatch '^\d+$') {
                throw "无效的档位编号 / Invalid tier token: $part"
            }
            $numbers += [int]$part
        }
    } elseif ($trimmed -match '^\d+$') {
        $remaining = $trimmed
        while ($remaining.Length -gt 0) {
            if ($remaining.Length -ge 2 -and $remaining.StartsWith("10")) {
                $numbers += 10
                $remaining = $remaining.Substring(2)
            } else {
                $numbers += [int]$remaining.Substring(0, 1)
                $remaining = $remaining.Substring(1)
            }
        }
    } else {
        throw "无效的档位输入 / Invalid tier input: $trimmed"
    }

    $invalid = @($numbers | Where-Object { $_ -lt 1 -or $_ -gt $MaxTier })
    if ($invalid.Count -gt 0) {
        throw "未知的档位编号 / Unknown tier number(s): $($invalid -join ', ')（有效范围 / valid: 1-$MaxTier）"
    }

    return @($numbers | Select-Object -Unique)
}

function Map-TierNumbersToPackageIds {
    param([int[]]$TierNumbers)

    $byNumber = @{}
    foreach ($tier in $DeployTierCatalog) {
        $byNumber[[int]$tier.Number] = [string]$tier.PackageId
    }

    $selected = @()
    foreach ($n in @($TierNumbers)) {
        $selected += $byNumber[$n]
    }
    return @($selected | Where-Object { $_ } | Select-Object -Unique)
}

function Read-DeployTierChoices {
    $maxTier = [int]$DeployTierCatalog[-1].Number

    Write-Host ""
    Write-Host "选择要安装的档位（输入编号，共 $maxTier 档）："
    Write-Host "Select install tiers (enter numbers; up to $maxTier tiers):"
    Write-Host ""
    foreach ($tier in $DeployTierCatalog) {
        Write-Host ("  [{0}] {1,-19} {2}" -f $tier.Number, $tier.Name, $tier.Zh)
        Write-Host ("{0}{1}" -f (' ' * 26), $tier.En)
    }
    Write-Host ""
    Write-Host "  面捕：装 [2] 或 [3] 任一个即可用摄像头追踪面部。"
    Write-Host "  Face capture: install [2] OR [3] (either enables camera face tracking)."
    Write-Host ""
    Write-Host "  示例 / Examples: 1  |  2  |  1 3 6  |  136"
    Write-Host "  （每个数字是一个档位编号 / each digit is a tier number）"
    Write-Host "  不输入直接回车 = 只装 [1] basic_run。"
    Write-Host "  Press Enter without typing = install [1] basic_run only."
    Write-Host ""

    $rawInput = $TierInput
    if (-not $NonInteractive) {
        $rawInput = Read-Host "要安装的档位编号 / Tier numbers to install"
    } elseif ([string]::IsNullOrWhiteSpace($rawInput)) {
        $rawInput = ""
    }

    $tierNumbers = Parse-DeployTierNumbers -Raw $rawInput -MaxTier $maxTier
    $selected = Map-TierNumbersToPackageIds -TierNumbers $tierNumbers

    if ($selected.Count -eq 0) {
        Write-Host ""
        Write-Host "未选择任何档位。至少需要 [1] basic_run 或一个面捕档（[2]/[3]）。"
        Write-Host "Nothing selected. At least [1] basic_run or a face-capture tier ([2]/[3]) is required."
        Write-Host "请重新运行 DEPLOY.bat 并输入 1（或直接回车使用默认）。"
        Write-Host "Re-run DEPLOY.bat and enter 1 (or press Enter for default)."
        exit 1
    }

    $hasBasic = $tierNumbers -contains 1
    $hasFace = $tierNumbers -contains 3
    $hasTha3 = $tierNumbers -contains 4
    $hasTha4 = $tierNumbers -contains 5

    Write-Host ""
    Write-Host "已选档位 / Selected tiers: $($tierNumbers -join ', ') -> $($selected -join ', ')"

    if (-not $hasBasic -and -not $hasFace -and ($hasTha3 -or $hasTha4)) {
        Write-Host ""
        Write-Host "THA3 会准备自己的本地环境；THA4 训练使用单独的便携 Teacher 目录。"
        Write-Host "THA3 prepares its local environment; THA4 training uses a separate portable Teacher folder."
        Write-Host ""
    }

    return @($selected)
}

Show-AddonStatus
return @(Read-DeployTierChoices)
