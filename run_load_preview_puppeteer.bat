@echo off
setlocal EnableDelayedExpansion
set "REPO_ROOT=%~dp0"
if "%REPO_ROOT:~-1%"=="\" set "REPO_ROOT=%REPO_ROOT:~0,-1%"

set "EXP_SCRIPT=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py"
if not exist "%EXP_SCRIPT%" set "EXP_SCRIPT=%REPO_ROOT%\experiments\puppeteer_load_preview\character_model_mediapipe_puppeteer_load_preview.py"
if not exist "%EXP_SCRIPT%" (
  echo ERROR: cannot find load preview script under repo root: %REPO_ROOT%
  exit /b 1
)

if exist "%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\src" (
  set "DEMO_ROOT=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
) else if exist "%REPO_ROOT%\talking-head-anime-4-demo\src" (
  set "DEMO_ROOT=%REPO_ROOT%\talking-head-anime-4-demo"
) else if exist "%REPO_ROOT%\src" (
  set "DEMO_ROOT=%REPO_ROOT%"
) else (
  echo ERROR: cannot find talking-head-anime-4-demo src under %REPO_ROOT%
  exit /b 1
)

cd /d "%DEMO_ROOT%"
set PYTHONPATH=%cd%\src
set "PYTHON_EXE="
if exist "%DEMO_ROOT%\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%DEMO_ROOT%\venv\Scripts\python.exe"
) else if exist "%REPO_ROOT%\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%REPO_ROOT%\venv\Scripts\python.exe"
) else if exist "%REPO_ROOT%\talking-head-anime-4-demo\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%REPO_ROOT%\talking-head-anime-4-demo\venv\Scripts\python.exe"
) else if exist "%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\python.exe" (
  set "PYTHON_EXE=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo\venv\Scripts\python.exe"
)

set "PYTHON_CMD="
if defined PYTHON_EXE (
  set "PYTHON_CMD=%PYTHON_EXE%"
) else (
  where python >nul 2>nul && set "PYTHON_CMD=python"
  if not defined PYTHON_CMD (
    where py >nul 2>nul && set "PYTHON_CMD=py -3"
  )
)

if not defined PYTHON_CMD (
  echo ERROR: cannot find Python runtime under %REPO_ROOT%
  exit /b 1
)

echo Load Preview experiment puppeteer
echo Repo root: %REPO_ROOT%
echo Demo root: %DEMO_ROOT%
echo.

call %PYTHON_CMD% "%EXP_SCRIPT%"
exit /b %ERRORLEVEL%
