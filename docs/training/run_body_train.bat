@echo off
setlocal
cd /d E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
set PYTHONPATH=%cd%\src
set CONFIG=E:\THA4_bundle\distill_outputs\bai\config.yaml

echo THA4_bundle_bai_custom body training (anti eye-smear schedule)
echo Config: %CONFIG%
echo Target: 800000 examples (phases 450k / 650k / 800k, ckpt every 10k)
echo First eval milestone: 450000 -^> checkpoint 0045
echo.

venv\Scripts\torchrun.exe --nnodes=1 --nproc_per_node=1 --standalone ^
  src\tha4\distiller\distill_body_morpher.py ^
  --target_checkpoint_examples 800000 ^
  --config_file=%CONFIG%

endlocal
