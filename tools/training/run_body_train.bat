@echo off
setlocal EnableDelayedExpansion
set "PORTABLE_ROOT=%~dp0..\.."
if "%PORTABLE_ROOT:~-1%"=="\" set "PORTABLE_ROOT=%PORTABLE_ROOT:~0,-1%"
set "THA4_PORTABLE_ROOT=%PORTABLE_ROOT%"
set "THA4_WORKSPACE=%PORTABLE_ROOT%\workspace"

set "DEMO=%PORTABLE_ROOT%\face-puppeteer-ui-enhancements-ai-code\talking-head-anime-4-demo"
set "CONFIG=%THA4_WORKSPACE%\distill_outputs\bai\config.yaml"
if not "%~1"=="" set "CONFIG=%~1"

set "TORCHRUN="
if exist "%PORTABLE_ROOT%\addons\face_puppeteer\venv\Scripts\torchrun.exe" (
  set "TORCHRUN=%PORTABLE_ROOT%\addons\face_puppeteer\venv\Scripts\torchrun.exe"
) else if exist "%PORTABLE_ROOT%\runtime\venv\Scripts\torchrun.exe" (
  set "TORCHRUN=%PORTABLE_ROOT%\runtime\venv\Scripts\torchrun.exe"
)
if not defined TORCHRUN (
  echo ERROR: torchrun not found. Run scripts\launch\THA4_DownloadAssets.bat or docs\DEPLOY.md setup.
  exit /b 1
)

cd /d "%DEMO%"
set PYTHONPATH=%cd%\src

echo Portable body training (800k schedule)
echo Config: %CONFIG%
echo.

"%TORCHRUN%" --nnodes=1 --nproc_per_node=1 --standalone ^
  src\tha4\distiller\distill_body_morpher.py ^
  --target_checkpoint_examples 800000 ^
  --config_file=%CONFIG%

exit /b %ERRORLEVEL%
