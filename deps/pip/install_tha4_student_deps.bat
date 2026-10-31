@echo off
setlocal
set "REPO_ROOT=%~dp0"
:find_root
if exist "%REPO_ROOT%\DEPLOY.bat" goto found_root
for %%I in ("%REPO_ROOT%\..") do set "PARENT_ROOT=%%~fI"
if /i "%PARENT_ROOT%"=="%REPO_ROOT%" exit /b 1
set "REPO_ROOT=%PARENT_ROOT%"
goto find_root
:found_root
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%\packaging\deploy_portable.ps1" -PortableRoot "%REPO_ROOT%" -PackageIds "mouse_student" -Confirmed
exit /b %ERRORLEVEL%
