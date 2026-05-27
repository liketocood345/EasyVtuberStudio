@echo off
setlocal
set "DEPS_DIR=%~dp0"
set "VENV=%DEPS_DIR%..\..\..\talking-head-anime-4-demo\venv"
set "PIP=%VENV%\Scripts\pip.exe"

if not exist "%PIP%" (
  echo ERROR: venv not found: %VENV%
  exit /b 1
)

echo Installing THA4 Student black-box deps (shell pins)...
"%PIP%" install -r "%DEPS_DIR%requirements-tha4-student.txt"
exit /b %ERRORLEVEL%
