@echo off
setlocal
set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

if exist "%REPO_ROOT%\venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\venv\Scripts\activate.bat"
  goto :eof
)
if exist "%REPO_ROOT%\talking-head-anime-4-demo\venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\talking-head-anime-4-demo\venv\Scripts\activate.bat"
  goto :eof
)
if exist "%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\activate.bat"
  goto :eof
)

echo ERROR: cannot find venv activate.bat under repo root: %REPO_ROOT%
exit /b 1
