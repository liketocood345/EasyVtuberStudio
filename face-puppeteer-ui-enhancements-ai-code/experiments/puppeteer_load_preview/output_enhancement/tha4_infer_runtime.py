"""THA4 Student render runtime: eager path + optional CUDA Graph (EVS-PERF Phase 3).

Measured on RTX A4000 / torch 1.13.1 (bench_tha4_infer.py): the per-frame cost
is ~15 ms of GPU work plus ~7 ms of Python op dispatch. Dispatch competes with
the wx UI thread for the GIL, so under UI load a frame stretched to ~24 ms.
A CUDA Graph replays the identical kernels from one call, removing almost all
per-frame Python dispatch; the GPU work itself is unchanged.

Contract
- Every call (render_rgba / reset / status) happens under the caller's model
  render lock (MainFrame._model_render_lock).
- render_rgba returns a view of a reused pinned host buffer. It stays valid
  until the next render_rgba call; consume or copy it under the same lock.
- The graph is only prepared on a worker thread (allow_prepare=True) and only
  after a trial on the live model: max pixel diff <= GRAPH_MAX_DIFF against the
  eager path and not slower than eager. Any failure keeps the eager path.
- One graph at a time, bound to (poser, source image, precision). A change of
  any of them drops it; reset() releases it (model unload / reload).
"""
from __future__ import annotations

import inspect
import os
import statistics
import time
import weakref
from typing import Any, Dict, List, Optional

import numpy
import torch

from tha4.image_util import convert_linear_to_srgb

GRAPH_WARMUP_EAGER_FRAMES = 3
GRAPH_TRIAL_FRAMES = 6
GRAPH_MAX_DIFF = 4
GRAPH_SLOWER_TOLERANCE = 1.10
GRAPH_MIN_FREE_VRAM = 512 * 2 ** 20
_TRIAL_POSE_INDEX = 39  # head_x in the THA4 pose layout


def _postprocess(output_image: torch.Tensor) -> torch.Tensor:
    # Same ops as the former MainFrame._render_pose_to_wx_image_locked.
    output_image = torch.clip((output_image + 1.0) / 2.0, 0.0, 1.0)
    output_image = convert_linear_to_srgb(output_image)
    c, h, w = output_image.shape
    output_image = 255.0 * torch.transpose(output_image.reshape(c, h * w), 0, 1).reshape(h, w, c)
    return output_image.byte()


def _forward_rgba(poser, image, pose, use_half: bool, autocast_cache: bool = True) -> torch.Tensor:
    with torch.no_grad():
        if use_half:
            with torch.cuda.amp.autocast(dtype=torch.float16, cache_enabled=autocast_cache):
                output_image = poser.pose(image, pose)[0].float()
        else:
            output_image = poser.pose(image, pose)[0].float()
        return _postprocess(output_image)


def _constant_references(poser) -> List[Any]:
    """Tensors captured by reference in the graph that the modules cache."""
    refs: List[Any] = []
    for module in poser.get_modules().values():
        for sub in module.modules():
            owners = [sub] + [v for v in sub.__dict__.values() if hasattr(v, "__dict__")]
            for owner in owners:
                cache = owner.__dict__.get("_evs_const_cache")
                if cache:
                    refs.extend(cache.values())
                identity = owner.__dict__.get("last_identity")
                if identity is not None:
                    refs.append(identity)
                refs.extend((owner.__dict__.get("_evs_identities") or {}).values())
    return refs


class _StaticTha4Graph:
    def __init__(self, poser, image, use_half: bool, device: torch.device):
        self.poser, self.image, self.use_half, self.device = poser, image, use_half, device
        count, dtype = poser.get_num_parameters(), poser.get_dtype()
        self.host_pose = torch.empty((count,), dtype=dtype, pin_memory=True)
        self.host_pose_np = self.host_pose.numpy()
        self.pose = torch.zeros((count,), dtype=dtype, device=device)
        stream = torch.cuda.Stream(device=device)
        current = torch.cuda.current_stream(device)
        stream.wait_stream(current)
        with torch.cuda.stream(stream):
            for _ in range(3):
                self._gpu_frame()
        current.wait_stream(stream)
        torch.cuda.synchronize(device)
        self.keepalive = _constant_references(poser)
        self.graph = torch.cuda.CUDAGraph()
        options: Dict[str, Any] = {"stream": stream}
        if "capture_error_mode" in inspect.signature(torch.cuda.graph).parameters:
            options["capture_error_mode"] = "thread_local"
        with torch.cuda.graph(self.graph, **options):
            self.output = self._gpu_frame()
        torch.cuda.synchronize(device)

    def _gpu_frame(self) -> torch.Tensor:
        return _forward_rgba(self.poser, self.image, self.pose, self.use_half,
                             autocast_cache=False).contiguous()

    def launch(self, pose_list, host_out: torch.Tensor) -> None:
        # Each torch call releases and re-takes the GIL; under UI load every
        # re-take can wait a switch interval, so the pose is filled via NumPy.
        # The previous frame finished (caller synchronizes), so reuse is safe.
        self.host_pose_np[:] = pose_list
        self.pose.copy_(self.host_pose, non_blocking=True)
        self.graph.replay()
        host_out.copy_(self.output, non_blocking=True)


class Tha4InferRuntime:
    def __init__(self, device):
        device = torch.device(device)
        if device.type == "cuda" and device.index is None and torch.cuda.is_available():
            device = torch.device("cuda", torch.cuda.current_device())
        self.device = device
        self._host: Optional[torch.Tensor] = None
        self._host_np: Optional[numpy.ndarray] = None
        self._done = None
        self._graph: Optional[_StaticTha4Graph] = None
        self._key = None
        self._eager_frames = 0
        self._attempted = False
        self._status: Dict[str, Any] = {"enabled": False, "reason": "not prepared"}
        self.last_path = "eager"
        self.last_launch_ms = 0.0
        self.last_wait_ms = 0.0
        self._trt_clear("off")

    # ---------------------------------------------------------------- state
    def reset(self, reason: str = "reset") -> None:
        self._graph = None
        self._key = None
        self._eager_frames = 0
        self._attempted = False
        self._status = {"enabled": False, "reason": reason}
        self._trt_clear("off")

    def status(self) -> Dict[str, Any]:
        result = dict(self._status)
        result.update(active=self._graph is not None, last_path=self.last_path,
                      eager_frames=self._eager_frames, trt=dict(self._trt_status))
        return result

    def _trt_clear(self, state: str, **status) -> None:
        # A running build job keeps going (its engine file is still cached);
        # its result is simply no longer consumed here.
        self._trt_engine = None
        self._trt_job = None
        self._trt_blob = None
        self._trt_candidates: List[bool] = []
        self._trt_half: Optional[bool] = None
        self._trt_key: Optional[str] = None
        self._trt_state = state
        self._trt_status: Dict[str, Any] = dict(status, state=state)

    def _matches_key(self, poser, image, use_half: bool) -> bool:
        key = self._key
        return key is not None and key[0]() is poser and key[1]() is image and key[2] == use_half

    def _bind_key(self, poser, image, use_half: bool) -> None:
        previous = self._key is not None
        self.reset("model or precision changed" if previous else "not prepared")
        self._key = (weakref.ref(poser), weakref.ref(image), use_half)

    def _host_buffer(self, shape) -> torch.Tensor:
        if self._host is None or tuple(self._host.shape) != tuple(shape):
            self._host = torch.empty(tuple(shape), dtype=torch.uint8, pin_memory=True)
            self._host_np = self._host.numpy()
            self._done = torch.cuda.Event()
        return self._host

    # --------------------------------------------------------------- render
    def render_rgba(self, poser, image, pose_list, use_half: bool,
                    allow_prepare: bool = False, trt_model=None) -> numpy.ndarray:
        """trt_model: the CharacterModel when the TensorRT backend is chosen
        (opt-in, f-058); None keeps the PyTorch paths only."""
        use_half = bool(use_half) and torch.cuda.is_available()
        if self.device.type != "cuda":
            pose = torch.tensor(pose_list, device=self.device, dtype=poser.get_dtype())
            self.last_path = "eager-cpu"
            return _forward_rgba(poser, image, pose, use_half).detach().cpu().numpy()
        if not self._matches_key(poser, image, use_half):
            self._bind_key(poser, image, use_half)
        if trt_model is None:
            if self._trt_state != "off":
                self._trt_clear("off", reason="backend is not TensorRT")
        elif allow_prepare and self._trt_state not in ("active", "fallback"):
            self._advance_trt(poser, image, pose_list, use_half, trt_model)
        if (allow_prepare and not self._attempted
                and self._eager_frames >= GRAPH_WARMUP_EAGER_FRAMES):
            self._attempted = True
            self._prepare_graph(poser, image, use_half, pose_list)

        start = time.perf_counter()
        engine = self._trt_engine
        if engine is not None and trt_model is not None:
            try:
                output = _postprocess(engine.launch(pose_list).float())
                host = self._host_buffer(output.shape)
                host.copy_(output, non_blocking=True)
                self.last_path = "tensorrt"
                return self._finish(start)
            except Exception as exc:  # keep rendering with PyTorch; no retry
                self._trt_engine = None
                self._trt_state = "fallback"
                self._trt_status = dict(self._trt_status, state="fallback",
                                        reason="runtime error: %s: %s" % (type(exc).__name__, exc))
                start = time.perf_counter()
        graph = self._graph
        if graph is not None:
            try:
                host = self._host_buffer(graph.output.shape)
                graph.launch(pose_list, host)
                self.last_path = "graph"
                return self._finish(start)
            except Exception as exc:  # keep rendering; never retry this graph
                self._graph = None
                self._status = {"enabled": False, "reason": "replay failed: %s: %s" % (
                    type(exc).__name__, exc)}
                start = time.perf_counter()
        pose = torch.tensor(pose_list, device=self.device, dtype=poser.get_dtype())
        output = _forward_rgba(poser, image, pose, use_half)
        host = self._host_buffer(output.shape)
        host.copy_(output, non_blocking=True)
        self._eager_frames += 1
        self.last_path = "eager"
        return self._finish(start)

    def _finish(self, start: float) -> numpy.ndarray:
        self._done.record()
        launched = time.perf_counter()
        self._done.synchronize()
        self.last_launch_ms = (launched - start) * 1000.0
        self.last_wait_ms = (time.perf_counter() - launched) * 1000.0
        return self._host_np

    # ---------------------------------------------------------------- graph
    def _eager_copy(self, poser, image, pose_list, use_half: bool) -> numpy.ndarray:
        pose = torch.tensor(pose_list, device=self.device, dtype=poser.get_dtype())
        return _forward_rgba(poser, image, pose, use_half).cpu().numpy()

    def _prepare_graph(self, poser, image, use_half: bool, pose_list) -> None:
        from output_enhancement.gpu_work_gate import SHARED_GPU_GATE
        began = time.perf_counter()
        try:
            free, _ = torch.cuda.mem_get_info(self.device)
            if free < GRAPH_MIN_FREE_VRAM:
                self._status = {"enabled": False, "reason": "insufficient free VRAM",
                                "free_mb": round(free / 2 ** 20)}
                return
            # torch.cuda.graph() empties the allocator cache on entry; do it first so
            # the delta is comparable. It covers warm-up + graph pool, not the pool alone.
            torch.cuda.synchronize(self.device)
            torch.cuda.empty_cache()
            reserved = torch.cuda.memory_reserved(self.device)
            with SHARED_GPU_GATE.job("tha4-graph-prepare"):
                graph = _StaticTha4Graph(poser, image, use_half, self.device)
            pool_mb = (torch.cuda.memory_reserved(self.device) - reserved) / 2 ** 20
            trial_host = torch.empty(tuple(graph.output.shape), dtype=torch.uint8, pin_memory=True)
            base = numpy.asarray(pose_list, dtype=numpy.float32)
            index = min(_TRIAL_POSE_INDEX, base.shape[0] - 1)
            eager_ms, graph_ms = [], []
            max_diff = 0
            for step in range(GRAPH_TRIAL_FRAMES):
                test = base.copy()
                test[index] = float(numpy.clip(test[index] + 0.01 * (step - 2), -1.0, 1.0))
                test_list = test.tolist()
                wall = time.perf_counter()
                expected = self._eager_copy(poser, image, test_list, use_half)
                eager_ms.append((time.perf_counter() - wall) * 1000.0)
                wall = time.perf_counter()
                graph.launch(test_list, trial_host)
                torch.cuda.current_stream(self.device).synchronize()
                graph_ms.append((time.perf_counter() - wall) * 1000.0)
                diff = numpy.abs(trial_host.numpy().astype(numpy.int16) - expected.astype(numpy.int16))
                max_diff = max(max_diff, int(diff.max()))
            eager, captured = statistics.median(eager_ms), statistics.median(graph_ms)
            status = {"eager_ms": round(eager, 2), "graph_ms": round(captured, 2),
                      "max_diff": max_diff, "reserved_delta_mb": round(pool_mb, 1), "use_half": use_half,
                      "trial_frames": GRAPH_TRIAL_FRAMES}
            if max_diff > GRAPH_MAX_DIFF:
                status.update(enabled=False, reason="trial pixel mismatch")
            elif captured > eager * GRAPH_SLOWER_TOLERANCE:
                status.update(enabled=False, reason="graph slower than eager")
            else:
                status.update(enabled=True, reason="")
                self._graph = graph
            self._status = status
        except Exception as exc:
            self._graph = None
            self._status = {"enabled": False, "reason": "%s: %s" % (type(exc).__name__, exc)}
        finally:
            self._status["prepare_ms"] = round((time.perf_counter() - began) * 1000.0, 1)

    # ------------------------------------------------------------ TensorRT
    def _advance_trt(self, poser, image, pose_list, use_half: bool, trt_model) -> None:
        """One cheap step per worker frame: pick engine -> build (background)
        -> quality/speed trial -> active; otherwise next candidate -> fallback."""
        from output_enhancement import tha4_trt as T
        try:
            if self._trt_state == "off":
                version = T.tensorrt_version()
                if version is None:
                    self._trt_clear("fallback", reason="TensorRT not installed")
                    return
                # User precision first; the FP32 engine is the quality fallback.
                self._trt_candidates = [True, False] if use_half else [False]
                self._trt_state = "next"
                self._trt_status = {"state": "next", "tensorrt": version, "attempts": []}
            if self._trt_state == "next":
                if not self._trt_candidates:
                    self._trt_state = "fallback"
                    self._trt_status = dict(self._trt_status, state="fallback",
                                            reason="no TensorRT engine passed the trial")
                    return
                half = self._trt_candidates[0]
                key = T.engine_key(trt_model, half, self.device)
                directory = T.cache_dir()
                engine_path = os.path.join(directory, key + ".engine")
                gate_path = os.path.join(directory, key + ".gate.json")
                self._trt_half, self._trt_key = half, key
                previous = T.read_json(gate_path)
                if (previous is not None and not previous.get("passed")
                        and previous.get("gate_version") == T.GATE_VERSION
                        and previous.get("factor") == T.GATE_MEAN_FACTOR):
                    self._trt_reject(previous, cached=True)
                    return
                if os.path.isfile(engine_path):
                    with open(engine_path, "rb") as handle:
                        self._trt_blob = handle.read()
                    self._trt_state = "trial"
                else:
                    onnx_path = os.path.join(directory, T.onnx_name(trt_model, self.device))
                    if not os.path.isfile(onnx_path):
                        T.export_onnx(poser, image, pose_list, onnx_path)
                    self._trt_job = T.EngineBuildJob(key, onnx_path, engine_path, half)
                    self._trt_state = "building"
                    self._trt_status = dict(self._trt_status, state="building", engine_fp16=half,
                                            note="one-time build; PyTorch renders meanwhile")
                    return
            if self._trt_state == "building":
                job = self._trt_job
                if job is None or not job.done:
                    return
                self._trt_status = dict(self._trt_status, build_s=round(job.elapsed_s(), 1))
                if job.error:
                    self._trt_reject({"passed": False, "reason": "build failed: " + job.error})
                    return
                self._trt_blob, self._trt_job = job.blob, None
                self._trt_state = "trial"
            if self._trt_state == "trial":
                self._trial_trt(poser, image, pose_list, use_half, T)
        except Exception as exc:
            self._trt_clear("fallback", reason="%s: %s" % (type(exc).__name__, exc))

    def _trt_reject(self, result: Dict[str, Any], cached: bool = False) -> None:
        attempts = list(self._trt_status.get("attempts", []))
        attempts.append(dict(result, engine_fp16=self._trt_half, cached_decision=cached))
        if self._trt_candidates:
            self._trt_candidates.pop(0)
        self._trt_blob = None
        self._trt_state = "next"
        self._trt_status = dict(self._trt_status, state="next", attempts=attempts)

    def _trial_trt(self, poser, image, pose_list, use_half: bool, T) -> None:
        engine = T.Tha4TrtEngine(self._trt_blob, self.device)
        base = numpy.asarray(pose_list, dtype=numpy.float32)
        index = min(_TRIAL_POSE_INDEX, base.shape[0] - 1)
        poses = []
        for step in range(GRAPH_TRIAL_FRAMES):
            test = base.copy()
            test[index] = float(numpy.clip(test[index] + 0.01 * (step - 2), -1.0, 1.0))
            poses.append(test.tolist())
        reference = [self._eager_copy(poser, image, p, False) for p in poses]
        accepted, candidate, eager_ms, trt_ms = [], [], [], []
        for p in poses:
            wall = time.perf_counter()
            accepted.append(self._eager_copy(poser, image, p, use_half))
            eager_ms.append((time.perf_counter() - wall) * 1000.0)
            wall = time.perf_counter()
            candidate.append(_postprocess(engine.launch(p).float()).cpu().numpy())
            trt_ms.append((time.perf_counter() - wall) * 1000.0)
        result = T.trial_gate(candidate, accepted, reference)
        result.update(eager_ms=round(statistics.median(eager_ms), 2),
                      trt_ms=round(statistics.median(trt_ms), 2),
                      engine_fp16=self._trt_half, user_fp16=use_half, gate_version=T.GATE_VERSION)
        if result["passed"] and result["trt_ms"] > result["eager_ms"]:
            result.update(passed=False, reason="TensorRT not faster than PyTorch")
        elif not result["passed"]:
            result["reason"] = "quality gate: worse than the PyTorch path vs FP32 reference"
        T.write_json(os.path.join(T.cache_dir(), self._trt_key + ".gate.json"), result)
        if not result["passed"]:
            self._trt_reject(result)
            return
        self._trt_engine, self._trt_blob = engine, None
        self._trt_state = "active"
        self._trt_status = dict(self._trt_status, state="active", **result)
