# Optional add-on packs

Large optional downloads install under `addons/<pack>/`. CORE paths (`runtime/venv`, `deps/tha3/models`, `demo/data/*`) are **junction links** rebuilt by `packaging/reconcile_portable_layout.ps1`.

## DEPLOY tiers (number menu)

| Tier | Default Enter | Add-on folder | Installs |
|------|---------------|---------------|----------|
| **[1] basic_run** | Y | — | `workspace/student_venv` (Mouse + THA4 Student) |
| **[2] openseeface** | N | `addons/openseeface/` | OpenSeeFace facetracker + models（HF Bucket 首选） |
| **[3] face_puppeteer** | N | `addons/face_puppeteer/` | PyTorch + wx + MediaPipe + `.task` |
| **[4] tha3_models** | N | `addons/tha3_models/` | THA3 portrait weights |
| **[5] output_enhancement** | N | `addons/output_enhancement/` | onnxruntime + NN SR/RIFE（ONNX 从 HF Bucket 或桶内已带） |
| **[6] tha4_training** | N | `addons/tha4_training/` | Teacher + pose dataset |

Run **`DEPLOY.bat`** from the repo root. **`EasyVtuberStudio.exe`** starts when tier [1] (or face-capture tier [2]/[3]) is already satisfied.

**Remove an add-on:** delete its folder (or run `RESET_ADDON.bat`), then reconcile runs automatically.

**CORE GitHub ZIP includes:** exe, code, THA4 Student (bai). It does **not** include runtime, training weights, or `data/ezvtb_nn/*.onnx` (see HF Bucket or DEPLOY [5]).

**HF Bucket full release:** https://huggingface.co/buckets/liketocode789/EasyVtuberStudio

See [docs/ADDONS_LAYOUT.md](../docs/ADDONS_LAYOUT.md) · [docs/DEPLOY.md](../docs/DEPLOY.md).
