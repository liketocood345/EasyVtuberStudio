# Deprecated: use repo-bundled deps/tha3 instead of vendor junctions.
$ErrorActionPreference = "Stop"
$RepoRoot = $null
foreach ($rel in @("..\..\..", "..\..", "..\..\..\..")) {
    $candidate = (Resolve-Path (Join-Path $PSScriptRoot $rel) -ErrorAction SilentlyContinue)
    if ($candidate -and (Test-Path (Join-Path $candidate "deps\tha3\populate_tha3_bundle.ps1"))) {
        $RepoRoot = $candidate.Path
        break
    }
}
$Populate = Join-Path $RepoRoot "deps\tha3\populate_tha3_bundle.ps1"
if (-not $RepoRoot -or -not (Test-Path $Populate)) {
    throw "Cannot find deps\tha3\populate_tha3_bundle.ps1 under repo root."
}
Write-Host "Forwarding to bundled THA3 populate script..."
& $Populate @args
