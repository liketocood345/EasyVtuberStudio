# Quick check for stale path references after repo layout change.
# Usage: powershell -File scripts\maint\verify_path_refs.ps1

$ErrorActionPreference = "Continue"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$patterns = @(
    @{ Name = "root start bat only"; Pattern = '(?<![\\/])》》》》start《《《《\.bat' },
    @{ Name = "root run_load_preview"; Pattern = '(?<![\\/])run_load_preview_puppeteer\.bat' },
    @{ Name = "root THA4_DownloadAssets"; Pattern = '(?<![\\/])THA4_DownloadAssets\.bat' },
    @{ Name = "root THA4Train exe"; Pattern = '(?<![\\/])THA4Train\.exe' },
    @{ Name = "root assets_manifest"; Pattern = '(?<![\\/])assets_manifest\.json' },
    @{ Name = "broken docs link"; Pattern = '\]\(docs/DOC_INDEX\.md\)' },
    @{ Name = "root HANDOVER link"; Pattern = '\]\(\.\./HANDOVER\.md\)' },
    @{ Name = "legacy demo venv path"; Pattern = 'talking-head-anime-4-demo\\venv' },
    @{ Name = "THA4_bundle_bai_custom"; Pattern = 'THA4_bundle_bai_custom' },
    @{ Name = "THA4_bundle root"; Pattern = 'E:\\THA4_bundle[^_]' },
    @{ Name = "external F drive EasyVtuber"; Pattern = 'F:\\EasyVtuber' }
)
$exclude = @("\venv\", "\.git\", "\his\", "\packaging\launcher\build\", "verify_path_refs.ps1", "restructure_repo.ps1", "REPO_LAYOUT.plan.md", "oid.md", "SOFTWARE_REQUIREMENTS", "\docs\training\", "migrate_from_bai_custom.ps1", "sync_plans_from_bai_custom.ps1", "\docs\", "\plans\", "README.md", "HANDOVER.md", "TROUBLESHOOTING", "BACKUP.md", "PACKAGING_README", "TRAINING_NOTES", "reset_fork_fresh_extract.ps1", "README_PORTABLE.txt", "restore_develop_full_install.ps1", "setup_portable_runtime.ps1", "data\character_models\baiten")
$files = Get-ChildItem $root -Recurse -File -Include *.md,*.bat,*.ps1,*.py,*.txt -ErrorAction SilentlyContinue |
    Where-Object {
        $p = $_.FullName
        -not ($exclude | Where-Object { $p -like "*$_*" })
    }

$issues = @()
foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
    if (-not $content) { continue }
    foreach ($pat in $patterns) {
        if ($content -match $pat.Pattern) {
            $issues += [PSCustomObject]@{ File = $file.FullName.Substring($root.Length + 1); Issue = $pat.Name }
        }
    }
}

if ($issues.Count -eq 0) {
    Write-Host "No stale path patterns found."
    exit 0
}

$issues | Sort-Object File, Issue | Format-Table -AutoSize
Write-Host "Found $($issues.Count) potential stale reference(s)."
exit 1
