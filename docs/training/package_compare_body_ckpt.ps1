# Pack face 0010 + several body checkpoints for A/B eye comparison in puppeteer.
param(
    [string]$BaseDest = "E:\bai_body_compare",
    [string]$TrainPrefix = "E:\THA4_bundle\distill_outputs\bai",
    [string]$RepoRoot = "E:\THA4_bundle_bai_custom\talking-head-anime-4-demo",
    [string[]]$BodyCheckpoints = @("0001", "0002", "0003", "0045", "0080")
)

$ErrorActionPreference = "Stop"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($ck in $BodyCheckpoints) {
    $dest = Join-Path $BaseDest "body_$ck"
    & (Join-Path $scriptDir "package_bai_student.ps1") -Dest $dest -TrainPrefix $TrainPrefix `
        -RepoRoot $RepoRoot -FaceCheckpoint "0010" -BodyCheckpoint $ck
}
Write-Host "Compare folders under $BaseDest"
