@echo off
setlocal EnableDelayedExpansion
set "PORTABLE_ROOT=%~dp0"
if "%PORTABLE_ROOT:~-1%"=="\" set "PORTABLE_ROOT=%PORTABLE_ROOT:~0,-1%"
set "THA4_PORTABLE_ROOT=%PORTABLE_ROOT%"

if "%~1"=="" (
  echo Usage: THA4_Distill.bat ^<config.yaml^>
  exit /b 1
)

call "%PORTABLE_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\bin\run.bat" src\tha4\app\distill.py %*
exit /b %ERRORLEVEL%
