# Move fork root (except his/.git/keep list) into his/yyyy-MM-dd_HH-mm-ss/
param(
    [switch]$SyncFromBaiCustom
)

$ErrorActionPreference = "Stop"
$fork = $PSScriptRoot
$stamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$dest = Join-Path $fork "his\$stamp"

# Never archive these names from root
$skip = @("his", ".git")
# Stay at fork root after archive (docs + tooling)
$keepInRoot = @(
    "BACKUP.md",
    "archive_to_his.ps1",
    "sync_from_bai_custom.ps1"
)

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Write-Host "Archive destination: $dest"

Get-ChildItem -LiteralPath $fork -Force | ForEach-Object {
    $name = $_.Name
    if ($skip -contains $name) { return }
    if ($keepInRoot -contains $name) { return }
    Move-Item -LiteralPath $_.FullName -Destination $dest -Force
    Write-Host "Moved: $name"
}

$snapshotReadme = @"
# Snapshot ``$stamp``

Archived from fork root at **$stamp** (local time).

See [BACKUP.md](../../BACKUP.md) for restore and naming rules.
"@
Set-Content -LiteralPath (Join-Path $dest "CHANGELOG_SNAPSHOT.md") -Value $snapshotReadme -Encoding UTF8

# Refresh his index line hint
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Add a row to his/README.md for: his/$stamp/"
Write-Host "  2. Update CHANGELOG.md if this release has new features"
if ($SyncFromBaiCustom) {
    $sync = Join-Path $fork "sync_from_bai_custom.ps1"
    if (Test-Path $sync) {
        & $sync
    } else {
        Write-Warning "sync_from_bai_custom.ps1 not found"
    }
} else {
    Write-Host "  3. Copy new version from bai_custom or run: archive_to_his.ps1 -SyncFromBaiCustom"
}
Write-Host "Done."
