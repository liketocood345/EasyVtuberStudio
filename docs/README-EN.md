# EasyVtuberStudio — English Guide

**EasyVtuberStudio** is a virtual avatar face-puppeteering application built on THA3 and THA4, with UI patterns influenced by EasyVtuber and optional OpenSeeFace / MediaPipe capture.

## Startup Guide

### Recommended (end users)

1. **GitHub:** Code → Download ZIP → extract, **or** sync the full project from [HF Bucket](https://huggingface.co/buckets/liketocode789/EasyVtuberStudio) (`pip install huggingface_hub` then `hf buckets sync …`)
2. Double-click **`DEPLOY.bat`** — **six** install tiers (type numbers; **Enter = [1] only**):
   - **[1] basic_run** — Mouse + THA4 Student (minimal runtime)
   - **[2] openseeface** — OpenSeeFace camera mocap
   - **[3] face_puppeteer** — MediaPipe camera / window capture
   - **[4] tha3_models** — THA3 portrait weights
   - **[5] tha4_training** — THA4 teacher / distillation assets
   - **[6] output_enhancement** — NN super-res / RIFE (ONNX from HF Bucket)
3. Double-click **`EasyVtuberStudio.exe`**

Camera mocap: install **[2] openseeface** **or** **[3] face_puppeteer** (either is enough).

See [DEPLOY.md](DEPLOY.md) (Chinese, step-by-step).

### Developer fallback

```bat
scripts\launch\run_load_preview_puppeteer.bat
```

Other launchers under `scripts\launch\` (e.g. `THA4Train.exe`, `THA4_DownloadAssets.bat`).

## What EasyVtuberStudio Is

- **Release repo:** `E:\easyvtuberstudio-main` — deployment, GitHub push, docs under `docs/`
- **Active development:** `E:\easyvtuberstudio-develop` — daily coding; sync to fork when stable
- **HF Bucket:** full release mirror with `data/ezvtb_nn/` and `addons/openseeface/` payloads
- Fork remote: [liketocood345/EasyVtuberStudio](https://github.com/liketocood345/EasyVtuberStudio) (formerly `EasyVtuber-with-THA3-THA4`)

## Quick Pointers

- Chinese main overview: [../README.md](../README.md)
- **Full doc index:** [DOC_INDEX.md](DOC_INDEX.md)
- **First-time deploy:** [DEPLOY.md](DEPLOY.md)
- **HF Bucket (full release):** https://huggingface.co/buckets/liketocode789/EasyVtuberStudio
- Troubleshooting: [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)
- Handover: [HANDOVER.md](HANDOVER.md)

## Current Direction (2026-06-24)

- **Three mocap modes:** OpenSeeFace · MediaPipe (camera / window / file) · Mouse + Audio (no camera)
- **Single ULW output window** (`easyvtuberstudio_output`) for transparent + solid backgrounds; layer edit on overlay
- **Layer system L2:** dynamic slots, swing / circular / orbit-follow motion, binding with torso lean
- **Optional output enhancement:** SR / RIFE / TensorRT pipeline (tier [6])
- **Release builds:** long-run NDJSON debug scaffolding removed; production ULW threading and stall heal retained

See [CHANGELOG.md](CHANGELOG.md) and [../plans/PORTABLE_RELEASE.plan.md](../plans/PORTABLE_RELEASE.plan.md).
