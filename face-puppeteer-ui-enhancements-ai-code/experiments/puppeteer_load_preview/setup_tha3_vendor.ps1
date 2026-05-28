# Junction THA3 / EasyVtuber model assets into bai_custom (no large file copies).
$ErrorActionPreference = "Stop"
$EzRoot = "F:\EasyVtuber\EasyVtuber_v0.8.1\EasyVtuber_v0.8.1"
$BundleRoot = "E:\THA4_bundle_bai_custom"
$VendorRoot = Join-Path $BundleRoot "vendor\easyvtuber"
$Links = @(
    @{ Name = "tha3"; Target = Join-Path $EzRoot "tha3" },
    @{ Name = "ezvtuber-rt"; Target = Join-Path $EzRoot "ezvtuber-rt" },
    @{ Name = "data_models"; Target = Join-Path $EzRoot "data\models" },
    @{ Name = "data_images"; Target = Join-Path $EzRoot "data\images" }
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
