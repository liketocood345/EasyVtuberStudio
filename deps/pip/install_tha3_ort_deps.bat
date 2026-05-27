@echo off
setlocal
call "%~dp0resolve_venv.bat"
if errorlevel 1 exit /b 1
"%PIP%" install -r "%~dp0requirements-tha3-ort.txt"
exit /b %ERRORLEVEL%
