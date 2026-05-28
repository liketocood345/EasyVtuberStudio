Packaged: 2026-05-23 11:14:27
Dest: E:\THA4_bundle_bai_custom\packaged\bai_450k
Train prefix: E:\THA4_bundle\distill_outputs\bai
face_morpher.pt <= face_morpher/checkpoint/0010/module_module.pt
body_morpher.pt <= body_morpher/checkpoint/0045/module_module.pt
character.png <= data/images/bai.png

Load in demo:
  cd E:\THA4_bundle_bai_custom\talking-head-anime-4-demo
  bin\run.bat src\tha4\app\character_model_manual_poser.py
  -> Load Model -> E:\THA4_bundle_bai_custom\packaged\bai_450k\character_model\character_model.yaml

Custom schedule milestones: 0045=450k eval, 0080=800k final.
