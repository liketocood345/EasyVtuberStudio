# Shared DEPLOY session helpers (TLS, logging, portable root checks).
$ErrorActionPreference = "Stop"

function Initialize-DeploySession {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PortableRoot
    )
    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 -bor [Net.SecurityProtocolType]::Tls13
    } catch {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    }
    $script:DeployLogPath = Join-Path $PortableRoot "workspace\deploy.log"
    if (-not (Test-Path (Split-Path $script:DeployLogPath -Parent))) {
        New-Item -ItemType Directory -Force -Path (Split-Path $script:DeployLogPath -Parent) | Out-Null
    }
}

function Write-DeployLog {
    param([string]$Message)
    if (-not $script:DeployLogPath) { return }
    $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Add-Content -Path $script:DeployLogPath -Value "[$stamp] $Message" -Encoding UTF8
}

function Write-DeployFailure {
    param(
        [Parameter(Mandatory = $true)]
        $ErrorRecord
    )
    $text = if ($ErrorRecord -is [System.Management.Automation.ErrorRecord]) {
        $ErrorRecord.Exception.Message
    } else {
        [string]$ErrorRecord
    }
    Write-Host ""
    Write-Host "DEPLOY failed: $text" -ForegroundColor Red
    Write-DeployLog "ERROR: $text"
    if ($ErrorRecord -is [System.Management.Automation.ErrorRecord] -and $ErrorRecord.ScriptStackTrace) {
        Write-DeployLog $ErrorRecord.ScriptStackTrace
    }
}

function Sync-BundledEzvtbNnWeights {
    param(
        [Parameter(Mandatory = $true)][string]$PortableRoot,
        [Parameter(Mandatory = $true)][string]$AddonDataRoot
    )
    $bundled = Join-Path $PortableRoot "data\ezvtb_nn"
    if (-not (Test-Path $bundled)) { return $false }
    $copied = $false
    foreach ($sub in @("rife", "waifu2x", "Real-ESRGAN")) {
        $src = Join-Path $bundled $sub
        if (-not (Test-Path $src)) { continue }
        $dst = Join-Path $AddonDataRoot $sub
        New-Item -ItemType Directory -Force -Path $dst | Out-Null
        Get-ChildItem -Path $src -Filter "*.onnx" -File -ErrorAction SilentlyContinue | ForEach-Object {
            $target = Join-Path $dst $_.Name
            if (-not (Test-Path $target) -or $_.LastWriteTimeUtc -gt (Get-Item $target).LastWriteTimeUtc) {
                Copy-Item -Force $_.FullName $target
                $copied = $true
            }
        }
    }
    return $copied
}

function Invoke-PipUpgradePackages {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PythonExe,
        [Parameter(Mandatory = $true)]
        [string[]]$Packages,
        [string]$Label = "pip install"
    )
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        throw "Python not found: $PythonExe"
    }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    Write-Host "${Label}: $($Packages -join ', ')"
    $pipOutput = & $PythonExe -m pip install --upgrade @Packages 2>&1
    foreach ($line in @($pipOutput)) {
        if ($line -is [System.Management.Automation.ErrorRecord]) {
            Write-Host $line.ToString()
        } else {
            Write-Host $line
        }
    }
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEap
    if ($exitCode -ne 0) {
        throw "pip install failed (exit=$exitCode): $($Packages -join ' ')"
    }
}
