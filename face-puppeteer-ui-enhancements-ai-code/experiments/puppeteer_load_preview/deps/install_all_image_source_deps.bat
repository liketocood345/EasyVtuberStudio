@echo off
setlocal
set "DEPS_DIR=%~dp0"
set "VENV=%DEPS_DIR%..\..\..\talking-head-anime-4-demo\venv"
set "PIP=%VENV%\Scripts\pip.exe"

if not exist "%PIP%" (
  echo ERROR: venv not found: %VENV%
  exit /b 1
)

echo Installing shell + THA4 Student + THA3 ORT deps...
"%PIP%" install -r "%DEPS_DIR%requirements-tha4-student.txt"
if errorlevel 1 exit /b 1
"%PIP%" install -r "%DEPS_DIR%requirements-tha3-ort.txt"
exit /b %ERRORLEVEL%
