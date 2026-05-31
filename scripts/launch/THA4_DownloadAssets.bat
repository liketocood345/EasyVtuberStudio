@echo off
setlocal EnableDelayedExpansion
call "%~dp0_repo_root.bat"
set "THA4_PORTABLE_ROOT=%REPO_ROOT%"
set "THA4_WORKSPACE=%REPO_ROOT%\workspace"

call "%REPO_ROOT%\packaging\THA4_DownloadAssets.bat" %*
exit /b %ERRORLEVEL%
