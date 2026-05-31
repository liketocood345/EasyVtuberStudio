@echo off
setlocal EnableDelayedExpansion
call "%~dp0..\scripts\launch\_repo_root.bat"
set "REPO_ROOT=%REPO_ROOT%"
set "VENV_PY="
call "%REPO_ROOT%\scripts\launch\_resolve_portable_python.bat"
if defined PYTHON_EXE set "VENV_PY=%PYTHON_EXE%"
if not defined VENV_PY (
  echo ERROR: no portable Python under %REPO_ROOT%
  echo   Install face_puppeteer add-on ^(DEPLOY.bat [2]^) or run EasyVtuberStudio.exe once.
  exit /b 1
)

echo === THA4 Load Preview release build (draft) ===
echo Repo: %REPO_ROOT%
echo Python: %VENV_PY%
echo.

"%VENV_PY%" -m pip install -q pyinstaller
if errorlevel 1 exit /b 1

cd /d "%REPO_ROOT%"
"%VENV_PY%" -m PyInstaller "packaging\load_preview.spec" --noconfirm --clean
exit /b %ERRORLEVEL%
