# Optional: junction EasyVtuber vendor assets into this repo (no large file copies).
# Usage:
#   powershell -ExecutionPolicy Bypass -File setup_tha3_vendor.ps1 -EasyVtuberRoot "F:\EasyVtuber\..."
param(
    [string]$RepoRoot = "",
    [string]$EasyVtuberRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) {
    $RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
} else {
    $RepoRoot = (Resolve-Path $RepoRoot).Path
}

if (-not $EasyVtuberRoot) {
    Write-Host "Pass -EasyVtuberRoot to the extracted EasyVtuber folder (contains tha3/, data/, etc.)."
    Write-Host "Repo root: $RepoRoot"
    exit 1
}
$EasyVtuberRoot = (Resolve-Path $EasyVtuberRoot).Path

$VendorRoot = Join-Path $RepoRoot "vendor\easyvtuber"
$Links = @(
    @{ Name = "tha3"; Target = Join-Path $EasyVtuberRoot "tha3" },
    @{ Name = "ezvtuber-rt"; Target = Join-Path $EasyVtuberRoot "ezvtuber-rt" },
    @{ Name = "data_models"; Target = Join-Path $EasyVtuberRoot "data\models" },
    @{ Name = "data_images"; Target = Join-Path $EasyVtuberRoot "data\images" }
)

New-Item -ItemType Directory -Force -Path $VendorRoot | Out-Null

function Ensure-Junction($LinkPath, $TargetPath) {
    if (-not (Test-Path $TargetPath)) {
        Write-Warning "Skip missing target: $TargetPath"
        return
    }
    if (Test-Path $LinkPath) {
        $item = Get-Item $LinkPath -Force
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
            Write-Host "OK (exists): $LinkPath"
            return
        }
        throw "Path exists and is not a junction: $LinkPath"
    }
    cmd /c mklink /J "$LinkPath" "$TargetPath" | Out-Null
    Write-Host "Linked: $LinkPath -> $TargetPath"
}

foreach ($entry in $Links) {
    Ensure-Junction (Join-Path $VendorRoot $entry.Name) $entry.Target
}

Write-Host "THA3 vendor junctions ready under $VendorRoot"
