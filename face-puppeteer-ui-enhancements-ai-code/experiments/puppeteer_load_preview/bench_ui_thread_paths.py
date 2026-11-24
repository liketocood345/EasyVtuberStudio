"""Before/after micro-benchmarks for EVS-PERF Phase 0/1/2 changes (2026-11-24).

Each case runs the former implementation (copied verbatim below) and the
current one on the same input, checks the outputs are identical, and reports
median ms per call. Run from the develop root:
  runtime\\venv\\Scripts\\python.exe face-puppeteer-ui-enhancements-ai-code\\experiments\\puppeteer_load_preview\\bench_ui_thread_paths.py
"""
from __future__ import annotations

import gc
import json
import os
import statistics
import sys
import tempfile
import threading
import time

import cv2
import numpy

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)


def median_ms(fn, repeat=200, rounds=7, warmup=20):
    for _ in range(warmup):
        fn()
    samples = []
    for _ in range(rounds):
        start = time.perf_counter()
        for _ in range(repeat):
            fn()
        samples.append((time.perf_counter() - start) / repeat * 1000.0)
    return statistics.median(samples)


def row(name, before, after, identical, note=""):
    print("%-44s %9.3f %9.3f %7.2fx  %-9s %s" % (
        name, before, after, before / after if after > 0 else float("inf"),
        "identical" if identical is True else ("n/a" if identical is None else "DIFF"), note))
    return {"case": name, "before_ms": round(before, 4), "after_ms": round(after, 4),
            "identical": identical, "note": note}


# ------------------------------------------------------------ former code
def preview_before(bgr, pw, ph, mirror=True):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    if mirror:
        rgb = cv2.flip(rgb, 1)
    h, w = rgb.shape[:2]
    s = min(pw / w, ph / h)
    return cv2.resize(rgb, (max(1, int(round(w * s))), max(1, int(round(h * s)))), interpolation=cv2.INTER_AREA)


def preview_after(bgr, pw, ph, mirror=True):
    h, w = bgr.shape[:2]
    if mirror:
        bgr = cv2.flip(bgr, 1)
    s = min(pw / w, ph / h)
    return cv2.cvtColor(cv2.resize(bgr, (max(1, int(round(w * s))), max(1, int(round(h * s)))),
                                   interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2RGB)


def premultiply_before(rgba):
    bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
    b, g, r, a = cv2.split(bgra)
    b = cv2.multiply(b, a, scale=1.0 / 255.0)
    g = cv2.multiply(g, a, scale=1.0 / 255.0)
    r = cv2.multiply(r, a, scale=1.0 / 255.0)
    return cv2.merge([b, g, r, a])


def tha3_ui_before(bgra):
    rgb = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)          # _numpy_rgba_to_wx_image
    data, alpha = rgb[:, :, 0:3].tobytes(), rgb[:, :, 3].tobytes()
    last = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)          # _last_tha3_rgba
    return data, alpha, last


def tha3_ui_after(rgba):  # rgba converted once on the worker; contiguous extraction
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB).tobytes(), cv2.extractChannel(rgba, 3).tobytes(), rgba


def tha4_wx_bytes_before(rgba):
    return rgba[:, :, 0:3].tobytes(), rgba[:, :, 3].tobytes()


def tha4_wx_bytes_after(rgba):
    return cv2.cvtColor(rgba, cv2.COLOR_RGBA2RGB).tobytes(), cv2.extractChannel(rgba, 3).tobytes()


def main() -> int:
    from rgba_capture_compose import _straight_rgba_to_premultiplied_bgra as premultiply_after
    rng = numpy.random.default_rng(7)
    results = []
    print("%-44s %9s %9s %8s  %-9s" % ("case (UI thread unless noted)", "before", "after", "speedup", "output"))

    cam = cv2.GaussianBlur(rng.integers(0, 256, (720, 1280, 3), dtype=numpy.uint8), (0, 0), 3)
    same = all(numpy.array_equal(preview_before(cam, s, s, m), preview_after(cam, s, s, m))
               for s in (160, 192, 240) for m in (True, False))
    results.append(row("1.2 camera preview 1280x720 -> 192",
                       median_ms(lambda: preview_before(cam, 192, 192)),
                       median_ms(lambda: preview_after(cam, 192, 192)), same))
    results.append(row("1.2 read_capture_frame_bgr defensive copy",
                       median_ms(lambda: cam.copy()), median_ms(lambda: cam), None, "copy removed"))

    frame = rng.integers(0, 256, (768, 768, 4), dtype=numpy.uint8)
    c = numpy.repeat(numpy.arange(256, dtype=numpy.uint8), 256)
    a = numpy.tile(numpy.arange(256, dtype=numpy.uint8), 256)
    exhaustive = numpy.stack([c, 255 - c, c // 2 + 7, a], axis=1).reshape(256, 256, 4).copy()
    same = (numpy.array_equal(premultiply_before(frame), premultiply_after(frame))
            and numpy.array_equal(premultiply_before(exhaustive), premultiply_after(exhaustive)))
    results.append(row("2.3 premultiply 768^2 (presenter thread)",
                       median_ms(lambda: premultiply_before(frame)),
                       median_ms(lambda: premultiply_after(frame)), same))
    premul = premultiply_after(frame)
    results.append(row("2.3 ULW post: 2 defensive copies 768^2",
                       median_ms(lambda: (numpy.array(frame, dtype=numpy.uint8, order="C", copy=True),
                                          numpy.array(premul, dtype=numpy.uint8, order="C", copy=True))),
                       median_ms(lambda: (numpy.array(frame, dtype=numpy.uint8, order="C", copy=False),
                                          numpy.array(premul, dtype=numpy.uint8, order="C", copy=False))),
                       None, "owned=True on live-scene path"))

    bgra = rng.integers(0, 256, (512, 512, 4), dtype=numpy.uint8)
    rgba = cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)
    before_out, after_out = tha3_ui_before(bgra), tha3_ui_after(rgba)
    same = before_out[0] == after_out[0] and before_out[1] == after_out[1] and numpy.array_equal(before_out[2], after_out[2])
    results.append(row("1.5 THA3 result -> wx bytes + RGBA (per infer)",
                       median_ms(lambda: tha3_ui_before(bgra)), median_ms(lambda: tha3_ui_after(rgba)), same,
                       "cvtColor to worker + contiguous bytes"))
    results.append(row("1.5 THA4 wx bytes (infer worker, in lock)",
                       median_ms(lambda: tha4_wx_bytes_before(rgba)), median_ms(lambda: tha4_wx_bytes_after(rgba)),
                       tha4_wx_bytes_before(rgba) == tha4_wx_bytes_after(rgba), "per inference frame"))

    # 0.1/1.1: the 1 Hz snapshot's IO-side work (thread list, gc, RSS, JSON, file append).
    import character_model_mediapipe_puppeteer_load_preview as main_mod
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "snap.log")
        payload = {k: 1.0 for k in range(40)}

        def snapshot_io():
            names = [t.name for t in threading.enumerate()][:16]
            data = dict(payload, threads=names, gc=list(gc.get_count()), rss=main_mod._e5_rss_mb())
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(data) + "\n")
        results.append(row("0.1 1 Hz present snapshot (IO part, per call)",
                           median_ms(snapshot_io, repeat=100), median_ms(lambda: None, repeat=100), None,
                           "skipped unless EVS_PERF_DIAG=1"))

    from portable_process_env import debug_log_path
    import portable_process_env as ppe
    saved = ppe._DIAG_DIRECTORY

    def debug_path_before():
        directory = ppe.root_from_source() / "workspace/diagnostics"
        directory.mkdir(parents=True, exist_ok=True)
        return str(directory / "debug-x.log")
    results.append(row("0.1 debug_log_path() per call",
                       median_ms(debug_path_before, repeat=100), median_ms(lambda: debug_log_path("x")), None,
                       "mkdir once"))
    ppe._DIAG_DIRECTORY = saved

    # 1.6: MediaPipe detect worker: new thread per frame vs lingering worker.
    def spawn_join():
        t = threading.Thread(target=lambda: None)
        t.start()
        t.join()
    cond = threading.Condition()
    box = {"job": None, "done": threading.Event(), "stop": False}

    def linger():
        while True:
            with cond:
                while box["job"] is None and not box["stop"]:
                    cond.wait(1.0)
                if box["stop"]:
                    return
                box["job"] = None
            box["done"].set()
    worker = threading.Thread(target=linger, daemon=True)
    worker.start()

    def handoff():
        box["done"].clear()
        with cond:
            box["job"] = 1
            cond.notify_all()
        box["done"].wait()
    results.append(row("1.6 MediaPipe job dispatch (per frame)",
                       median_ms(spawn_join, repeat=100), median_ms(handoff, repeat=100), None,
                       "thread start+exit vs Condition handoff"))
    with cond:
        box["stop"] = True
        cond.notify_all()

    # 1.3: three read-only TextCtrl updates per detection (30 Hz -> <= 10 Hz).
    import wx
    app = wx.App(False)
    frame_wx = wx.Frame(None)
    controls = [wx.TextCtrl(frame_wx) for _ in range(3)]
    for ctrl in controls:
        ctrl.Disable()
    counter = [0]

    def update_three():
        counter[0] += 1
        for i, ctrl in enumerate(controls):
            text = "%0.2f" % (counter[0] * 0.37 + i)
            if ctrl.GetValue() != text:
                ctrl.ChangeValue(text)
    per_call = median_ms(update_three, repeat=100)
    results.append(row("1.3 head-angle TextCtrls, ms per second",
                       per_call * 30.0, per_call * 10.0, None, "30 Hz -> <=10 Hz"))
    frame_wx.Destroy()
    app.Destroy()

    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_HERE))), "workspace", "diagnostics")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "bench_ui_thread_paths_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    with open(out_path, "w", encoding="utf-8") as fout:
        json.dump({"time": time.strftime("%Y-%m-%dT%H:%M:%S"), "results": results}, fout, ensure_ascii=False, indent=2)
    print("\nreport:", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
