@echo off
REM Shared venv resolution relative to repo root (included by other install_*.bat).
set "REPO_ROOT=%~dp0..\.."
if exist "%REPO_ROOT%\venv\Scripts\pip.exe" (
  set "VENV=%REPO_ROOT%\venv"
  goto :done
)
if exist "%REPO_ROOT%\talking-head-anime-4-demo\venv\Scripts\pip.exe" (
  set "VENV=%REPO_ROOT%\talking-head-anime-4-demo\venv"
  goto :done
)
if exist "%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\pip.exe" (
  set "VENV=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv"
  goto :done
)
echo ERROR: cannot find venv under repo root: %REPO_ROOT%
exit /b 1
:done
set "PIP=%VENV%\Scripts\pip.exe"
