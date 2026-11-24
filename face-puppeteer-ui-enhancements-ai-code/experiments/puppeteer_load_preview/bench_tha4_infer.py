"""THA4 Student inference benchmark (Phase 3: before/after per change).

Measures pose list -> HxWx4 uint8 RGBA numpy, i.e. the GPU part of
``_render_pose_to_wx_image_locked`` (wx.Image construction excluded).

Scenarios
  idle : the inference thread runs alone.
  ui   : a second Python thread simulates the UI thread (busy BUSY ms, then
         sleeps IDLE ms, repeat) and competes for the GIL, like timers/compose
         do in the app.

Quality: every variant renders the same fixed pose sequence and is compared
with ``baseline`` (max / mean abs diff, pixels with any channel diff > 4).

Usage (from develop root):
  runtime\\venv\\Scripts\\python.exe face-puppeteer-ui-enhancements-ai-code\\experiments\\puppeteer_load_preview\\bench_tha4_infer.py
      [--variants baseline,skip_outputs,pinned] [--precision half|float]
      [--frames 200] [--rounds 3] [--busy-ms 15 --idle-ms 18]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import sys
import threading
import time
from typing import Callable, Dict, List

import numpy

_HERE = os.path.dirname(os.path.abspath(__file__))
_FACE_ROOT = os.path.dirname(os.path.dirname(_HERE))
_DEV_ROOT = os.path.dirname(_FACE_ROOT)
_DEMO_SRC = os.path.join(_FACE_ROOT, "talking-head-anime-4-demo", "src")
for _p in (_HERE, _DEMO_SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import torch  # noqa: E402
from tha4.charmodel.character_model import CharacterModel  # noqa: E402
from tha4.image_util import convert_linear_to_srgb  # noqa: E402
from tha4.poser.modes.mode_14 import Keys, TwoStepPoserComputationProtocol  # noqa: E402
from tha4.shion.core.cached_computation import ComputationState  # noqa: E402

DEFAULT_MODEL = os.path.join(
    _DEV_ROOT, "data", "character_models", "baiten_from_project_forlon9",
    "bai_450k", "character_model", "character_model.yaml")


# ---------------------------------------------------------------- variants
def _postprocess(output_image):
    # Verbatim from MainFrame._render_pose_to_wx_image_locked.
    output_image = torch.clip((output_image + 1.0) / 2.0, 0.0, 1.0)
    output_image = convert_linear_to_srgb(output_image)
    c, h, w = output_image.shape
    output_image = 255.0 * torch.transpose(output_image.reshape(c, h * w), 0, 1).reshape(h, w, c)
    return output_image.byte()


def make_baseline(poser, image, device, use_half):
    """Current production code path (before Phase 3)."""
    def run(pose_list):
        pose = torch.tensor(pose_list, device=device, dtype=poser.get_dtype())
        with torch.no_grad():
            if use_half and torch.cuda.is_available():
                with torch.cuda.amp.autocast(dtype=torch.float16):
                    output_image = poser.pose(image, pose)[0].float()
            else:
                output_image = poser.pose(image, pose)[0].float()
        with torch.no_grad():
            output_image = _postprocess(output_image)
        return output_image.detach().cpu().numpy()
    return run


def make_original(poser, image, device, use_half):
    """Code path before Phase 3: baseline with the constant-grid caches off."""
    import tha4.nn.image_processing_util as ipu
    inner = make_baseline(poser, image, device, use_half)

    def run(pose_list):
        ipu.EVS_CONST_CACHE_ENABLED = False
        try:
            return inner(pose_list)
        finally:
            ipu.EVS_CONST_CACHE_ENABLED = True
    return run


def make_skip_outputs(poser, image, device, use_half):
    """3.3: ask the protocol for body_morpher_output only (no all_outputs list)."""
    protocol = TwoStepPoserComputationProtocol()
    keys = Keys()

    def _forward(pose):
        state = ComputationState(modules=poser.get_modules(), accumulated_modules={},
                                 batch=[image.unsqueeze(0), pose.unsqueeze(0)], outputs={})
        return protocol.get_output(keys.body_morpher_output, state)[0][0]

    def run(pose_list):
        pose = torch.tensor(pose_list, device=device, dtype=poser.get_dtype())
        with torch.no_grad():
            if use_half:
                with torch.cuda.amp.autocast(dtype=torch.float16):
                    output_image = _forward(pose).float()
            else:
                output_image = _forward(pose).float()
            output_image = _postprocess(output_image)
        return output_image.detach().cpu().numpy()
    return run


def make_pinned(poser, image, device, use_half):
    """3.2: same compute; pinned host buffer + non_blocking D2H + stream sync."""
    size = poser.get_image_size()
    host = torch.empty((size, size, 4), dtype=torch.uint8, pin_memory=True)
    host_np = host.numpy()

    def run(pose_list):
        pose = torch.tensor(pose_list, device=device, dtype=poser.get_dtype())
        with torch.no_grad():
            if use_half:
                with torch.cuda.amp.autocast(dtype=torch.float16):
                    output_image = poser.pose(image, pose)[0].float()
            else:
                output_image = poser.pose(image, pose)[0].float()
            output_image = _postprocess(output_image)
            host.copy_(output_image, non_blocking=True)
        torch.cuda.current_stream(device).synchronize()
        return host_np
    return run


def make_runtime(poser, image, device, use_half):
    """Production Tha4InferRuntime (after Phase 3 changes)."""
    from output_enhancement.tha4_infer_runtime import Tha4InferRuntime
    runtime = Tha4InferRuntime(device)

    def run(pose_list):
        return runtime.render_rgba(poser, image, pose_list, use_half, allow_prepare=True)
    run.runtime = runtime  # type: ignore[attr-defined]
    return run


def make_tensorrt(poser, image, device, use_half):
    """Production runtime with the TensorRT backend chosen (f-058, opt-in).
    Renders until the build/trial state machine settles, then times it."""
    from output_enhancement.tha4_infer_runtime import Tha4InferRuntime
    runtime = Tha4InferRuntime(device)
    model = CharacterModel.load(_MODEL_PATH[0])
    pose = [0.0] * poser.get_num_parameters()
    deadline = time.monotonic() + 600.0
    while time.monotonic() < deadline:
        runtime.render_rgba(poser, image, pose, use_half, allow_prepare=True, trt_model=model)
        if runtime.status()["trt"].get("state") in ("active", "fallback"):
            break
        time.sleep(0.02)
    print("tensorrt state:", {k: v for k, v in runtime.status()["trt"].items() if k != "attempts"})
    for attempt in runtime.status()["trt"].get("attempts", []):
        print("  rejected:", attempt)

    def run(pose_list):
        return runtime.render_rgba(poser, image, pose_list, use_half, allow_prepare=True, trt_model=model)
    run.runtime = runtime  # type: ignore[attr-defined]
    return run


_MODEL_PATH = [DEFAULT_MODEL]


VARIANTS: Dict[str, Callable] = {
    "baseline": make_baseline,
    "original": make_original,
    "skip_outputs": make_skip_outputs,
    "pinned": make_pinned,
    "runtime": make_runtime,
    "tensorrt": make_tensorrt,
}


# ------------------------------------------------------------------ inputs
def make_poses(poser, count: int, seed: int = 1234) -> List[List[float]]:
    ranges = []
    for group in poser.get_pose_parameter_groups():
        for _ in range(group.get_arity()):
            ranges.append(group.get_range())
    rng = numpy.random.default_rng(seed)
    freqs = rng.uniform(0.05, 0.6, len(ranges))
    phases = rng.uniform(0.0, 2.0 * math.pi, len(ranges))
    poses = []
    for i in range(count):
        t = i / 30.0
        pose = []
        for k, (lo, hi) in enumerate(ranges):
            mid, amp = (lo + hi) * 0.5, (hi - lo) * 0.5
            pose.append(float(mid + amp * math.sin(2.0 * math.pi * freqs[k] * t + phases[k])))
        poses.append(pose)
    return poses


class UiLoad:
    """Python thread competing for the GIL like the wx UI thread."""

    def __init__(self, busy_ms: float, idle_ms: float):
        self.busy_s, self.idle_s = busy_ms / 1000.0, idle_ms / 1000.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="bench-ui-load", daemon=True)
        self.cycles = 0

    def _run(self):
        scratch = numpy.zeros((64, 64), numpy.float32)
        while not self._stop.is_set():
            end = time.perf_counter() + self.busy_s
            while time.perf_counter() < end:
                acc = 0
                for i in range(200):
                    acc += i * i
                scratch += 1.0
            self.cycles += 1
            if self.idle_s > 0:
                time.sleep(self.idle_s)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()


# --------------------------------------------------------------- measuring
def time_frames(fn, poses) -> List[float]:
    samples = []
    for pose in poses:
        t0 = time.perf_counter()
        fn(pose)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def summarize(samples: List[float]) -> Dict[str, float]:
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, int(round(0.95 * (len(ordered) - 1))))]
    mean = statistics.fmean(ordered)
    return {"n": len(ordered), "mean_ms": round(mean, 3), "p50_ms": round(statistics.median(ordered), 3),
            "p95_ms": round(p95, 3), "max_ms": round(ordered[-1], 3), "fps": round(1000.0 / mean, 1)}


def compare(reference: List[numpy.ndarray], candidate: List[numpy.ndarray]) -> Dict[str, float]:
    max_diff, alpha_max, total, over4, pixels = 0, 0, 0.0, 0, 0
    for ref, cand in zip(reference, candidate):
        diff = numpy.abs(ref.astype(numpy.int16) - cand.astype(numpy.int16))
        max_diff = max(max_diff, int(diff.max()))
        alpha_max = max(alpha_max, int(diff[:, :, 3].max()))
        total += float(diff.mean())
        over4 += int(numpy.any(diff > 4, axis=2).sum())
        pixels += diff.shape[0] * diff.shape[1]
    return {"max_diff": max_diff, "alpha_max_diff": alpha_max,
            "mean_abs_diff": round(total / max(1, len(reference)), 5),
            "pixels_over4_pct": round(100.0 * over4 / max(1, pixels), 5)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--variants", default="baseline,skip_outputs,pinned")
    parser.add_argument("--precision", choices=["half", "float"], default="half")
    parser.add_argument("--frames", type=int, default=200, help="timed frames per variant per round")
    parser.add_argument("--rounds", type=int, default=3, help="interleaved rounds per scenario")
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--quality-frames", type=int, default=90)
    parser.add_argument("--scenarios", default="idle,ui")
    parser.add_argument("--busy-ms", type=float, default=15.0)
    parser.add_argument("--idle-ms", type=float, default=18.0)
    parser.add_argument("--label", default="")
    parser.add_argument("--save-ref", default="", help="save baseline quality frames (.npz) for later runs")
    parser.add_argument("--ref", default="", help="compare every variant with frames saved by --save-ref")
    parser.add_argument("--switchinterval", type=float, default=0.0,
                        help="sys.setswitchinterval seconds for this run (0 = keep default)")
    args = parser.parse_args()
    if args.switchinterval > 0:
        sys.setswitchinterval(args.switchinterval)

    device = torch.device("cuda")
    use_half = args.precision == "half"
    _MODEL_PATH[0] = args.model
    model = CharacterModel.load(args.model)
    image = model.get_character_image(device)
    poser = model.get_poser(device)
    names = [v.strip() for v in args.variants.split(",") if v.strip()]
    if names[0] != "baseline":
        names.insert(0, "baseline")
    fns = {name: VARIANTS[name](poser, image, device, use_half) for name in names}
    poses = make_poses(poser, max(args.frames, args.quality_frames) + args.warmup)

    print("torch %s | %s | precision=%s | switchinterval=%.4fs" % (
        torch.__version__, torch.cuda.get_device_name(device), args.precision, sys.getswitchinterval()))

    # Quality first (also serves as warmup / lazy init for each variant).
    reference = None
    saved = None
    if args.ref:
        with numpy.load(args.ref) as data:
            saved = [data["f%03d" % i] for i in range(len(data.files))]
    quality = {}
    quality_saved = {}
    for name in names:
        for pose in poses[:args.warmup]:
            fns[name](pose)
        outs = [fns[name](pose).copy() for pose in poses[args.warmup:args.warmup + args.quality_frames]]
        if reference is None:
            reference = outs
            if args.save_ref:
                numpy.savez(args.save_ref, **{"f%03d" % i: frame for i, frame in enumerate(outs)})
        quality[name] = compare(reference, outs)
        if saved is not None:
            quality_saved[name] = compare(saved, outs)

    timing = {}
    timed_poses = poses[args.warmup:args.warmup + args.frames]
    for scenario in [s.strip() for s in args.scenarios.split(",") if s.strip()]:
        samples = {name: [] for name in names}
        for _ in range(args.rounds):
            for name in names:
                if scenario == "ui":
                    with UiLoad(args.busy_ms, args.idle_ms):
                        samples[name] += time_frames(fns[name], timed_poses)
                else:
                    samples[name] += time_frames(fns[name], timed_poses)
        timing[scenario] = {name: summarize(samples[name]) for name in names}

    extra = {}
    for name in names:
        runtime = getattr(fns[name], "runtime", None)
        if runtime is not None:
            extra[name] = runtime.status()

    report = {"label": args.label, "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "torch": torch.__version__,
              "gpu": torch.cuda.get_device_name(device), "precision": args.precision,
              "frames": args.frames, "rounds": args.rounds,
              "ui_load": {"busy_ms": args.busy_ms, "idle_ms": args.idle_ms},
              "quality_vs_baseline": quality, "quality_vs_saved_ref": quality_saved,
              "saved_ref": args.ref or None, "timing": timing, "runtime_status": extra}

    for scenario, rows in timing.items():
        base = rows["baseline"]["mean_ms"]
        print("\n[%s]" % scenario)
        print("%-14s %8s %8s %8s %8s %7s %8s" % ("variant", "mean", "p50", "p95", "max", "fps", "vs base"))
        for name, row in rows.items():
            print("%-14s %8.2f %8.2f %8.2f %8.2f %7.1f %7.2fx" % (
                name, row["mean_ms"], row["p50_ms"], row["p95_ms"], row["max_ms"], row["fps"],
                base / row["mean_ms"]))
    print("\n[quality vs baseline]")
    for name, row in quality.items():
        print("%-14s %s" % (name, row))
    if quality_saved:
        print("\n[quality vs saved reference %s]" % os.path.basename(args.ref))
        for name, row in quality_saved.items():
            print("%-14s %s" % (name, row))
    for name, status in extra.items():
        print("%-14s status %s" % (name, status))

    out_dir = os.path.join(_DEV_ROOT, "workspace", "diagnostics")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "bench_tha4_infer_%s%s.json" % (
        time.strftime("%Y%m%d_%H%M%S"), ("_" + args.label) if args.label else ""))
    with open(out_path, "w", encoding="utf-8") as fout:
        json.dump(report, fout, ensure_ascii=False, indent=2)
    print("\nreport: %s" % out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
