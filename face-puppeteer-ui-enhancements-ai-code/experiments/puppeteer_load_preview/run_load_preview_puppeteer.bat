@echo off
setlocal
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
set LOG_FILE=E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\run_load_preview_runtime.log

echo Load Preview experiment puppeteer
echo Window title: THA4 MediaPipe Puppeteer [Load Preview]
echo After Load Model: right panel shows DEFAULT POSE even if camera is off.
echo Runtime log: %LOG_FILE%
echo.

venv\Scripts\python.exe E:\THA4_bundle_bai_custom\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py > "%LOG_FILE%" 2>&1

endlocal
