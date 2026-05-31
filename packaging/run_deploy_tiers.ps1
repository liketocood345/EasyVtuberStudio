param(
    [Parameter(Mandatory = $true)]
    [string]$PortableRoot,
    [string[]]$PackageIds = @("mouse_student", "face_puppeteer", "tha3_models")
)

$script = Join-Path $PSScriptRoot "deploy_portable.ps1"
& $script -PortableRoot $PortableRoot -PackageIds $PackageIds -Confirmed
exit $LASTEXITCODE
