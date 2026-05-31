@echo off
setlocal EnableDelayedExpansion
set "PORTABLE_ROOT=%~dp0.."
if "%PORTABLE_ROOT:~-1%"=="\" set "PORTABLE_ROOT=%PORTABLE_ROOT:~0,-1%"
if defined THA4_PORTABLE_ROOT set "PORTABLE_ROOT=%THA4_PORTABLE_ROOT%"

where powershell >nul 2>nul
if errorlevel 1 (
  echo ERROR: PowerShell is required for THA3_DownloadModels.
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%PORTABLE_ROOT%\packaging\download_tha3_assets.ps1" -PortableRoot "%PORTABLE_ROOT%"
exit /b %ERRORLEVEL%
