@echo off
setlocal
call "%~dp0find_repo_root.bat"
if errorlevel 1 exit /b 1
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%\packaging\repair_capture_dependencies.ps1" -PortableRoot "%REPO_ROOT%"
exit /b %ERRORLEVEL%
