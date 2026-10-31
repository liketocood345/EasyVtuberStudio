@echo off
setlocal
call "%~dp0_repo_root.bat"
if errorlevel 1 exit /b 1
set "TEACHER=%REPO_ROOT%\addons\tha4_training\THA4Train.exe"
if not exist "%TEACHER%" (
  echo Please run DEPLOY tier [5] to install the independent portable Teacher.
  exit /b 1
)
start "" "%TEACHER%" %*
exit /b 0
