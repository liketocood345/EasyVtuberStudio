# English Guide (Native English Readers)

This repository is a fork that combines work around THA3, THA4, and EasyVtuber-related tooling.

## Startup Guide

### Recommended (one-step launch)

From repository root:

```bat
run_load_preview_puppeteer.bat
```

This launcher auto-detects the runtime layout (`src`, `venv`, and `PYTHONPATH`) and is the preferred way to start.

### Alternative launchers

- `run.bat` - generic wrapper launcher
- `》》》》start《《《《.bat` - shortcut-style starter kept for existing workflow compatibility

## Packaging Status

This project is already packaged and ready for direct use in its current repository structure.

- Core scripts, docs, and dependency paths are included.
- You can run immediately with the launcher above.
- Re-packaging is optional and only needed if you want a custom distribution layout.

## What This Repo Is

- **Release repo (this tree):** `E:\tha4fork` — deployment, GitHub push, **canonical documentation**
- **Active development:** `E:\tha4fork-develop` — daily coding; merge to fork when stable
- Upstream base: [pkhungurn/talking-head-anime-4-demo](https://github.com/pkhungurn/talking-head-anime-4-demo)
- Fork remote: [liketocood345/EasyVtuber-with-THA3-THA4](https://github.com/liketocood345/EasyVtuber-with-THA3-THA4)

## Quick Pointers

- Chinese main overview: [README.md](README.md)
- **Full doc index:** [docs/DOC_INDEX.md](docs/DOC_INDEX.md)
- **First-time deploy (GitHub ZIP):** [DEPLOY.md](DEPLOY.md)
- Detailed project notes: [README-detail.md](README-detail.md)
- Troubleshooting FAQ (most complete): [TROUBLESHOOTING_QA.md](TROUBLESHOOTING_QA.md)
- Handover document: [HANDOVER.md](HANDOVER.md)
- Change history: [CHANGELOG.md](CHANGELOG.md)

## Current Direction

- Window capture video source (OBS-style, for DroidCam preview window bypass)
- Output dynamic enhancement calibration (scale baseline + horizontal recenter)
- Documentation in **`E:\tha4fork`** is the operational source of truth

## Encoding and Language Note

To preserve file integrity and avoid data loss, Chinese characters are allowed in this project documentation and related text files.

- Do not force-convert all content to English-only text.
- Keep files in UTF-8 encoding.
- If a Chinese term is project-specific, keep the original Chinese and add an English explanation when needed.


