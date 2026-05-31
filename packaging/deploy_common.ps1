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
