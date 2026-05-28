# One-time migration: copy valuable docs and code from E:\THA4_bundle_bai_custom into this repo.
# Safe to re-run; skips missing source if bai_custom already deleted.
$ErrorActionPreference = "Stop"
$Src = "E:\THA4_bundle_bai_custom"
$Repo = $PSScriptRoot
$Bundle = Join-Path $Repo "face-puppeteer-ui-enhancements-ai-code"
$Exp = Join-Path $Bundle "experiments\puppeteer_load_preview"
$Demo = Join-Path $Bundle "talking-head-anime-4-demo"

if (-not (Test-Path $Src)) {
    Write-Warning "Source $Src not found — skip file copy (docs may already be in repo)."
} else {
    $copyPairs = @(
        @("$Src\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py", "$Exp\character_model_mediapipe_puppeteer_load_preview.py"),
        @("$Src\experiments\puppeteer_load_preview\smoke_load_preview.py", "$Exp\smoke_load_preview.py"),
        @("$Src\experiments\puppeteer_load_preview\smoke_tha3_preview.py", "$Exp\smoke_tha3_preview.py"),
        @("$Src\experiments\puppeteer_load_preview\README.txt", "$Exp\README.txt"),
        @("$Src\experiments\puppeteer_load_preview\THA3_INTEGRATION.md", "$Exp\THA3_INTEGRATION.md"),
        @("$Src\experiments\puppeteer_load_preview\verify_periodic_calibration.py", "$Exp\verify_periodic_calibration.py"),
        @("$Src\talking-head-anime-4-demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py", "$Demo\src\tha4\mocap\mediapipe_face_pose_converter_00.py"),
        @("$Src\HANDOVER.md", "$Repo\plans\_HANDOVER_source_snapshot.md"),
        @("$Src\layer-runtime-replan_3a393fc1.plan.md", "$Repo\plans\layer-runtime-replan_3a393fc1.plan.md")
    )
    foreach ($p in $copyPairs) {
        if (-not (Test-Path $p[0])) { Write-Warning "Skip: $($p[0])"; continue }
        $dir = Split-Path $p[1] -Parent
        if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
        Copy-Item -LiteralPath $p[0] -Destination $p[1] -Force
        Write-Host "OK $($p[0])"
    }
    $dirs = @("image_sources", "deps")
    foreach ($d in $dirs) {
        $from = Join-Path "$Src\experiments\puppeteer_load_preview" $d
        $to = Join-Path $Exp $d
        if (Test-Path $from) {
            Copy-Item -Path "$from\*" -Destination $to -Recurse -Force
            Write-Host "OK dir $d"
        }
    }
    $pyExtras = @("tha3_engine.py", "tha3_paths.py", "tha3_pose_adapter.py", "external_layer_output_bridge.py", "setup_tha3_vendor.ps1")
    foreach ($f in $pyExtras) {
        $from = Join-Path "$Src\experiments\puppeteer_load_preview" $f
        $to = Join-Path $Exp $f
        if (Test-Path $from) { Copy-Item -LiteralPath $from -Destination $to -Force; Write-Host "OK $f" }
    }
}

# Docs / scaffolding (always ensure dirs exist)
$docDirs = @(
    "$Repo\docs\training",
    "$Repo\docs\camfix",
    "$Repo\scripts"
)
foreach ($d in $docDirs) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

if (Test-Path $Src) {
    @(
        @("$Src\README_BAI_CUSTOM.txt", "$Repo\docs\training\README_BAI_CUSTOM.txt"),
        @("$Src\camfix\CAMERA_CHANGES_SUMMARY.md", "$Repo\docs\camfix\CAMERA_CHANGES_SUMMARY.md"),
        @("$Src\scripts\probe_cameras.bat", "$Repo\scripts\probe_cameras.bat")
    ) | ForEach-Object {
        if (Test-Path $_[0]) { Copy-Item -LiteralPath $_[0] -Destination $_[1] -Force; Write-Host "OK doc $($_[1])" }
    }
    $trainScripts = @(
        "setup_bai_custom.ps1", "preflight_train.ps1", "preflight_config_check.py",
        "package_bai_student.ps1", "package_compare_body_ckpt.ps1",
        "run_body_train.bat", "run_body_train_450k.bat"
    )
    foreach ($s in $trainScripts) {
        $from = Join-Path $Src $s
        if (Test-Path $from) {
            Copy-Item -LiteralPath $from -Destination (Join-Path "$Repo\docs\training" $s) -Force
            Write-Host "OK training $s"
        }
    }
    $packNotes = Join-Path $Src "packaged\bai_450k"
    if (Test-Path $packNotes) {
        foreach ($n in @("TRAINING_NOTES.txt", "PACKAGING_README.txt")) {
            $f = Join-Path $packNotes $n
            if (Test-Path $f) { Copy-Item -LiteralPath $f -Destination "$Repo\docs\training\$n" -Force }
        }
    }
}

Write-Host "Migration copy pass finished. Update HANDOVER.md at repo root (canonical entry)."
