# Desktop shortcut for Load Preview puppeteer.
# Default: active dev (bai_custom). Pass -Fork to point at fork repo instead.
param([switch]$Fork)

$shortcutPath = "C:\Users\WXH\Desktop\run_load_preview_puppeteer.bat - 快捷方式.lnk"

if ($Fork) {
    $batPath = "E:\tha4fork\run_load_preview_puppeteer.bat"
    $workDir = "E:\tha4fork"
    $description = "THA4 Load Preview (fork)"
} else {
    $batPath = "E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat"
    $workDir = "E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview"
    $description = "THA4 Load Preview (bai_custom active dev)"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $batPath
$shortcut.WorkingDirectory = $workDir
$shortcut.Arguments = ""
$shortcut.Description = $description
$shortcut.Save()

Write-Host "Shortcut updated:"
Write-Host "  Target: $($shortcut.TargetPath)"
Write-Host "  WorkDir: $($shortcut.WorkingDirectory)"
