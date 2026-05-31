@echo off
setlocal EnableDelayedExpansion
call "%~dp0launch\_repo_root.bat"
set "DEMO=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
if not exist "%DEMO%\src" set "DEMO=%REPO_ROOT%\talking-head-anime-4-demo"
if not exist "%DEMO%\src" (
  echo ERROR: talking-head-anime-4-demo not found under %REPO_ROOT%
  exit /b 1
)
cd /d "%DEMO%"
set "PYTHONPATH=%CD%\src"
set "PYTHON_EXE="
call "%~dp0launch\_resolve_portable_python.bat"
if not defined PYTHON_EXE (
  where py >nul 2>nul && set "PYTHON_EXE=py -3"
)
if not defined PYTHON_EXE (
  echo ERROR: no Python found for camera probe under %REPO_ROOT%
  exit /b 1
)
call %PYTHON_EXE% "%REPO_ROOT%\scripts\probe_cameras.py"
pause
