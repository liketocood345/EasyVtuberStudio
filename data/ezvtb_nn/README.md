# EZVTB NN weights (DEPLOY tier [5])

RIFE / waifu2x / Real-ESRGAN ONNX for post-process super-resolution and frame interpolation.

## 从哪里获取

| 来源 | `data/ezvtb_nn/*.onnx` |
|------|------------------------|
| **[HF Bucket 完整发行](https://huggingface.co/buckets/liketocode789/EasyVtuberStudio)** | **已内置**（`hf buckets sync` 整目录即可） |
| **GitHub CORE ZIP（瘦包）** | **不含** ONNX；装档位 [5] 时由 DEPLOY 从 Bucket 拉取 |
| **维护者本地** | `scripts/maint/import_ezvtb_nn_weights.ps1`（Google Drive 数据包） |

## GitHub 瘦包用户

安装档位 **[5] output_enhancement** 时，DEPLOY 会：

1. **首选**从 Bucket `liketocode789/EasyVtuberStudio` 下载 `data/ezvtb_nn/`；
2. 复制到 `addons/output_enhancement/ezvtb_data/`；
3. Bucket 失败时回退 `import_ezvtb_nn_weights.ps1`。

详见 [docs/DEPLOY.md](../docs/DEPLOY.md)、[docs/HF_BUCKET_MIRROR.md](../docs/HF_BUCKET_MIRROR.md)。

## Layout

```text
data/ezvtb_nn/
├── rife/
│   ├── rife_x2_fp32.onnx
│   ├── rife_x3_fp32.onnx
│   ├── rife_x4_fp32.onnx
│   └── (optional fp16 variants)
├── waifu2x/
│   └── noise0_scale2x_fp32.onnx (+ fp16)
└── Real-ESRGAN/
    └── exported_256_fp32.onnx (+ fp16)
```

## Maintainer refresh

```powershell
powershell -ExecutionPolicy Bypass -File scripts\maint\import_ezvtb_nn_weights.ps1 -PortableRoot .
```

复制到 `EasyVtuberStudio-hf` 后 `sync_develop_to_hf_bucket.ps1` 上传 Bucket。见 [docs/HF_BUCKET_MIRROR.md](../docs/HF_BUCKET_MIRROR.md)。

Source archive: [ezvtuber-rt Google Drive data pack](https://drive.google.com/file/d/1pWKIpjWeqfpa3Rub185FVvxDr5H09pOi/view?usp=drive_link).

License: upstream THA3 / RIFE / waifu2x / Real-ESRGAN terms; see `deps/tha3/ezvtuber_rt/README.md`.
