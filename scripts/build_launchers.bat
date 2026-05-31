@echo off
setlocal
call "%~dp0launch\_repo_root.bat"
echo Building EasyVtuberStudio.exe and THA4Train.exe ...
echo Repo: %REPO_ROOT%
echo.
call "%REPO_ROOT%\packaging\build_launchers.bat"
if errorlevel 1 (
  echo.
  echo [FAILED] See errors above. Need venv + PyInstaller; see docs\DEPLOY.md.
  exit /b 1
)
echo.
echo Output:
if exist "%REPO_ROOT%\EasyVtuberStudio.exe" (
  echo   [OK] EasyVtuberStudio.exe
) else (
  echo   [MISSING] EasyVtuberStudio.exe
)
if exist "%REPO_ROOT%\scripts\launch\THA4Train.exe" (
  echo   [OK] scripts\launch\THA4Train.exe
) else (
  echo   [MISSING] scripts\launch\THA4Train.exe
)
exit /b 0
