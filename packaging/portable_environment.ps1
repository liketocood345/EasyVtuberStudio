# dep-007: install only inside the selected portable folder, never in the OS.
$ErrorActionPreference='Stop'
function Get-ComponentRuntimeBinding([string]$Root,[string]$Component) {
    $path=Join-Path $Root 'runtime/bindings/components.json'
    if(-not(Test-Path -LiteralPath $path)) { return $null }
    $config=Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
    $property=$config.components.PSObject.Properties[$Component]
    if($null -eq $property) { return $null }
    $binding=$property.Value
    if(-not $binding.python) { throw "Missing Python in component binding: $Component" }
    [void](Assert-LocalChild $Root (Join-Path $Root $binding.python))
    return $binding
}
function Get-ComponentPythonExecutable([string]$Root,[string]$Component,[string]$DefaultRelative) {
    $binding=Get-ComponentRuntimeBinding $Root $Component
    $relative=if($binding) { [string]$binding.python } else { $DefaultRelative }
    return Assert-LocalChild $Root (Join-Path $Root $relative)
}
function Assert-LocalChild([string]$Root,[string]$Path) {
    $rootPath=[IO.Path]::GetFullPath($Root).TrimEnd('\','/')
    $target=[IO.Path]::GetFullPath($Path)
    if(-not $target.StartsWith($rootPath+'\',[StringComparison]::OrdinalIgnoreCase)) { throw "Path escapes portable folder: $target" }
    return $target
}
function Initialize-LocalProcessEnvironment([string]$Root) {
    $env:PYTHONNOUSERSITE='1'; $env:PIP_CONFIG_FILE='NUL'; $env:PIP_REQUIRE_VIRTUALENV='true'; $env:PIP_DISABLE_PIP_VERSION_CHECK='1'
    foreach($key in @('PYTHONHOME','PYTHONPATH','PIP_TARGET','PIP_PREFIX','PIP_USER')) { Remove-Item ('Env:'+$key) -ErrorAction SilentlyContinue }
    foreach($key in @('TEMP','TMP','PIP_CACHE_DIR','TORCH_HOME','MPLCONFIGDIR','HF_HOME','CUDA_CACHE_PATH','NUMBA_CACHE_DIR','APPDATA','LOCALAPPDATA','XDG_CACHE_HOME')) {
        $path=Assert-LocalChild $Root (Join-Path $Root ('workspace/cache/'+$key.ToLowerInvariant()))
        New-Item -ItemType Directory -Force -Path $path | Out-Null
        [Environment]::SetEnvironmentVariable($key,$path,'Process')
    }
    $env:THA4_PORTABLE_ROOT=[IO.Path]::GetFullPath($Root)
}
function Test-LocalPython([string]$Root,[string]$Python) {
    if(-not(Test-Path -LiteralPath $Python)) { return $false }
    # Windows PowerShell 5.1 promotes redirected native stderr to an error under
    # Stop. A rejected old venv must return false so deployment can repair it.
    $previousPreference=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $Python -I -c 'import pathlib,sys; r=pathlib.Path(sys.argv[1]).resolve(); assert all(pathlib.Path(p).resolve().is_relative_to(r) for p in (sys.executable,sys.prefix,sys.base_prefix))' $Root 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    } finally { $ErrorActionPreference=$previousPreference }
}
function Get-LocalPythonBase([string]$Root) {
    Initialize-LocalProcessEnvironment $Root
    $base=Assert-LocalChild $Root (Join-Path $Root 'runtime/python310')
    $python=Join-Path $base 'python.exe'
    if(Test-LocalPython $Root $python) { return $python }
    $cache=Join-Path $Root 'workspace/asset_downloads'
    New-Item -ItemType Directory -Force -Path $cache | Out-Null
    $archive=Join-Path $cache 'python.3.10.11.nupkg'
    if(-not(Test-Path -LiteralPath $archive)) {
        [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri 'https://api.nuget.org/v3-flatcontainer/python/3.10.11/python.3.10.11.nupkg' -OutFile ($archive+'.part')
        Move-Item -LiteralPath ($archive+'.part') -Destination $archive -Force
    }
    $expected='7c6f99b160a36a7e09492dfcff2b0a3a60bb5229ca44cdcc3ecb32871a6144d0'
    if((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) { throw 'Python base archive hash mismatch; invalid cache retained for inspection' }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $stage=Assert-LocalChild $Root (Join-Path $Root ('runtime/extract-'+[Guid]::NewGuid().ToString('N')))
    [IO.Compression.ZipFile]::ExtractToDirectory($archive,$stage)
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    Copy-Item -Path (Join-Path $stage 'tools/*') -Destination $base -Recurse -Force
    $stage=Assert-LocalChild $Root $stage
    Remove-Item -LiteralPath $stage -Recurse -Force
    if(-not(Test-LocalPython $Root $python)) { throw 'Application-local Python failed validation' }
    return $python
}
function New-LocalPythonEnvironment([string]$Root,[string]$Relative,[switch]$Force) {
    $base=Get-LocalPythonBase $Root
    $target=Assert-LocalChild $Root (Join-Path $Root $Relative)
    $python=Join-Path $target 'Scripts/python.exe'
    if(-not $Force -and (Test-LocalPython $Root $python)) { return $python }
    if(Test-Path -LiteralPath $target) {
        $active=@(Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -and $_.ExecutablePath.StartsWith($target+'\',[StringComparison]::OrdinalIgnoreCase) })
        if($active.Count) { throw "Close the application before repairing $target" }
        if((Get-Item -LiteralPath $target -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked environment cannot be overwritten: $target" }
        $backup=Assert-LocalChild $Root ($target+'.before-local-'+[Guid]::NewGuid().ToString('N'))
        Move-Item -LiteralPath $target -Destination $backup
    }
    & $base -I -m venv $target
    if($LASTEXITCODE -ne 0 -or -not(Test-LocalPython $Root $python)) { throw "Local environment creation failed: $target" }
    return $python
}
function Install-LocalRequirements([string]$Root,[string]$Python,[string]$Requirements) {
    Initialize-LocalProcessEnvironment $Root
    if(-not(Test-LocalPython $Root $Python)) { throw "External Python rejected: $Python" }
    if((Get-Content -LiteralPath $Requirements -Raw) -match '\.whl#sha256=') {
        $cached=Join-Path $Root ('workspace/asset_downloads/'+[IO.Path]::GetFileName($Requirements))
        & $Python -I (Join-Path $PSScriptRoot 'fetch_verified_wheels.py') --root $Root --requirements $Requirements --output $cached
        if($LASTEXITCODE -ne 0) { throw "Verified wheel download failed: $Requirements" }
        $Requirements=$cached
    }
    $previousPreference=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $Python -I -m pip install --require-virtualenv --prefer-binary --progress-bar off --timeout 30 --retries 3 -c (Join-Path $Root 'deps/pip/constraints.txt') -r $Requirements
        $installExit=$LASTEXITCODE
    } finally { $ErrorActionPreference=$previousPreference }
    if($installExit -ne 0) { throw "Dependency installation failed: $Requirements (exit=$installExit)" }
}
function Get-LocalDownloadPython([string]$Root) {
    $python=New-LocalPythonEnvironment $Root 'runtime/download_venv'
    $previousPreference=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $python -I -c 'import huggingface_hub' 2>$null | Out-Null
        $clientReady=$LASTEXITCODE -eq 0
    } finally { $ErrorActionPreference=$previousPreference }
    if(-not $clientReady) {
        & $python -I -m pip install --require-virtualenv 'huggingface_hub==2.2.0' | Out-Host
        if($LASTEXITCODE -ne 0) { throw 'Cannot prepare folder-local Bucket download client' }
    }
    return $python
}

function Install-LockedRuntime([string]$Root,[string]$Python,[string[]]$Profiles) {
    Initialize-LocalProcessEnvironment $Root
    if(-not(Test-LocalPython $Root $Python)) { throw 'External runtime rejected' }
    $arguments=@('--root',$Root,'--python',$Python)
    foreach($profile in $Profiles) { $arguments+=@('--profile',$profile) }
    & $Python -I (Join-Path $PSScriptRoot 'locked_runtime.py') @arguments
    if($LASTEXITCODE -ne 0) { throw 'Hash-locked runtime install failed' }
}
function Set-CommonRuntimeBindings([string]$Root,[string[]]$Roles=@('app','basic_run','face_puppeteer','tha3_models','tha4_training')) {
    $path=Join-Path $Root 'runtime/bindings/components.json'
    if(Test-Path -LiteralPath $path) { $config=Get-Content -LiteralPath $path -Raw | ConvertFrom-Json }
    else { $config=[pscustomobject]@{schema_version=1;stage='locked-common';components=[pscustomobject]@{}} }
    foreach($role in $Roles) {
        # Preserve explicitly configured, tested private bindings.
        if(-not $config.components.PSObject.Properties[$role]) {
            $config.components | Add-Member -NotePropertyName $role -NotePropertyValue ([pscustomobject]@{python='runtime/venvs/common/Scripts/python.exe';base='runtime/python310'})
        }
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $path -Parent) | Out-Null
    $config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $path -Encoding UTF8
}
