param([Parameter(Mandatory=$true)][string]$PortableRoot)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'portable_environment.ps1')
# bh-6 26.10.31 02:56 s
$roles=@('app','face_puppeteer','tha3_models','basic_run')
try {
    $state=Get-Content -LiteralPath (Join-Path $PortableRoot 'workspace/load_preview_ui_state.json') -Raw | ConvertFrom-Json
    if($state.image_source_mode -eq 'tha3') { $roles=@('app','tha3_models','face_puppeteer','basic_run') }
} catch { }
foreach($role in $roles) {
    $binding=Get-ComponentRuntimeBinding $PortableRoot $role
    if(-not $binding) { continue }
    $python=Get-ComponentPythonExecutable $PortableRoot $role 'runtime/venvs/common/Scripts/python.exe'
    if(Test-LocalPython $PortableRoot $python) { Write-Output $python; exit 0 }
    throw "Explicit runtime binding is unusable: $python"
}
$order=@('runtime/venvs/common','addons/face_puppeteer/venv','workspace/student_venv','addons/tha3_models/venv')
foreach($relative in $order) {
    $python=Join-Path $PortableRoot ($relative+'/Scripts/python.exe')
    if(Test-LocalPython $PortableRoot $python) { Write-Output $python; exit 0 }
}
exit 1
# bh-6 26.10.31 02:56 e
