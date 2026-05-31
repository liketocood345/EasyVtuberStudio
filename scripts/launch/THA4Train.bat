@echo off
setlocal EnableDelayedExpansion
call "%~dp0_repo_root.bat"
set "THA4_PORTABLE_ROOT=%REPO_ROOT%"
set "THA4_WORKSPACE=%REPO_ROOT%\workspace"

if exist "%~dp0THA4Train.exe" (
  start "" "%~dp0THA4Train.exe"
  exit /b 0
)

set "DEMO=%REPO_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
set "TRAIN_DATA=%DEMO%\data\tha4\face_morpher.pt"
set "POSE_DATA=%DEMO%\data\pose_dataset.pt"
if not exist "%TRAIN_DATA%" goto :need_training_assets
if not exist "%POSE_DATA%" goto :need_training_assets
goto :launch_distiller

:need_training_assets
echo.
echo THA4 teacher weights / pose_dataset.pt are missing.
echo They will be downloaded from pkhungurn official Dropbox and installed automatically.
set /p CONFIRM=Download now? [Y/N]:
if /i not "%CONFIRM%"=="Y" exit /b 1
call "%REPO_ROOT%\packaging\THA4_DownloadTrainingAssets.bat"
if errorlevel 1 exit /b 1

:launch_distiller
call "%DEMO%\bin\run.bat" src\tha4\app\distiller_ui.py
exit /b %ERRORLEVEL%
