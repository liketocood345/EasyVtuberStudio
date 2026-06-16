param(
    [string]$MirrorRoot = "",
    [string]$BucketId = "liketocode789/EasyVtuberStudio",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Back-compat alias
if ([string]::IsNullOrWhiteSpace($MirrorRoot) -and $PSBoundParameters.ContainsKey("DevelopRoot")) {
    $MirrorRoot = $DevelopRoot
}

if ([string]::IsNullOrWhiteSpace($MirrorRoot)) {
    $hfMirror = "E:\EasyVtuberStudio-hf"
    if (Test-Path $hfMirror) {
        $MirrorRoot = $hfMirror
    } else {
        $MirrorRoot = (Join-Path $PSScriptRoot "..\..")
    }
}
$MirrorRoot = (Resolve-Path $MirrorRoot).Path

function Get-HfCliArgs {
    param([string[]]$SubArgs)
    return @("-m", "huggingface_hub.cli.hf") + $SubArgs
}

function Invoke-HfCli {
    param([string[]]$CliArgs)
    $all = Get-HfCliArgs $CliArgs
    & python @all
    if ($LASTEXITCODE -ne 0) {
        throw "hf command failed (exit $LASTEXITCODE): hf $($CliArgs -join ' ')"
    }
}

Write-Host ""
Write-Host "=== Sync local mirror -> HF Bucket ==="
Write-Host "Source : $MirrorRoot"
Write-Host "Bucket : hf://buckets/$BucketId"
Write-Host "Docs   : docs/HF_BUCKET_MIRROR.md (upload checklist)"
Write-Host ""

$sum = (Get-ChildItem $MirrorRoot -Recurse -File -ErrorAction SilentlyContinue |
    Measure-Object -Property Length -Sum).Sum
Write-Host ("Local size: {0:N2} GB ({1:N0} bytes)" -f ($sum / 1GB), $sum)
Write-Host "Tip: use E:\EasyVtuberStudio-hf copied from main; do not sync full develop (~12 GB)."
Write-Host ""

try {
    Invoke-HfCli @("auth", "whoami") | Out-Host
} catch {
    throw @"
Not logged in to Hugging Face. Run:
  powershell -ExecutionPolicy Bypass -File scripts\maint\hf_login_from_file.ps1 -TokenFile <path-to-utf8-token.txt>
Or: python -m huggingface_hub.cli.hf auth login --token <hf_...>
See docs/HF_BUCKET_MIRROR.md if you see Illegal header value Bearer \x00...
"@
}

$syncArgs = @(
    "buckets", "sync",
    $MirrorRoot,
    "hf://buckets/$BucketId",
    "--exclude", ".git/**"
)

if ($DryRun) {
    $syncArgs += "--dry-run"
}

Write-Host "Running: python -m huggingface_hub.cli.hf $($syncArgs -join ' ')"
Invoke-HfCli $syncArgs

Write-Host ""
Write-Host "Sync complete."
if ($DryRun) {
    Write-Host "Dry-run only; re-run without -DryRun to upload."
}
