@echo off
setlocal
set "DEPS_DIR=%~dp0"
call "%DEPS_DIR%..\..\..\..\deps\pip\resolve_venv.bat"
if errorlevel 1 exit /b 1
echo Repairing mediapipe/protobuf after mistaken onnx install...
"%PIP%" uninstall -y onnx 2>nul
"%PIP%" install "protobuf==3.20.3" "mediapipe==0.10.9"
exit /b %ERRORLEVEL%
