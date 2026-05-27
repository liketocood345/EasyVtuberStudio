@echo off
setlocal
set "DEPS_DIR=%~dp0"
set "VENV=%DEPS_DIR%..\..\..\talking-head-anime-4-demo\venv"
set "PIP=%VENV%\Scripts\pip.exe"

if not exist "%PIP%" (
  echo ERROR: venv not found: %VENV%
  exit /b 1
)

echo Installing THA3 ORT black-box deps (DirectML, NO onnx package)...
"%PIP%" install -r "%DEPS_DIR%requirements-tha3-ort.txt"
if errorlevel 1 exit /b 1

echo.
echo If onnx was previously installed, run repair_mediapipe_protobuf.bat
exit /b 0
