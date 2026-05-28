@echo off
cd /d E:\THA4_bundle\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
venv\Scripts\python.exe E:\THA4_bundle_bai_custom\scripts\probe_cameras.py
pause
