@echo off
setlocal
call "%~dp0_repo_root.bat"

if exist "%REPO_ROOT%\EasyVtuberStudio.exe" (
  start "" "%REPO_ROOT%\EasyVtuberStudio.exe"
  exit /b 0
)

call "%~dp0run_load_preview_puppeteer.bat"
endlocal
