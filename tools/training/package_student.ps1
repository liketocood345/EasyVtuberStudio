param(
    [string]$Dest = "",
    [string]$TrainPrefix = "",
    [string]$RepoRoot = "",
    [string]$FaceCheckpoint = "0010",
    [string]$BodyCheckpoint = "0045"
)

$ErrorActionPreference = "Stop"
$PortableRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
if ([string]::IsNullOrWhiteSpace($RepoRoot)) {
    $RepoRoot = Join-Path $PortableRoot "face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
}
if ([string]::IsNullOrWhiteSpace($TrainPrefix)) {
    $TrainPrefix = Join-Path $PortableRoot "workspace\distill_outputs\bai"
}
if ([string]::IsNullOrWhiteSpace($Dest)) {
    $Dest = Join-Path $PortableRoot "workspace\distill_outputs\packaged_student"
}

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

Write-Host "Student packaged to $cm"
Get-ChildItem $cm | Format-Table Name, Length
