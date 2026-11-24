@rem EVS-DESIGN-AUDIT FILE BEGIN
@rem Manual lookup: E:/record/easyvtuberstudio-index.json
@rem Prompt evidence: E:/record/easyvtuberstudio-prompt-index.json
@rem 2026-10-29 comments only. Adopt latest explicit requirement per property.
@rem Statuses and Chinese details: E:/record/easyvtuberstudio-code-annotations-20261029/annotations.json
@rem EVS-DESIGN-AUDIT FILE END
@rem EVS-DESIGN-AUDIT EVS-A128 BEGIN
@rem Design: dep-003, dep-012, dep-025, f-057; status: partial; runtime untested.
@rem Numeric menu and Enter default basic match current requirements.
@rem Existing 10-40min estimate conflicts with design maximum ten minutes.
@rem This is a text mismatch. DEPLOY not executed.
@rem Hotspot: #6. Risk: R-DEPLOY-03
@rem EVS-DESIGN-AUDIT EVS-A128 END
@echo off
setlocal EnableDelayedExpansion
rem Install tiers after GitHub ZIP extract (basic / face / THA3 / THA4 training).
rem 2026-11-25 zh/en bilingual text. This file is UTF-8 WITHOUT BOM (a BOM breaks
rem line 1). The console uses code page 65001 only while this file prints, and goes
rem back to the user's code page before PowerShell runs, so native tool output
rem inside DEPLOY keeps its usual decoding. Keep all lines above this ASCII-only.
set "EVS_OLD_CP="
for /f "tokens=2 delims=:" %%c in ('chcp') do set "EVS_OLD_CP=%%c"
if defined EVS_OLD_CP set "EVS_OLD_CP=!EVS_OLD_CP: =!"
if defined EVS_OLD_CP set "EVS_OLD_CP=!EVS_OLD_CP:.=!"
chcp 65001 >nul

set "PORTABLE_ROOT=%~dp0"
if "%PORTABLE_ROOT:~-1%"=="\" set "PORTABLE_ROOT=%PORTABLE_ROOT:~0,-1%"
if defined THA4_PORTABLE_ROOT set "PORTABLE_ROOT=%THA4_PORTABLE_ROOT%"

cd /d "%PORTABLE_ROOT%" 2>nul
if errorlevel 1 (
  echo 错误：无法进入目录 / ERROR: cannot enter folder: %PORTABLE_ROOT%
  goto :fail
)
set "THA4_PORTABLE_ROOT=%PORTABLE_ROOT%"

if not exist "%PORTABLE_ROOT%\packaging\deploy_portable.ps1" (
  echo 错误：缺少 packaging\deploy_portable.ps1 / ERROR: missing packaging\deploy_portable.ps1
  echo 请在解压后的根目录（与 EasyVtuberStudio.exe 同一目录）运行 DEPLOY.bat。
  echo Run DEPLOY.bat from the extracted repo root ^(same folder as EasyVtuberStudio.exe^).
  goto :fail
)

echo.
echo ============================================================
echo  EasyVtuberStudio 部署 / DEPLOY
echo ============================================================
echo.
echo  程序目录 / Repo root: %PORTABLE_ROOT%
echo.
echo  共六档，按提示输入编号（例如 1、2 6 或 136）：
echo  Six tiers - enter numbers when prompted (e.g. 1, 2 6, or 136):
echo    [1] basic_run           基础运行：鼠标 + THA4 Student（最小 PyTorch + wx）
echo                            Mouse + THA4 Student (minimal PyTorch + wx)
echo    [2] openseeface         OpenSeeFace 面捕 / OpenSeeFace face capture
echo    [3] face_puppeteer      MediaPipe 面捕 / MediaPipe face capture
echo    [4] tha3_models         THA3 模型权重 / THA3 portrait weights
echo    [5] tha4_training       独立的 THA4 Teacher 训练程序（addons\tha4_training）
echo                            Independent THA4 Teacher app (addons\tha4_training)
echo    [6] output_enhancement  NN 超分 / RIFE 补帧 / DirectML ORT（NVIDIA 显卡另装 TensorRT）
echo                            NN super-res / RIFE / DirectML ORT (+TensorRT on NVIDIA GPUs)
echo.
echo  在档位提示处直接回车 = 只装 [1]（首次推荐）。
echo  Press Enter at tier prompt = install [1] only (recommended first time).
echo  CORE 压缩包已自带 THA4 Student（bai）。 / CORE ZIP already includes THA4 Student (bai).
echo  Python、依赖和缓存都放在本目录内，不装到系统里。
echo  Python, dependencies and caches stay in portable folders; no system install.
echo.
echo  需要联网。[1] 约 2-4 GB；全部档位约 17 GB。可能需要 10-40 分钟。
echo  Requires internet. [1] ~2-4 GB; all tiers ~17 GB. May take 10-40 min.
echo.

set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%POWERSHELL_EXE%" (
  echo 错误：需要 PowerShell。 / ERROR: PowerShell is required.
  goto :fail
)

call :restore_cp
"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%PORTABLE_ROOT%\packaging\deploy_portable.ps1" -PortableRoot "%PORTABLE_ROOT%" -ShowMenu -Confirmed
set "EVS_DEPLOY_EXIT=!errorlevel!"
chcp 65001 >nul
if not "!EVS_DEPLOY_EXIT!"=="0" (
  echo.
  echo 安装未完成。如有 workspace\deploy.log 请查看。
  echo Install did not finish. See workspace\deploy.log if present.
  echo 请检查网络和磁盘空间，然后重新运行 DEPLOY.bat。
  echo Check network and disk space, then run DEPLOY.bat again.
  goto :fail
)

echo.
set "LAUNCH="
set /p LAUNCH=安装完成，现在启动 EasyVtuberStudio.exe？ / Install complete. Launch EasyVtuberStudio.exe now? [Y/n]:
if "!LAUNCH!"=="" set "LAUNCH=Y"
if /i "!LAUNCH!"=="Y" (
  if exist "%PORTABLE_ROOT%\EasyVtuberStudio.exe" (
    start "" "%PORTABLE_ROOT%\EasyVtuberStudio.exe"
  ) else (
    echo 找不到 EasyVtuberStudio.exe。 / EasyVtuberStudio.exe not found.
    goto :fail
  )
)
echo.
echo 完成。之后随时可以再运行 DEPLOY.bat 追加档位。
echo Done. Run DEPLOY.bat again anytime to add more tiers.
pause
call :restore_cp
exit /b 0

:fail
pause
call :restore_cp
exit /b 1

:restore_cp
if defined EVS_OLD_CP chcp !EVS_OLD_CP! >nul
exit /b 0
