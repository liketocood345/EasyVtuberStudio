# Shared add-on path helpers (single source: packaging/addons_manifest.json)
$ErrorActionPreference = "Stop"

function Resolve-PortableRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PortableRoot
    )
    $candidate = $PortableRoot.TrimEnd('\', '/')
    if ([string]::IsNullOrWhiteSpace($candidate)) {
        throw "PortableRoot is empty. Run DEPLOY.bat from the extracted ZIP folder."
    }
    if (-not (Test-Path -LiteralPath $candidate)) {
        throw @(
            "Portable root not found: $candidate"
            "Run DEPLOY.bat from the folder that contains EasyVtuberStudio.exe and DEPLOY.bat."
        ) -join "`n"
    }
    return (Resolve-Path -LiteralPath $candidate).Path
}

function Invoke-PyLauncherSafe {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$PyArgs
    )
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        return @{ ExitCode = 9009; Output = @() }
    }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $output = @()
    $exitCode = 1
    try {
        $raw = & py @PyArgs 2>&1
        foreach ($line in @($raw)) {
            if ($line -is [System.Management.Automation.ErrorRecord]) { continue }
            $text = [string]$line
            if ($text -match '^\[ERROR\]') { continue }
            $output += $text
        }
        if ($null -ne $LASTEXITCODE) { $exitCode = [int]$LASTEXITCODE }
    } catch {
        $exitCode = 1
    } finally {
        $ErrorActionPreference = $prevEap
    }
    return @{ ExitCode = $exitCode; Output = $output }
}

function Get-PyLauncherPythonVersion {
    param([string]$VersionSpec = "3.11")
    $result = Invoke-PyLauncherSafe @("-$VersionSpec", "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    if ($result.ExitCode -ne 0) { return $null }
    $ver = [string]($result.Output | Where-Object { $_ } | Select-Object -Last 1).Trim()
    if ($ver -match '^3\.(10|11)$') { return $ver }
    return $null
}

function Resolve-PyLauncherExecutable {
    param([string[]]$VersionSpecs = @("3.11", "3.10"))
    foreach ($spec in $VersionSpecs) {
        $result = Invoke-PyLauncherSafe @("-$spec", "-c", "import sys; print(sys.executable)")
        if ($result.ExitCode -ne 0) { continue }
        $exe = [string]($result.Output | Where-Object { $_ } | Select-Object -Last 1).Trim()
        if ($exe -and (Test-Path -LiteralPath $exe)) { return $exe }
    }
    return $null
}

function Get-SuitablePythonCandidateSpec {
    param([Parameter(Mandatory=$true)][string]$PortableRoot)
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    $python=Join-Path $PortableRoot 'runtime/python310/python.exe'
    if(Test-LocalPython $PortableRoot $python) { return @{Command=$python;Args=@();Version='3.10'} }
    return $null
}

function Get-AddonsManifestPath {
    param([string]$ScriptRoot = $PSScriptRoot)
    return Join-Path $ScriptRoot "addons_manifest.json"
}

function Get-AddonsManifest {
    param([string]$ScriptRoot = $PSScriptRoot)
    $path = Get-AddonsManifestPath -ScriptRoot $ScriptRoot
    if (-not (Test-Path $path)) {
        throw "Missing packaging/addons_manifest.json"
    }
    return Get-Content $path -Raw | ConvertFrom-Json
}

function Resolve-PortableRootPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PortableRoot,
        [Parameter(Mandatory = $true)]
        [string]$RelativePath
    )
    return Join-Path $PortableRoot (($RelativePath -replace "/", "\"))
}

function Get-AddonRecord {
    param(
        [Parameter(Mandatory = $true)]
        $Manifest,
        [Parameter(Mandatory = $true)]
        [string]$AddonId
    )
    $record = @($Manifest.addons | Where-Object { $_.id -eq $AddonId } | Select-Object -First 1)
    if (-not $record) {
        throw "Unknown addon id: $AddonId"
    }
    return $record
}

function Get-AddonFolderRelative {
    param(
        [Parameter(Mandatory = $true)]
        $AddonRecord
    )
    $root = "addons"
    return Join-Path $root ([string]$AddonRecord.folder)
}

function Get-AddonFolderAbsolute {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PortableRoot,
        [Parameter(Mandatory = $true)]
        $AddonRecord
    )
    return Resolve-PortableRootPath $PortableRoot (Get-AddonFolderRelative -AddonRecord $AddonRecord)
}

function Test-AddonInstalled {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PortableRoot,
        [Parameter(Mandatory = $true)]
        $AddonRecord
    )
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    if($AddonRecord.id -eq 'tha4_training') {
        $teacher=Join-Path $PortableRoot 'addons/tha4_training'
        foreach($relative in @('THA4Train.exe','data/tha4/face_morpher.pt','data/tha4/body_morpher.pt','data/tha4/eyebrow_decomposer.pt','data/tha4/eyebrow_morphing_combiner.pt','data/tha4/upscaler.pt','data/pose_dataset.pt')) {
            if(-not(Test-Path -LiteralPath (Join-Path $teacher $relative))) { return $false }
        }
        $bindings=Get-Content -LiteralPath (Join-Path $PortableRoot 'runtime/bindings/components.json') -Raw | ConvertFrom-Json
        $teacherPython=Join-Path $PortableRoot $bindings.components.tha4_training.python
        return (Test-LocalPython $PortableRoot $teacherPython)
    }
    if($AddonRecord.id -eq 'face_puppeteer' -and -not(Test-LocalPython $PortableRoot (Get-ComponentPythonExecutable $PortableRoot 'face_puppeteer' 'runtime/venvs/common/Scripts/python.exe'))) { return $false }
    if($AddonRecord.id -eq 'tha3_models' -and -not(Test-LocalPython $PortableRoot (Get-ComponentPythonExecutable $PortableRoot 'tha3_models' 'runtime/venvs/common/Scripts/python.exe'))) { return $false }
    foreach ($rel in @($AddonRecord.verify)) {
        $path = Resolve-PortableRootPath $PortableRoot ([string]$rel)
        if (-not (Test-Path $path)) {
            return $false
        }
    }
    return $true
}

function Get-FacePuppeteerVenvRelative {
    return "runtime/venvs/common"
}

function Get-FacePuppeteerMediapipeRelative {
    return "addons/face_puppeteer/mediapipe"
}

function Test-FacePuppeteerVenv {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    # bh-6 26.10.31 03:08 s
    $python = Get-ComponentPythonExecutable $PortableRoot 'face_puppeteer' 'runtime/venvs/common/Scripts/python.exe'
    return (Test-LocalPython $PortableRoot $python)
    # bh-6 26.10.31 03:08 e
}

function Get-MouseStudentVenvRelative {
    return "runtime/venvs/common"
}

function Get-MouseStudentVenvAbsolute {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    return Split-Path (Split-Path (Get-ComponentPythonExecutable $PortableRoot 'basic_run' 'runtime/venvs/common/Scripts/python.exe') -Parent) -Parent
}

function Test-PythonImports {
    param(
        [Parameter(Mandatory = $true)][string]$PythonExe,
        [switch]$RequireMediapipe
    )
    $code = if ($RequireMediapipe) { "import torch, wx, mediapipe" } else { "import torch, wx" }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $PythonExe -c $code 2>$null | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return $ok
}

function Get-MouseStudentPythonExe {
    param([Parameter(Mandatory=$true)][string]$PortableRoot)
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    if(Get-ComponentRuntimeBinding $PortableRoot 'basic_run') {
        $python=Get-ComponentPythonExecutable $PortableRoot 'basic_run' 'runtime/venvs/common/Scripts/python.exe'
        if((Test-LocalPython $PortableRoot $python) -and (Test-PythonImports $python)) { return $python }
        return $null
    }
    foreach($relative in @('runtime/venvs/common','workspace/student_venv','addons/face_puppeteer/venv','addons/tha3_models/venv')) {
        $python=Join-Path $PortableRoot ($relative+'/Scripts/python.exe')
        if((Test-LocalPython $PortableRoot $python) -and (Test-PythonImports $python)) { return $python }
    }
    return $null
}

function Test-MouseStudentRuntime {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    return [bool](Get-MouseStudentPythonExe $PortableRoot)
}

function Test-OutputEnhancementInstalled {
    param(
        [Parameter(Mandatory = $true)][string]$PortableRoot,
        [Parameter(Mandatory = $true)][string]$ScriptRoot
    )
    $manifest = Get-AddonsManifest -ScriptRoot $ScriptRoot
    $record = Get-AddonRecord -Manifest $manifest -AddonId "output_enhancement"
    return Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $record
}

function Test-OutputEnhancementPipImports {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe)) { return $false }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $PythonExe -c "import onnxruntime; import pyanime4k" 2>$null | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return $ok
}

function Test-OrtHasDirectML {
    param([Parameter(Mandatory = $true)][string]$PythonExe)
    if (-not (Test-Path -LiteralPath $PythonExe)) { return $false }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    & $PythonExe -c "import onnxruntime as o, sys; sys.exit(0 if 'DmlExecutionProvider' in o.get_available_providers() else 1)" 2>$null | Out-Null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return $ok
}

function Test-FacePuppeteerRuntimeReady {
    param(
        [Parameter(Mandatory = $true)][string]$PortableRoot,
        [Parameter(Mandatory = $true)][string]$ScriptRoot
    )
    if (-not (Test-FacePuppeteerVenv -PortableRoot $PortableRoot)) {
        return $false
    }
    $python = Join-Path (Get-FacePuppeteerVenvAbsolute -PortableRoot $PortableRoot) "Scripts\python.exe"
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    if (-not (Test-LocalPython $PortableRoot $python)) { return $false }
    if (-not (Test-PythonImports -PythonExe $python -RequireMediapipe)) {
        return $false
    }
    $manifest = Get-AddonsManifest -ScriptRoot $ScriptRoot
    $record = Get-AddonRecord -Manifest $manifest -AddonId "face_puppeteer"
    return Test-AddonInstalled -PortableRoot $PortableRoot -AddonRecord $record
}

function Get-FacePuppeteerVenvAbsolute {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    if(Get-ComponentRuntimeBinding $PortableRoot 'face_puppeteer') {
        return Split-Path (Split-Path (Get-ComponentPythonExecutable $PortableRoot 'face_puppeteer' 'runtime/venvs/common/Scripts/python.exe') -Parent) -Parent
    }
    $primary = Resolve-PortableRootPath $PortableRoot (Get-FacePuppeteerVenvRelative)
    if (Test-Path (Join-Path $primary "Scripts\python.exe")) {
        return $primary
    }
    $legacy = Join-Path $PortableRoot "runtime\venv"
    if (Test-Path (Join-Path $legacy "Scripts\python.exe")) {
        return $legacy
    }
    return $primary
}

function Test-IsReparsePoint {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) { return $false }
    try {
        $item = Get-Item -LiteralPath $Path -Force
        return [bool]($item.Attributes -band [IO.FileAttributes]::ReparsePoint)
    } catch {
        return $false
    }
}

function Get-JunctionTargetPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-IsReparsePoint $Path)) { return $null }
    try {
        $item = Get-Item -LiteralPath $Path -Force
        $target = $item.Target
        if ($target -is [array]) {
            $target = $target | Where-Object { -not [string]::IsNullOrWhiteSpace([string]$_) } | Select-Object -First 1
        }
        if ([string]::IsNullOrWhiteSpace([string]$target)) { return $null }
        return [string]$target
    } catch {
        return $null
    }
}

function Test-JunctionLinkPointsTo {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )
    if (-not (Test-IsReparsePoint $LinkPath)) { return $false }
    if (-not (Test-Path -LiteralPath $TargetPath)) { return $false }
    $expected = (Resolve-Path -LiteralPath $TargetPath).Path
    $currentTarget = Get-JunctionTargetPath $LinkPath
    if ([string]::IsNullOrWhiteSpace($currentTarget)) { return $false }
    if (-not (Test-Path -LiteralPath $currentTarget)) { return $false }
    try {
        $current = (Resolve-Path -LiteralPath $currentTarget).Path
    } catch {
        return $false
    }
    return ($current -eq $expected)
}

function Remove-PathForLayout {
    param([Parameter(Mandatory = $true)][string]$Path)
    # Layout operations must stay beneath the explicitly selected portable root.
    # Never route PowerShell-enumerated paths into a second shell for deletion.
    . (Join-Path $PSScriptRoot 'portable_environment.ps1')
    $Path=Assert-LocalChild $PortableRoot $Path
    if (-not (Test-Path $Path)) { return }
    if (Test-IsReparsePoint $Path) {
        [IO.Directory]::Delete($Path)
        return
    }
    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($item -and $item.PSIsContainer) {
        Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue
    } else {
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }
}

function Ensure-Directory {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (-not (Test-Path $Path)) {
        New-Item -ItemType Directory -Force -Path $Path | Out-Null
    }
}

function Ensure-DeployLayoutDirectories {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    Ensure-Directory (Join-Path $PortableRoot "workspace")
    foreach ($rel in @(
            "addons/face_puppeteer",
            "addons/face_puppeteer/mediapipe",
            "addons/tha3_models",
            "addons/tha4_training"
        )) {
        Ensure-Directory (Resolve-PortableRootPath $PortableRoot $rel)
    }
}

function Ensure-JunctionLink {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )
    if (-not (Test-Path $TargetPath)) {
        Remove-PathForLayout $LinkPath
        return $false
    }
    $targetFull = (Resolve-Path -LiteralPath $TargetPath).Path
    if (Test-Path $LinkPath) {
        if (Test-JunctionLinkPointsTo -LinkPath $LinkPath -TargetPath $TargetPath) {
            return $true
        }
        Remove-PathForLayout $LinkPath
    }
    $parent = Split-Path $LinkPath -Parent
    Ensure-Directory $parent
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    cmd /c mklink /J "$LinkPath" "$targetFull" 2>$null | Out-Null
    $ErrorActionPreference = $prevEap
    if (-not (Test-Path $LinkPath)) {
        if ((Get-Item $TargetPath).PSIsContainer) {
            Copy-Item -Recurse -Force $TargetPath $LinkPath
        } else {
            Copy-Item -Force $TargetPath $LinkPath
        }
    }
    return (Test-Path $LinkPath)
}

function Ensure-FileJunctionLink {
    param(
        [Parameter(Mandatory = $true)][string]$LinkPath,
        [Parameter(Mandatory = $true)][string]$TargetPath
    )
    if (-not (Test-Path $TargetPath)) {
        Remove-PathForLayout $LinkPath
        return $false
    }
    $targetFull = (Resolve-Path -LiteralPath $TargetPath).Path
    if (Test-Path $LinkPath) {
        if (Test-JunctionLinkPointsTo -LinkPath $LinkPath -TargetPath $TargetPath) {
            return $true
        }
        Remove-PathForLayout $LinkPath
    }
    Ensure-Directory (Split-Path $LinkPath -Parent)
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    cmd /c mklink "$LinkPath" "$targetFull" 2>$null | Out-Null
    $ErrorActionPreference = $prevEap
    if (-not (Test-Path $LinkPath)) {
        Copy-Item -Force $TargetPath $LinkPath
    }
    return (Test-Path $LinkPath)
}

function Restore-Tha4TrainingPlaceholder {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    $tha4Dir = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\data\tha4"
    Ensure-Directory $tha4Dir
    $placeholder = Join-Path $tha4Dir "placeholder.txt"
    if (-not (Test-Path $placeholder)) {
        Set-Content -Path $placeholder -Encoding UTF8 -Value @(
            "THA4 teacher weights are optional add-ons.",
            "Install via DEPLOY.bat -> [4] tha4_training, or scripts\launch\THA4_DownloadTrainingAssets.bat",
            "Files install to addons/tha4_training/ and link here when present."
        )
    }
}

function Restore-Tha3ModelsReadme {
    param([Parameter(Mandatory = $true)][string]$PortableRoot)
    $modelsDir = Join-Path $PortableRoot "deps\tha3\models"
    Ensure-Directory $modelsDir
    $readme = Join-Path $modelsDir "README.txt"
    if (-not (Test-Path $readme)) {
        Set-Content -Path $readme -Encoding UTF8 -Value @(
            "THA3 model weights are NOT stored in Git.",
            "Install to addons/tha3_models/ via DEPLOY.bat -> [3] tha3_models, or scripts\launch\THA3_DownloadModels.bat."
        )
    }
}
