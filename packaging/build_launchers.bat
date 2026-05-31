@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_launchers.ps1"
exit /b %ERRORLEVEL%
