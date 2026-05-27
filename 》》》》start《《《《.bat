@echo off
setlocal
set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "TARGET=%ROOT%\run_load_preview_puppeteer.bat"

if not exist "%TARGET%" (
  echo [ERROR] Launcher target not found:
  echo   %TARGET%
  exit /b 1
)

call "%TARGET%"
endlocal
