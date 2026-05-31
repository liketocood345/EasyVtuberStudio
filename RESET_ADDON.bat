@echo off
rem Wrapper: keep RESET_ADDON.bat at repo root (next to DEPLOY.bat).
call "%~dp0scripts\launch\RESET_ADDON.bat" %*
exit /b %ERRORLEVEL%
