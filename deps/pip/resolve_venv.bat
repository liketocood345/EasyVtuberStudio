@echo off
if not defined REPO_ROOT call "%~dp0find_repo_root.bat"
if errorlevel 1 exit /b 1
call "%REPO_ROOT%\scripts\launch\_resolve_portable_python.bat"
if errorlevel 1 (
  echo ERROR: cannot find venv under repo root: %REPO_ROOT%
  echo   Expected a folder-local THA3, Face or Student Python base and environment.
  echo   Run DEPLOY.bat tier [1] basic_run or [2] face_puppeteer first.
  exit /b 1
)
for %%P in ("%PYTHON_EXE%") do set "PYTHON_SCRIPTS=%%~dpP"
for %%V in ("%PYTHON_SCRIPTS%..") do set "VENV=%%~fV"
set "PIP=%VENV%\Scripts\pip.exe"
exit /b 0
