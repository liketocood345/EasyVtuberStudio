@echo off
setlocal
set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

if exist "%REPO_ROOT%\src" (
  set "DEMO_ROOT=%REPO_ROOT%"
) else if exist "%REPO_ROOT%\talking-head-anime-4-demo\src" (
  set "DEMO_ROOT=%REPO_ROOT%\talking-head-anime-4-demo"
) else if exist "%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src" (
  set "DEMO_ROOT=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
) else (
  echo ERROR: cannot find talking-head-anime-4-demo src under %REPO_ROOT%
  exit /b 1
)

cd /d "%DEMO_ROOT%"
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe %*
endlocal
