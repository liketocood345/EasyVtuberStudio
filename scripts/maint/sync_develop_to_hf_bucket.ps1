# No full-tree mirror. Default is a local verified plan; -Publish is explicit.
param([string]$MirrorRoot='', [string]$BucketId='liketocode789/EasyVtuberStudio', [switch]$DryRun, [switch]$Publish)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
. (Join-Path $root 'packaging/portable_environment.ps1')
Initialize-LocalProcessEnvironment $root
if(-not $MirrorRoot) { $MirrorRoot=Join-Path $root 'workspace/release/hf-stage' }
$python=Join-Path $root 'runtime/python310/python.exe'
if(-not(Test-LocalPython $root $python)) { throw 'Folder-local Python required' }
$arguments=@('--root',$root,'--stage',$MirrorRoot,'--bucket',$BucketId)
if($Publish -and -not $DryRun) {
    [void](Get-LocalDownloadPython $root)
    $arguments+='--publish'
}
& $python -I (Join-Path $root 'packaging/hf_release.py') @arguments
if($LASTEXITCODE -ne 0) { throw 'HF ark inventory/upload failed' }
