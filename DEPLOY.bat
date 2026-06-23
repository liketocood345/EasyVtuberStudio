@echo off
setlocal EnableDelayedExpansion
rem Install tiers after GitHub ZIP extract (basic / face / THA3 / THA4 training).
set "PORTABLE_ROOT=%~dp0"
if "%PORTABLE_ROOT:~-1%"=="\" set "PORTABLE_ROOT=%PORTABLE_ROOT:~0,-1%"
if defined THA4_PORTABLE_ROOT set "PORTABLE_ROOT=%THA4_PORTABLE_ROOT%"

cd /d "%PORTABLE_ROOT%" 2>nul
if errorlevel 1 (
  echo ERROR: cannot enter folder: %PORTABLE_ROOT%
  pause
  exit /b 1
)
set "THA4_PORTABLE_ROOT=%PORTABLE_ROOT%"

if not exist "%PORTABLE_ROOT%\packaging\deploy_portable.ps1" (
  echo ERROR: missing packaging\deploy_portable.ps1
  echo Run DEPLOY.bat from the extracted repo root ^(same folder as EasyVtuberStudio.exe^).
  pause
  exit /b 1
)

echo.
echo ============================================================
echo  EasyVtuberStudio DEPLOY
echo ============================================================
echo.
echo  Repo root: %PORTABLE_ROOT%
echo.
echo  Six tiers - enter numbers when prompted (e.g. 1, 2 6, or 136):
echo    [1] basic_run           - Mouse + THA4 Student (minimal PyTorch + wx)
echo    [2] openseeface         - OpenSeeFace face capture
echo    [3] face_puppeteer      - MediaPipe face capture
echo    [4] tha3_models         - THA3 portrait weights
echo    [5] tha4_training       - THA4 teacher + pose dataset
echo    [6] output_enhancement  - NN super-res / RIFE / ORT (optional TensorRT)
echo.
echo  Press Enter at tier prompt = install [1] only (recommended first time).
echo  CORE ZIP already includes THA4 Student (bai).
echo.
echo  Requires internet. [1] ~2-4 GB; all tiers ~15 GB. May take 10-40 min.
echo.

set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL_EXE%" (
  echo ERROR: PowerShell is required.
  pause
  exit /b 1
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PORTABLE_ROOT%\packaging\deploy_portable.ps1" -PortableRoot "%PORTABLE_ROOT%" -ShowMenu -Confirmed
if errorlevel 1 (
  echo.
  echo Install did not finish. See workspace\deploy.log if present.
  echo Check network and disk space, then run DEPLOY.bat again.
  pause
  exit /b 1
)

echo.
set /p LAUNCH=Install complete. Launch EasyVtuberStudio.exe now? [Y/n]:
if "!LAUNCH!"=="" set "LAUNCH=Y"
if /i "!LAUNCH!"=="Y" (
  if exist "%PORTABLE_ROOT%\EasyVtuberStudio.exe" (
    start "" "%PORTABLE_ROOT%\EasyVtuberStudio.exe"
  ) else (
    echo EasyVtuberStudio.exe not found.
    pause
    exit /b 1
  )
)
echo.
echo Done. Run DEPLOY.bat again anytime to add more tiers.
pause
exit /b 0