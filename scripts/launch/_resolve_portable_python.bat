@echo off
set "PYTHON_EXE="
if not defined REPO_ROOT exit /b 1
rem Outer quotes survive cmd.exe /c parsing when the portable folder has spaces.
for /f "delims=" %%P in ('""%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%\packaging\resolve_portable_python.ps1" -PortableRoot "%REPO_ROOT%""') do set "PYTHON_EXE=%%P"
if not defined PYTHON_EXE exit /b 1
exit /b 0
