@echo off
setlocal EnableDelayedExpansion
if defined REPO_ROOT (
  if exist "%REPO_ROOT%\DEPLOY.bat" goto :found
  if exist "%REPO_ROOT%\EasyVtuberStudio.exe" goto :found
)
set "CUR=%~dp0"
if not "%~1"=="" set "CUR=%~1"
:walk
if "%CUR:~-1%"=="\" set "CUR=%CUR:~0,-1%"
if exist "%CUR%\DEPLOY.bat" (
  set "REPO_ROOT=%CUR%"
  goto :found
)
if exist "%CUR%\EasyVtuberStudio.exe" (
  set "REPO_ROOT=%CUR%"
  goto :found
)
for %%P in ("%CUR%\..") do set "PARENT=%%~fP"
if /i "!PARENT!"=="!CUR!" goto :fail
set "CUR=!PARENT!"
goto :walk
:found
endlocal & set "REPO_ROOT=%REPO_ROOT%"
exit /b 0
:fail
endlocal
echo ERROR: cannot find repo root (need DEPLOY.bat or EasyVtuberStudio.exe)
if not "%~1"=="" echo   started from: %~1
exit /b 1
