@echo off
setlocal
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
set CONFIG=E:\THA4_bundle\distill_outputs\bai\config.yaml

echo THA4_bundle_bai_custom body training - stop at 450k for eye eval
echo Pack test: package_bai_student.ps1 -BodyCheckpoint 0045
echo.

venv\Scripts\torchrun.exe --nnodes=1 --nproc_per_node=1 --standalone ^
  src\tha4\distiller\distill_body_morpher.py ^
  --target_checkpoint_examples 450000 ^
  --config_file=%CONFIG%

endlocal
