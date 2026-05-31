@echo off
setlocal
set "DEPS_DIR=%~dp0"
call "%DEPS_DIR%..\..\..\..\deps\pip\resolve_venv.bat"
if errorlevel 1 exit /b 1
echo Installing THA4 Student black-box deps (shell pins)...
"%PIP%" install -r "%DEPS_DIR%requirements-tha4-student.txt"
exit /b %ERRORLEVEL%
