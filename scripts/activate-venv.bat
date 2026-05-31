@echo off
setlocal
call "%~dp0launch\_repo_root.bat"
set "REPO_ROOT=%REPO_ROOT%"

if exist "%REPO_ROOT%\addons\face_puppeteer\venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\addons\face_puppeteer\venv\Scripts\activate.bat"
  goto :eof
)
if exist "%REPO_ROOT%\runtime\venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\runtime\venv\Scripts\activate.bat"
  goto :eof
)
if exist "%REPO_ROOT%\workspace\student_venv\Scripts\activate.bat" (
  call "%REPO_ROOT%\workspace\student_venv\Scripts\activate.bat"
  goto :eof
)

echo ERROR: cannot find venv under repo root: %REPO_ROOT%
echo   Expected addons\face_puppeteer\venv, runtime\venv, or workspace\student_venv
exit /b 1
