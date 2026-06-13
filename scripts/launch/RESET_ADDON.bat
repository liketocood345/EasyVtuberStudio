@echo off
setlocal EnableDelayedExpansion
rem Remove one optional add-on folder and restore CORE layout.
set "PORTABLE_ROOT=%~dp0"
if "%PORTABLE_ROOT:~-1%"=="\" set "PORTABLE_ROOT=%PORTABLE_ROOT:~0,-1%"
if defined THA4_PORTABLE_ROOT set "PORTABLE_ROOT=%THA4_PORTABLE_ROOT%"

echo.
echo ============================================================
echo  EasyVtuberStudio RESET_ADDON
echo  Delete an add-on folder under addons\
echo ============================================================
echo.
echo  [1] face_puppeteer
echo  [2] tha3_models
echo  [3] tha4_training
echo  [0] cancel
echo.

set /p CHOICE=Which add-on to remove?
if "%CHOICE%"=="0" exit /b 0
if "%CHOICE%"=="1" set "ADDON_ID=face_puppeteer"
if "%CHOICE%"=="2" set "ADDON_ID=tha3_models"
if "%CHOICE%"=="3" set "ADDON_ID=tha4_training"
if not defined ADDON_ID (
  echo Invalid choice.
  pause
  exit /b 1
)

set /p CONFIRM=Delete addons\%ADDON_ID% and reconcile links? Type Y:
if /i not "%CONFIRM%"=="Y" (
  echo Cancelled.
  pause
  exit /b 0
)

set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PORTABLE_ROOT%\packaging\reset_addon.ps1" -PortableRoot "%PORTABLE_ROOT%" -AddonId "%ADDON_ID%" -Confirmed
if errorlevel 1 (
  echo Reset failed.
  pause
  exit /b 1
)

echo.
echo Add-on removed and layout reconciled.
pause
exit /b 0
