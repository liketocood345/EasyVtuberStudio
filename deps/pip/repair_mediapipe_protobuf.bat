@echo off
setlocal
call "%~dp0resolve_venv.bat"
if errorlevel 1 exit /b 1
"%PIP%" uninstall -y onnx 2>nul
"%PIP%" install "protobuf==3.20.3" "mediapipe==0.10.9"
exit /b %ERRORLEVEL%
