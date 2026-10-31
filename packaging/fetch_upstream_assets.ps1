param([Parameter(Mandatory=$true)][string]$PortableRoot,[string[]]$PackageIds=@())
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
Initialize-LocalProcessEnvironment $PortableRoot
$python=Get-LocalPythonBase $PortableRoot
$mapping=@{mediapipe_task='mediapipe';openseeface='openseeface';tha3_models='tha3_models';tha4_teacher_training='tha4_training';ezvtb_nn_weights='output_enhancement'}
if(-not $PackageIds.Count) { $PackageIds=@('mediapipe_task','openseeface','tha3_models','tha4_teacher_training','ezvtb_nn_weights') }
$arguments=@('install','--root',$PortableRoot)
foreach($id in $PackageIds) {
    if(-not $mapping.ContainsKey($id)) { throw ('Unknown resource package: '+$id) }
    $arguments+=@('--module',$mapping[$id])
}
# bh-6 26.10.31 16:10 s
$fetchExit = Invoke-IsolatedPythonFile $python (Join-Path $PSScriptRoot 'resource_modules.py') $arguments
if(-not ($fetchExit -eq 0)) { throw 'Resource module download/integrity verification failed' }
# bh-6 26.10.31 16:10 e
& (Join-Path $PSScriptRoot 'reconcile_portable_layout.ps1') -PortableRoot $PortableRoot | Out-Null

# dep-007 / hotspot #6: do not leak robocopy 1 (successful copy) to callers.
exit 0
