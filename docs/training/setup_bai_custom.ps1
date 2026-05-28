# Recreate THA4_bundle_bai_custom: copy src, junction large assets to THA4_bundle.
$ErrorActionPreference = "Stop"
$orig = "E:\THA4_bundle\talking-head-anime-4-demo"
$demo = "E:\THA4_bundle_bai_custom\talking-head-anime-4-demo"
$bundle = "E:\THA4_bundle_bai_custom"

New-Item -ItemType Directory -Force -Path $bundle | Out-Null
New-Item -ItemType Directory -Force -Path $demo | Out-Null

$copyItems = @("src", "bin", "poetry", "docs", "distiller-ui-doc", ".python-version", ".gitignore", "README.md", "LICENSE")
foreach ($item in $copyItems) {
    $srcPath = Join-Path $orig $item
    if (Test-Path $srcPath) {
        robocopy $srcPath (Join-Path $demo $item) /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    }
}

function Remove-Link([string]$Link) {
    if (-not (Test-Path $Link)) { return }
    $item = Get-Item $Link -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        if ($item.Attributes -band [IO.FileAttributes]::Directory) {
            cmd /c "rmdir `"$Link`"" | Out-Null
        } else {
            Remove-Item $Link -Force
        }
    }
}

function Ensure-DirJunction([string]$Link, [string]$Target) {
    Remove-Link $Link
    cmd /c "mklink /J `"$Link`" `"$Target`"" | Out-Null
}

function Ensure-FileHardLink([string]$Link, [string]$Target) {
    Remove-Link $Link
    cmd /c "mklink /H `"$Link`" `"$Target`"" | Out-Null
}

Ensure-DirJunction (Join-Path $demo "venv") (Join-Path $orig "venv")
$dataDemo = Join-Path $demo "data"
New-Item -ItemType Directory -Force -Path $dataDemo | Out-Null
foreach ($name in @("tha4", "images", "thirdparty", "character_models", "distill_examples")) {
    Ensure-DirJunction (Join-Path $dataDemo $name) (Join-Path (Join-Path $orig "data") $name)
}
Ensure-FileHardLink (Join-Path $dataDemo "pose_dataset.pt") (Join-Path (Join-Path $orig "data") "pose_dataset.pt")

$outBundle = Join-Path $bundle "distill_outputs"
New-Item -ItemType Directory -Force -Path $outBundle | Out-Null
Ensure-DirJunction (Join-Path $outBundle "bai") "E:\THA4_bundle\distill_outputs\bai"

$patch = Join-Path $bundle "patches\distiller_config.py"
if (Test-Path $patch) {
    Copy-Item $patch (Join-Path $demo "src\tha4\distiller\distiller_config.py") -Force
    Write-Host "Applied patches\distiller_config.py"
}
Write-Host "Done: $bundle"
