@echo off
setlocal EnableDelayedExpansion
call "%~dp0_repo_root.bat"
set "THA4_PORTABLE_ROOT=%REPO_ROOT%"
set "THA4_WORKSPACE=%REPO_ROOT%\workspace"

if exist "%REPO_ROOT%\EasyVtuberStudio.exe" (
  start "" "%REPO_ROOT%\EasyVtuberStudio.exe"
  exit /b 0
)

call "%~dp0run_load_preview_puppeteer.bat"
exit /b %ERRORLEVEL%
