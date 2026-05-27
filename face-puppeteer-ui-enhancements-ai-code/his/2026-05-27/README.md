# Face Puppeteer UI Enhancements (AI Code Draft)

This folder is a draft package prepared under `E:\` for a future fork repository.

## Included content

- `experiments/puppeteer_load_preview/character_model_mediapipe_puppeteer_load_preview.py`
- `experiments/puppeteer_load_preview/README.txt`
- `experiments/puppeteer_load_preview/run_load_preview_puppeteer.bat`
- `experiments/puppeteer_load_preview/smoke_load_preview.py`
- `talking-head-anime-4-demo/src/tha4/mocap/mediapipe_face_pose_converter_00.py`
- `packaged/bai_450k/`

## Main UI and puppeteer changes

- Render one neutral default pose frame immediately after a model is loaded.
- Keep the preview image visible when there is no face input instead of clearing back to `Nothing yet!`.
- Split the character output into a separate borderless output window with remembered size and position.
- Support drag-moving the borderless output window directly from the output canvas.
- Add `Load Last Model` and `Load Other Model`, including invalid last-path warning handling.
- Add automatic display move / scale driven by face tracking.
- Add nonlinear scale mapping with curve controls, peak shift, current-point status, and curve preview.
- Add tilt-driven display rotation, invert toggle, negative tilt attenuation, and tilt compensation.
- Add independent mirror output and adjustable post-process anti-aliasing.
- Reorganize controls into model input, dynamic output, and postprocess sections.
- Disable interactive controls while no model is loaded.
- Persist relevant UI state such as toggles, intervals, background, splitters, output window geometry, and last model path.
- Add breathing controls with reactive breathing behavior.
- Add mouth input switching between face capture and audio input.
- Add audio source selection, audio smoothing controls, and a live oscilloscope panel.
- Add compact startup launcher flow:
  - startup shows a small launcher window,
  - full controls are created lazily on first open,
  - compact and full windows can switch between each other,
  - launcher includes the hint `To load a new model, open full controls`.

## Bai model package

- Included packaged model: `packaged/bai_450k/character_model/character_model.yaml`
- Face morpher source: checkpoint `0010`
- Body morpher source: checkpoint `0045`

## Source of this draft

The files were copied from the current working custom environment under `E:\THA4_bundle_bai_custom`.
