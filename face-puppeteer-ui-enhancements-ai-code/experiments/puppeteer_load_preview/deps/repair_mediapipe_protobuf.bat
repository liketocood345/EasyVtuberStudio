@echo off
setlocal
set "DEPS_DIR=%~dp0"
set "VENV=%DEPS_DIR%..\..\..\talking-head-anime-4-demo\venv"
set "PIP=%VENV%\Scripts\pip.exe"

if not exist "%PIP%" (
  echo ERROR: venv not found: %VENV%
  exit /b 1
)

echo Repairing mediapipe/protobuf after mistaken onnx install...
"%PIP%" uninstall -y onnx 2>nul
"%PIP%" install "protobuf==3.20.3" "mediapipe==0.10.9"
exit /b %ERRORLEVEL%
