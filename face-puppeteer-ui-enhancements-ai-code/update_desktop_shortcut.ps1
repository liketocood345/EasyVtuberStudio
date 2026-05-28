# Desktop shortcut for Load Preview puppeteer.
# Default: tha4fork-develop. Pass -PublishFork to point at E:\tha4fork instead.
param([switch]$PublishFork)

$shortcutPath = "C:\Users\WXH\Desktop\run_load_preview_puppeteer.bat - 快捷方式.lnk"

if ($PublishFork) {
    $batPath = "E:\tha4fork\run_load_preview_puppeteer.bat"
    $workDir = "E:\tha4fork"
    $description = "THA4 Load Preview (publish fork)"
} else {
    $batPath = "E:\tha4fork-develop\》》》》start《《《《.bat"
    $workDir = "E:\tha4fork-develop"
    $description = "THA4 Load Preview (tha4fork-develop)"
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
