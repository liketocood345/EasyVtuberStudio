@echo off
setlocal
call "%~dp0resolve_venv.bat"
if errorlevel 1 exit /b 1
set "DEPS_DIR=%~dp0"

echo Installing shell + THA4 Student + THA3 ORT deps...
"%PIP%" install -r "%DEPS_DIR%requirements-tha4-student.txt"
if errorlevel 1 exit /b 1
"%PIP%" install -r "%DEPS_DIR%requirements-tha3-ort.txt"
exit /b %ERRORLEVEL%
