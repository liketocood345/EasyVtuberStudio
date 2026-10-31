param([string]$RepoRoot=(Split-Path $PSScriptRoot -Parent),[switch]$TeacherOnly,[switch]$MainAndCompatOnly)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
$RepoRoot=[IO.Path]::GetFullPath($RepoRoot).TrimEnd('\')
$compiler=Join-Path $env:SystemRoot 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
if(-not(Test-Path -LiteralPath $compiler)) { throw 'Windows .NET Framework C# compiler is required to build native thin entries.' }
$template=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'launcher/FolderPythonLauncher.cs') -Raw -Encoding UTF8
$build=Assert-LocalChild $RepoRoot (Join-Path $RepoRoot 'workspace/cache/native-launcher-build')
New-Item -ItemType Directory -Force -Path $build | Out-Null
$entries=@()
if(-not $TeacherOnly) {
    $entries+=@{name='EasyVtuberStudio';target='EasyVtuberStudio.exe';script='packaging/launcher/launch_face_puppeteer.py'}
    $entries+=@{name='THA4Train-compat';target='scripts/launch/THA4Train.exe';script='packaging/launcher/launch_tha4train.py'}
}
if(-not $MainAndCompatOnly) {
    $entries+=@{name='THA4Train';target='addons/tha4_training/THA4Train.exe';script='addons/tha4_training/launcher.py'}
}
foreach($entry in $entries) {
    $source=Join-Path $build ($entry.name+'.cs')
    $target=Assert-LocalChild $RepoRoot (Join-Path $RepoRoot $entry.target)
    $template.Replace('__SCRIPT_REL__',$entry.script) | Set-Content -LiteralPath $source -Encoding UTF8
    New-Item -ItemType Directory -Force -Path (Split-Path $target -Parent) | Out-Null
    $arguments=@('/nologo','/target:winexe','/platform:x64','/optimize+','/reference:System.Windows.Forms.dll',('/out:'+$target))
    $icon=Join-Path $RepoRoot 'assets/branding/app-icon-source.ico'
    if(Test-Path -LiteralPath $icon) { $arguments+=('/win32icon:'+$icon) }
    & $compiler @arguments $source
    if($LASTEXITCODE -ne 0) { throw ('Native entry compilation failed: '+$entry.name) }
    if((Get-Item -LiteralPath $target).Length -gt 2MB) { throw ('Unexpected non-thin entry size: '+$target) }
    Write-Host ('Built native entry: '+$target+' ('+(Get-Item -LiteralPath $target).Length+' bytes)')
}
