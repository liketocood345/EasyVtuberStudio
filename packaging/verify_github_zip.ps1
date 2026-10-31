param([Parameter(Mandatory=$true)][string]$PortableRoot,[switch]$Strict,[switch]$RequireRuntime)
$ErrorActionPreference='Stop'
if($RequireRuntime) { throw 'This verifier accepts CORE only; use verify_full_install.ps1 for installed trees.' }
$PortableRoot=[IO.Path]::GetFullPath($PortableRoot).TrimEnd('\')
$inventory=Get-Content -LiteralPath (Join-Path $PortableRoot 'core-files.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$expected=@{}
foreach($item in $inventory.files) {
    $full=[IO.Path]::GetFullPath((Join-Path $PortableRoot $item.path))
    if(-not $full.StartsWith($PortableRoot+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'CORE inventory escaped root' }
    if(-not(Test-Path -LiteralPath $full -PathType Leaf)) { throw ('Missing CORE file: '+$item.path) }
    if((Get-Item -LiteralPath $full).Length -ne $item.size_bytes -or (Get-FileHash -LiteralPath $full -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.sha256) { throw ('CORE hash mismatch: '+$item.path) }
    if($item.path -match '(^|/)\.git($|/)|^(runtime|plans|record)/|^addons/(?!README.md$|.gitkeep$)|(^|/)(_internal|site-packages|__pycache__|his)/|\.(whl|nupkg|onnx|pyc|pem|jsonl)$') { throw ('Forbidden CORE item: '+$item.path) }
    $expected[$full]=$true
}
$actual=@(Get-ChildItem -LiteralPath $PortableRoot -Recurse -File -Force)
if($actual.Count -ne $expected.Count+1) { throw 'Unexpected or missing CORE files' }
foreach($file in $actual) { if(-not $expected.ContainsKey($file.FullName) -and $file.FullName -ne (Join-Path $PortableRoot 'core-files.json')) { throw ('Unexpected file: '+$file.FullName) } }
foreach($rel in @('EasyVtuberStudio.exe','DEPLOY.bat','workspace/load_preview_ui_state.json','workspace/basic_layers/manifest.json','data/character_models/baiten_from_project_forlon9/bai_450k/parts/beitou.gif')) {
    if(-not(Test-Path -LiteralPath (Join-Path $PortableRoot $rel))) { throw ('CORE material missing: '+$rel) }
}
$state=Get-Content -LiteralPath (Join-Path $PortableRoot 'workspace/load_preview_ui_state.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if($state.mouth_settings.mouth_input_mode -ne 'mouse' -or $state.image_source_mode -ne 'tha4_student' -or $state.PSObject.Properties['window_capture_hwnd'] -or $state.PSObject.Properties['controls_frame_y']) { throw 'Unsanitized seed memory' }
Write-Host ('CORE verification passed without Python: '+$expected.Count+' files')
exit 0
