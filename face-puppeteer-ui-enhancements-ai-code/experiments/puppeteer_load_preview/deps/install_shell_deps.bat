@echo off
setlocal
set "DEPS_DIR=%~dp0"
call "%DEPS_DIR%..\..\..\..\deps\pip\resolve_venv.bat"
if errorlevel 1 exit /b 1
echo Installing Load Preview shell deps...
"%PIP%" install -r "%DEPS_DIR%requirements-shell.txt"
exit /b %ERRORLEVEL%
