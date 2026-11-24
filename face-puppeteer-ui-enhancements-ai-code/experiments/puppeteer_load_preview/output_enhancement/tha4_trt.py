"""THA4 Student TensorRT path (EVS-PERF 3.4, f-058 / f-057).

Opt-in: used only when the NN backend choice is TensorRT. PyTorch stays the
default and the fallback at every step.

Flow (all driven by Tha4InferRuntime on the infer worker, under the model lock
except where noted):
  1. ONNX export of the exact Student forward (face morpher -> paste into the
     source image -> body morpher, mode_14 geometry). ~1 s, once per model.
  2. Engine build on a background thread (no lock; minutes on first use),
     cached in workspace/cache/tha4_trt/<key>.engine. The key covers the model
     and source-image bytes, precision, TensorRT version, GPU and export code,
     so a cached engine never outlives what it was built from.
  3. Quality trial against the FP32 PyTorch reference (see trial_gate), then
     hot-swap. Rejection or any runtime error keeps PyTorch.

Quality yardstick: THA4's SIREN layers (sin with omega=30) amplify kernel
rounding, so *any* different implementation differs from eager by up to ~18
levels at a few pixels even in FP32 (PyTorch CPU vs CUDA: max 18, mean 0.032,
0.008% pixels > 4). "max_diff <= 4 vs eager" cannot be met by TensorRT. The
gate instead requires TensorRT to be no worse versus the FP32 reference than
the PyTorch path the user already runs at the same precision setting.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

import numpy
import torch

EXPORT_VERSION = "tha4-student-raw-v1"
# Bump when the PyTorch numerics the gate compares against change, so cached
# gate decisions are re-tried (v2: dtype-keyed GridChangeApplier identity).
GATE_VERSION = 2
# mode_14: face crop centre (x=256, y=128+16), 128x128.
_FACE_Y0, _FACE_Y1, _FACE_X0, _FACE_X1 = 80, 208, 192, 320
# Allowed ratio to the accepted PyTorch path's deviation from FP32. Default
# 1.25; EVS_THA4_TRT_GATE_FACTOR overrides it (user choice, e.g. 1.5 admits the
# FP16 engine measured at ~1.27x mean / ~1.4x pixels>4 on bai_450k).
def _gate_factor() -> float:
    try:
        return max(1.0, float(os.environ.get("EVS_THA4_TRT_GATE_FACTOR", "1.25")))
    except ValueError:
        return 1.25


GATE_MEAN_FACTOR = _gate_factor()
GATE_MEAN_FLOOR = 0.10          # FP32 mode: allow CPU-vs-GPU-sized noise
GATE_PX4_FACTOR = GATE_MEAN_FACTOR
GATE_PX4_FLOOR_PCT = 0.05


def import_tensorrt():
    try:
        import tensorrt as trt  # meta package alias, if installed
    except ImportError:
        import tensorrt_bindings as trt  # tensorrt-cu11-bindings wheel
    return trt


def tensorrt_version() -> Optional[str]:
    try:
        return str(import_tensorrt().__version__)
    except Exception:
        return None


class StudentForward(torch.nn.Module):
    """Same ops as GeneralPoser02.pose(...)[0] for mode_14, batch 1."""

    def __init__(self, poser, image: torch.Tensor):
        super().__init__()
        modules = poser.get_modules()
        self.face = modules["face_morpher"]
        self.body = modules["body_morpher"]
        self.register_buffer("image", image.unsqueeze(0).clone())

    def forward(self, pose: torch.Tensor) -> torch.Tensor:
        image = self.image.clone()
        image[:, :, _FACE_Y0:_FACE_Y1, _FACE_X0:_FACE_X1] = self.face(pose[:, 0:39])
        return self.body(image, pose)[0][0]


def _file_sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _model_parts(character_model) -> Dict[str, str]:
    return {"export": EXPORT_VERSION,
            "face": _file_sha256(character_model.face_morpher_file_name),
            "body": _file_sha256(character_model.body_morpher_file_name),
            "image": _file_sha256(character_model.character_image_file_name)}


def engine_key(character_model, use_half: bool, device: torch.device) -> str:
    parts = dict(_model_parts(character_model), half=bool(use_half), trt=tensorrt_version(),
                 gpu=torch.cuda.get_device_name(device), cc=list(torch.cuda.get_device_capability(device)))
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode("utf-8")).hexdigest()[:24]


def onnx_name(character_model, device: torch.device) -> str:
    digest = hashlib.sha256(json.dumps(_model_parts(character_model), sort_keys=True).encode("utf-8"))
    return "student-" + digest.hexdigest()[:24] + ".onnx"


def cache_dir() -> str:
    """Folder-local engine cache: <portable root>/workspace/cache/tha4_trt."""
    from portable_process_env import root_from_source
    directory = os.path.join(str(root_from_source()), "workspace", "cache", "tha4_trt")
    os.makedirs(directory, exist_ok=True)
    return directory


def read_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def write_json(path: str, data: Dict[str, Any]) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    except OSError:
        pass


def export_onnx(poser, image: torch.Tensor, pose_list, path: str) -> None:
    """Export under the caller's model lock. Constant grids must be cached
    (one eager forward) so tracing sees constants, not affine_grid."""
    wrapper = StudentForward(poser, image).eval()
    sample = torch.tensor([list(pose_list)], device=image.device, dtype=torch.float32)
    with torch.no_grad():
        wrapper(sample)
        torch.onnx.export(wrapper, sample, path, opset_version=17, input_names=["pose"],
                          output_names=["raw"], do_constant_folding=True)


def build_engine_bytes(onnx_path: str, use_half: bool) -> bytes:
    trt = import_tensorrt()
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    network = builder.create_network(0)
    parser = trt.OnnxParser(network, logger)
    with open(onnx_path, "rb") as handle:
        if not parser.parse(handle.read()):
            raise RuntimeError("ONNX parse failed: " + "; ".join(
                str(parser.get_error(i)) for i in range(parser.num_errors)))
    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 2 << 30)
    if use_half:
        config.set_flag(trt.BuilderFlag.FP16)
    blob = builder.build_serialized_network(network, config)
    if blob is None:
        raise RuntimeError("TensorRT build returned no engine")
    return bytes(blob)


class Tha4TrtEngine:
    """Deserialized engine bound to torch-owned device buffers."""

    def __init__(self, blob: bytes, device: torch.device):
        trt = import_tensorrt()
        self._logger = trt.Logger(trt.Logger.WARNING)
        self._runtime = trt.Runtime(self._logger)
        self.engine = self._runtime.deserialize_cuda_engine(blob)
        if self.engine is None:
            raise RuntimeError("TensorRT engine deserialization failed")
        self.context = self.engine.create_execution_context()
        self.device = device
        self.pose = torch.zeros((1, 45), dtype=torch.float32, device=device)
        self.host_pose = torch.empty((1, 45), dtype=torch.float32, pin_memory=True)
        self.host_pose_np = self.host_pose.numpy()
        raw_dtype = torch.float16 if self.engine.get_tensor_dtype("raw") == trt.DataType.HALF else torch.float32
        self.raw = torch.empty((4, 512, 512), dtype=raw_dtype, device=device)
        self.context.set_tensor_address("pose", self.pose.data_ptr())
        self.context.set_tensor_address("raw", self.raw.data_ptr())

    def launch(self, pose_list) -> torch.Tensor:
        """Enqueue on the current stream; returns the raw [4,512,512] output."""
        self.host_pose_np[0, :] = pose_list
        self.pose.copy_(self.host_pose, non_blocking=True)
        if not self.context.execute_async_v3(torch.cuda.current_stream(self.device).cuda_stream):
            raise RuntimeError("TensorRT execute_async_v3 failed")
        return self.raw


def trial_gate(candidate: List[numpy.ndarray], accepted: List[numpy.ndarray],
               reference_fp32: List[numpy.ndarray]) -> Dict[str, Any]:
    """Candidate must be no worse vs FP32 than the accepted PyTorch path."""
    def metrics(outs):
        diffs = [numpy.abs(a.astype(numpy.int16) - b.astype(numpy.int16)) for a, b in zip(reference_fp32, outs)]
        return (float(numpy.mean([d.mean() for d in diffs])),
                100.0 * float(numpy.mean([(d.max(axis=2) > 4).mean() for d in diffs])),
                int(max(d.max() for d in diffs)))
    cand_mean, cand_px4, cand_max = metrics(candidate)
    acc_mean, acc_px4, acc_max = metrics(accepted)
    mean_limit = max(acc_mean * GATE_MEAN_FACTOR, GATE_MEAN_FLOOR)
    px4_limit = max(acc_px4 * GATE_PX4_FACTOR, GATE_PX4_FLOOR_PCT)
    return {"passed": cand_mean <= mean_limit and cand_px4 <= px4_limit, "factor": GATE_MEAN_FACTOR,
            "trt_vs_fp32": {"mean": round(cand_mean, 4), "px4_pct": round(cand_px4, 4), "max": cand_max},
            "pytorch_vs_fp32": {"mean": round(acc_mean, 4), "px4_pct": round(acc_px4, 4), "max": acc_max},
            "limits": {"mean": round(mean_limit, 4), "px4_pct": round(px4_limit, 4)}}


class EngineBuildJob:
    """Background engine build (f-057 slow task: never on the UI thread, never
    holding the model lock; PyTorch renders meanwhile)."""

    def __init__(self, key: str, onnx_path: str, engine_path: str, use_half: bool):
        self.key, self.onnx_path, self.engine_path, self.use_half = key, onnx_path, engine_path, use_half
        self.started = time.monotonic()
        self.finished: Optional[float] = None
        self.blob: Optional[bytes] = None
        self.error: Optional[str] = None
        self._thread = threading.Thread(target=self._run, name="tha4-trt-build", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        try:
            blob = build_engine_bytes(self.onnx_path, self.use_half)
            tmp = self.engine_path + ".tmp"
            with open(tmp, "wb") as handle:
                handle.write(blob)
            os.replace(tmp, self.engine_path)
            self.blob = blob
        except Exception as exc:  # reported via status; PyTorch keeps rendering
            self.error = "%s: %s" % (type(exc).__name__, exc)
        finally:
            self.finished = time.monotonic()

    @property
    def done(self) -> bool:
        return self.finished is not None

    def elapsed_s(self) -> float:
        return (self.finished or time.monotonic()) - self.started
