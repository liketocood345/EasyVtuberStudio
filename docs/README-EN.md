# EasyVtuberStudio — English Guide

**EasyVtuberStudio** is a virtual avatar face-puppeteering application built on THA3 and THA4 (with UI patterns influenced by EasyVtuber).

## Startup Guide

### Recommended (end users)

1. **GitHub:** Code → Download ZIP → extract, **or** sync the full project from [HF Bucket](https://huggingface.co/buckets/liketocode789/EasyVtuberStudio) (`pip install huggingface_hub` then `hf buckets sync …`)  
2. Double-click **`DEPLOY.bat`** — **five** Y/N tiers (Enter = default): **[1] basic_run**, **[2] face_puppeteer**, **[3] tha3_models**, **[4] tha4_training**, **[5] output_enhancement**  
3. Double-click **`EasyVtuberStudio.exe`**

See [DEPLOY.md](DEPLOY.md) (Chinese, step-by-step).

### Developer fallback

```bat
scripts\launch\run_load_preview_puppeteer.bat
```

Other launchers under `scripts\launch\` (e.g. `THA4Train.exe`, `THA4_DownloadAssets.bat`).

## What EasyVtuberStudio Is

- **Release repo:** `E:\easyvtuberstudio-main` — deployment, GitHub push, docs under `docs/`
- **Active development:** `E:\easyvtuberstudio-develop` — daily coding; sync to fork when stable
- Fork remote: [liketocood345/EasyVtuberStudio](https://github.com/liketocood345/EasyVtuberStudio)（formerly `EasyVtuber-with-THA3-THA4`)

## Quick Pointers

- Chinese main overview: [../README.md](../README.md)
- **Full doc index:** [DOC_INDEX.md](DOC_INDEX.md)
- **First-time deploy:** [DEPLOY.md](DEPLOY.md)
- **HF Bucket (full release):** https://huggingface.co/buckets/liketocode789/EasyVtuberStudio
- Troubleshooting: [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)
- Handover: [HANDOVER.md](HANDOVER.md)

## Current Direction

- **Mouse + Audio mocap** (no camera): global mouse for head/eyes, mic for mouth — Model Input → *Mouse + Audio (EasyVtuber)*
- Window capture video source (OBS-style)
- Output dynamic enhancement calibration (scale, horizontal center, head roll baseline)
- Portable release: run **`DEPLOY.bat`**, then **`EasyVtuberStudio.exe`**

See [../plans/PORTABLE_RELEASE.plan.md](../plans/PORTABLE_RELEASE.plan.md).
