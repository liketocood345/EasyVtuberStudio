@echo off
setlocal
set "DEPS_DIR=%~dp0"
set "VENV=%DEPS_DIR%..\..\..\talking-head-anime-4-demo\venv"
set "PIP=%VENV%\Scripts\pip.exe"

if not exist "%PIP%" (
  echo ERROR: venv not found: %VENV%
  echo Create it first from talking-head-anime-4-demo\poetry
  exit /b 1
)

echo Installing Load Preview shell deps...
"%PIP%" install -r "%DEPS_DIR%requirements-shell.txt"
exit /b %ERRORLEVEL%
