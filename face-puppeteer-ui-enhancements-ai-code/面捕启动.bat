@echo off
setlocal

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "TARGET=%ROOT%\experiments\puppeteer_load_preview\run_load_preview_puppeteer.bat"

if not exist "%TARGET%" (
  echo [ERROR] Launcher target not found:
  echo   %TARGET%
  echo.
  echo Please keep filename/path unchanged or update this launcher .bat accordingly.
  pause
  exit /b 1
)

call "%TARGET%"
endlocal
