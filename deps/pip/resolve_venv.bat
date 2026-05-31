@echo off
if not defined REPO_ROOT call "%~dp0find_repo_root.bat"
if errorlevel 1 exit /b 1
set "VENV="
if exist "%REPO_ROOT%\addons\face_puppeteer\venv\Scripts\pip.exe" set "VENV=%REPO_ROOT%\addons\face_puppeteer\venv"
if not defined VENV if exist "%REPO_ROOT%\runtime\venv\Scripts\pip.exe" set "VENV=%REPO_ROOT%\runtime\venv"
if not defined VENV if exist "%REPO_ROOT%\workspace\student_venv\Scripts\pip.exe" set "VENV=%REPO_ROOT%\workspace\student_venv"
if not defined VENV (
  echo ERROR: cannot find venv under repo root: %REPO_ROOT%
  echo   Expected addons\face_puppeteer\venv, runtime\venv, or workspace\student_venv
  echo   Run DEPLOY.bat tier [1] basic_run or [2] face_puppeteer first.
  exit /b 1
)
set "PIP=%VENV%\Scripts\pip.exe"
exit /b 0
