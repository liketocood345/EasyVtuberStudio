# Manual THA4 student packager for bai (custom body schedule).
# Usage:
#   .\package_bai_student.ps1 -Dest "E:\bai_try" -BodyCheckpoint "0045"
#   .\package_bai_student.ps1 -BodyCheckpoint "0080"   # after 800k train
param(
    [string]$Dest = "E:\bai_try",
    [string]$TrainPrefix = "E:\THA4_bundle\distill_outputs\bai",
    [string]$RepoRoot = "E:\THA4_bundle_bai_custom\talking-head-anime-4-demo",
    [string]$FaceCheckpoint = "0010",
    [string]$BodyCheckpoint = "0045"
)

$ErrorActionPreference = "Stop"
$cm = Join-Path $Dest "character_model"
New-Item -ItemType Directory -Force -Path $cm | Out-Null

$facePt = Join-Path $TrainPrefix "face_morpher\checkpoint\$FaceCheckpoint\module_module.pt"
$bodyPt = Join-Path $TrainPrefix "body_morpher\checkpoint\$BodyCheckpoint\module_module.pt"
$charPng = Join-Path $RepoRoot "data\images\bai.png"

foreach ($p in @($facePt, $bodyPt, $charPng)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "Missing: $p" }
}

Copy-Item -LiteralPath $facePt -Destination (Join-Path $cm "face_morpher.pt") -Force
Copy-Item -LiteralPath $bodyPt -Destination (Join-Path $cm "body_morpher.pt") -Force
Copy-Item -LiteralPath $charPng -Destination (Join-Path $cm "character.png") -Force

@"
character_image_file_name: character.png
face_morpher_file_name: face_morpher.pt
body_morpher_file_name: body_morpher.pt
"@ | Set-Content -LiteralPath (Join-Path $cm "character_model.yaml") -Encoding utf8 -NoNewline
Add-Content -LiteralPath (Join-Path $cm "character_model.yaml") -Value "" -Encoding utf8

$manifest = @(
    "Packaged: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')",
    "Dest: $Dest",
    "Train prefix: $TrainPrefix",
    "face_morpher.pt <= face_morpher/checkpoint/$FaceCheckpoint/module_module.pt",
    "body_morpher.pt <= body_morpher/checkpoint/$BodyCheckpoint/module_module.pt",
    "character.png <= data/images/bai.png",
    "",
    "Load in demo:",
    "  cd $RepoRoot",
    "  bin\run.bat src\tha4\app\character_model_manual_poser.py",
    "  -> Load Model -> $cm\character_model.yaml",
    "",
    "Custom schedule milestones: 0045=450k eval, 0080=800k final."
)
$manifest | Set-Content -LiteralPath (Join-Path $Dest "PACKAGING_README.txt") -Encoding utf8

Write-Host "Student packaged to $cm"
Get-ChildItem $cm | Format-Table Name, Length
