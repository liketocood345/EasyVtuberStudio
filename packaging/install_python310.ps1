param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [switch]$MouseStudentOnly
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "addon_paths.ps1")
$PortableRoot = Resolve-PortableRoot $PortableRoot
$ProgressPreference = "SilentlyContinue"

$PythonVersion = "3.10.11"
$InstallerName = "python-$PythonVersion-amd64.exe"
$InstallerUrl = "https://www.python.org/ftp/python/$PythonVersion/$InstallerName"
$EmbedName = "python-$PythonVersion-embed-amd64.zip"
$EmbedUrl = "https://www.python.org/ftp/python/$PythonVersion/$EmbedName"
$MarkerFile = Join-Path $PortableRoot "workspace\.python310_cmd.json"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message"
}

function Refresh-UserPath {
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $env:Path = @($userPath, $machinePath) -join ";"
}

function Register-Python310Marker {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python310\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python311\python.exe"),
        (Join-Path ${env:ProgramFiles} "Python310\python.exe"),
        (Join-Path ${env:ProgramFiles} "Python311\python.exe")
    )
    foreach ($path in $candidates) {
        if (-not (Test-Path $path)) { continue }
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "SilentlyContinue"
        $ver = & $path -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        $ErrorActionPreference = $prevEap
        if ($LASTEXITCODE -eq 0 -and [string]$ver.Trim() -match '^3\.(10|11)$') {
            @{ command = $path; source = "direct" } | ConvertTo-Json | Set-Content -Path $MarkerFile -Encoding UTF8
            Write-Host "  Registered Python: $path"
            return $true
        }
    }
    return $false
}

function Test-Python310Available {
    if (Register-Python310Marker) { return $true }
    foreach ($spec in Get-Python310Candidates) {
        if (Test-PythonCandidate $spec) { return $true }
    }
    return $false
}

function Get-Python310Candidates {
    $list = @(
        @{ Command = "py"; Args = @("-3.11") },
        @{ Command = "py"; Args = @("-3.10") }
    )
    if (Test-Path $MarkerFile) {
        try {
            $marked = Get-Content $MarkerFile -Raw | ConvertFrom-Json
            if ($marked.command) {
                $list += @{ Command = [string]$marked.command; Args = @() }
            }
        } catch { }
    }
    return $list
}

function Test-PythonCandidate($spec) {
    if ($spec.Command -eq "py") {
        $verSpec = if ($spec.Args -contains "-3.11") { "3.11" } else { "3.10" }
        return [bool](Get-PyLauncherPythonVersion $verSpec)
    }
    if (-not (Test-Path -LiteralPath $spec.Command)) { return $false }
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    $ver = & $spec.Command @($spec.Args + @("-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")) 2>$null
    $ok = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEap
    return ($ok -and [string]$ver.Trim() -match '^3\.(10|11)$')
}

function Try-WingetInstallPython310 {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { return $false }
    Write-Step "Trying winget: Python 3.10 (current user)"
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & winget install --id Python.Python.3.10 -e --scope user `
        --accept-package-agreements --accept-source-agreements --disable-interactivity 2>&1 | Out-Host
    $ErrorActionPreference = $prevEap
    Refresh-UserPath
    Start-Sleep -Seconds 3
    [void](Register-Python310Marker)
    return (Test-Python310Available)
}

function Try-ExeInstallerPython310([string]$InstallerPath) {
    Write-Step "Installing Python $PythonVersion from downloaded installer (current user)"
    Write-Host "  Please wait 1-3 minutes."

    $argSets = @(
        @("/quiet", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0", "Include_doc=0"),
        @("/passive", "InstallAllUsers=0", "PrependPath=1", "Include_launcher=1", "Include_test=0", "Include_doc=0")
    )

    foreach ($installArgs in $argSets) {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $p = Start-Process -FilePath $InstallerPath -ArgumentList $installArgs -Wait -PassThru
        $ErrorActionPreference = $prevEap
        Refresh-UserPath
        Start-Sleep -Seconds 2
        [void](Register-Python310Marker)
        if ($p.ExitCode -eq 0 -and (Test-Python310Available)) { return $true }
        Write-Host "  Installer exit $($p.ExitCode); trying next method if any."
    }
    return $false
}

function Enable-EmbedSitePackages([string]$EmbedDir) {
    $pth = Get-ChildItem $EmbedDir -Filter "python*._pth" | Select-Object -First 1
    if (-not $pth) { throw "Missing python._pth in embed package" }
    $lines = Get-Content $pth.FullName
    $updated = $lines | ForEach-Object {
        if ($_ -match '^#\s*import site') { 'import site' } else { $_ }
    }
    if ($updated -notcontains 'Lib\site-packages') {
        $updated += 'Lib\site-packages'
    }
    Set-Content -Path $pth.FullName -Value $updated -Encoding ASCII
}

function Try-EmbeddedPython310 {
    Write-Step "Fallback: portable Python $PythonVersion embed (inside runtime\, no system install)"
    $downloadDir = Join-Path $PortableRoot "workspace\asset_downloads"
    New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null
    $embedZip = Join-Path $downloadDir $EmbedName
    $embedDir = Join-Path $PortableRoot "runtime\python310-embed"

    if (-not (Test-Path $embedZip) -or (Get-Item $embedZip).Length -lt 5MB) {
        Invoke-WebRequest -Uri $EmbedUrl -OutFile $embedZip -UseBasicParsing
    }
    if (Test-Path $embedDir) { Remove-Item $embedDir -Recurse -Force }
    Expand-Archive -Path $embedZip -DestinationPath $embedDir -Force
    Enable-EmbedSitePackages $embedDir

    $python = Join-Path $embedDir "python.exe"
    if (-not (Test-Path $python)) { return $false }

    $getPip = Join-Path $downloadDir "get-pip.py"
    if (-not (Test-Path $getPip)) {
        Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getPip -UseBasicParsing
    }

    Write-Host "  Bootstrapping pip in embed Python ..."
    & $python $getPip --no-warn-script-location 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { return $false }

    & $python -m pip install --no-warn-script-location virtualenv 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { return $false }

    $venv = if ($MouseStudentOnly) {
        Join-Path $PortableRoot "workspace\student_venv"
    } else {
        Join-Path $PortableRoot "addons\face_puppeteer\venv"
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $venv -Parent) | Out-Null
    if (Test-Path $venv) { Remove-Item $venv -Recurse -Force }
    Write-Host "  Creating $venv from embed Python ..."
    & $python -m virtualenv $venv 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { return $false }

    $venvPython = Join-Path $venv "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) { return $false }

    @{ command = $venvPython; source = "embed" } | ConvertTo-Json | Set-Content -Path $MarkerFile -Encoding UTF8
    Write-Host "  Portable Python ready: $venvPython"
    return $true
}

if (Test-Python310Available) {
    Write-Host "Python 3.10/3.11 already available; skip installer."
    exit 0
}

$downloadDir = Join-Path $PortableRoot "workspace\asset_downloads"
New-Item -ItemType Directory -Force -Path $downloadDir | Out-Null

if (Try-WingetInstallPython310) {
    Write-Host "Python 3.10 installed via winget."
    exit 0
}

$installerPath = Join-Path $downloadDir $InstallerName
if (-not (Test-Path $installerPath) -or (Get-Item $installerPath).Length -lt 10MB) {
    Write-Step "Downloading Python $PythonVersion installer"
    Invoke-WebRequest -Uri $InstallerUrl -OutFile $installerPath -UseBasicParsing
}

if ((Test-Path $installerPath) -and (Try-ExeInstallerPython310 $installerPath)) {
    Write-Host "Python $PythonVersion installed via official installer."
    exit 0
}

if (Try-EmbeddedPython310) {
    $where = if ($MouseStudentOnly) { "workspace\student_venv" } else { "addons\face_puppeteer\venv" }
    Write-Host "Python $PythonVersion ready via portable embed ($where)."
    exit 0
}

throw @"
Could not install Python 3.10 for EasyVtuberStudio.

Tried: winget, official installer, portable embed inside runtime\.

Check network and disk space, then run DEPLOY.bat again.
"@
