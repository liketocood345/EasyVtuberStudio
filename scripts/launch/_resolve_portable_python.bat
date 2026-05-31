@echo off

rem Resolve portable Python for %REPO_ROOT% (addons -> runtime junction -> student_venv).

rem Sets PYTHON_EXE when found.

set "PYTHON_EXE="

if not defined REPO_ROOT exit /b 1



if exist "%REPO_ROOT%\addons\face_puppeteer\venv\Scripts\python.exe" (

  set "PYTHON_EXE=%REPO_ROOT%\addons\face_puppeteer\venv\Scripts\python.exe"

  exit /b 0

)

if exist "%REPO_ROOT%\runtime\venv\Scripts\python.exe" (

  set "PYTHON_EXE=%REPO_ROOT%\runtime\venv\Scripts\python.exe"

  exit /b 0

)

if exist "%REPO_ROOT%\workspace\student_venv\Scripts\python.exe" (

  set "PYTHON_EXE=%REPO_ROOT%\workspace\student_venv\Scripts\python.exe"

  exit /b 0

)

exit /b 1

