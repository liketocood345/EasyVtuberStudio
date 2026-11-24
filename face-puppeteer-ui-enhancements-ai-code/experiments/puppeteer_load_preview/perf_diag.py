"""EVS-PERF 0.1: one switch for hot-path diagnostic file IO.

EVS_PERF_DIAG (read once at import) controls the per-second / throttled
debug NDJSON writers (1 Hz present snapshot, OSF/MediaPipe/transform probes).
Default ON (user decision 2026-11-24: "debug日志常开"); set EVS_PERF_DIAG=0
to turn them off. Cost when on, measured: ~0.31 ms per 1 Hz snapshot on the
UI thread plus throttled (>= 0.25 s) probe writes. Always-on regardless:
  - the e5 UI/infer watchdog (background thread, writes only on stalls),
  - display-gap >= 500 ms stall records,
  - longrun_diag's own switches (EVS_LONGRUN_DIAG, EVS_DIAG_TILT, ...).

All diagnostic files live in <portable root>/workspace/diagnostics and are
size-capped (EVS_DIAG_MAX_MB, default 16 MB; one rotated ".1" file).
"""
from __future__ import annotations

import os
import threading


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes", "on")


PERF_DIAG = os.environ.get("EVS_PERF_DIAG", "1").strip().lower() not in ("0", "false", "no", "off")

try:
    _MAX_BYTES = max(1, int(float(os.environ.get("EVS_DIAG_MAX_MB", "16")) * 2 ** 20))
except ValueError:
    _MAX_BYTES = 16 * 2 ** 20

_lock = threading.Lock()


def append_line(path: str, line: str, max_bytes: int = _MAX_BYTES) -> None:
    """Append one text line; rotate ``path`` to ``path + '.1'`` past max_bytes.

    Never raises into callers (diagnostics must not break the app).
    """
    try:
        with _lock:
            try:
                if os.path.getsize(path) >= max_bytes:
                    os.replace(path, path + ".1")
            except OSError:
                pass
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line if line.endswith("\n") else line + "\n")
    except Exception:
        pass
