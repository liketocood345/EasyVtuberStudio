@echo off
call "%~dp0..\..\..\..\deps\pip\repair_mediapipe_protobuf.bat"
exit /b %ERRORLEVEL%
