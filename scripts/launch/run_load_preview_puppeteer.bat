@echo off
setlocal EnableDelayedExpansion
call "%~dp0_repo_root.bat"
set "THA4_PORTABLE_ROOT=%REPO_ROOT%"
set "THA4_WORKSPACE=%REPO_ROOT%\workspace"

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
call "%~dp0_resolve_portable_python.bat"

if not defined PYTHON_EXE (
  echo ERROR: cannot find Python runtime under %REPO_ROOT%
  echo   Expected a folder-local THA3, Face or Student environment.
  echo   Run DEPLOY.bat tier [1] basic_run or [2] face_puppeteer first.
  exit /b 1
)

if /I not "%EVS_EARLY_SPLASH%"=="1" (
  set "SPLASH_PY=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\experiments\puppeteer_load_preview\start_with_splash.py"
  set "PYTHONW=%PYTHON_EXE%"
  if defined PYTHONW set "PYTHONW=!PYTHONW:python.exe=pythonw.exe!"
  if exist "!SPLASH_PY!" if exist "!PYTHONW!" (
    start "" "!PYTHONW!" "!SPLASH_PY!"
    exit /b 0
  )
)

echo Load Preview experiment puppeteer
echo Repo root: %REPO_ROOT%
echo Demo root: %DEMO_ROOT%
echo.

"%PYTHON_EXE%" "%EXP_SCRIPT%"
exit /b %ERRORLEVEL%
