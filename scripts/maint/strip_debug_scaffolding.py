#!/usr/bin/env python3
"""One-shot: remove longrun / NDJSON agent-log scaffolding from preview modules."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PREVIEW = ROOT / "face-puppeteer-ui-enhancements-ai-code" / "experiments" / "puppeteer_load_preview"

for name in (
    "longrun_freeze_debug.py",
    "longrun_watchdog.py",
    "smoke_longrun_freeze_debug.py",
):
    path = PREVIEW / name
    if path.is_file():
        path.unlink()
        print("deleted", path)

main_py = PREVIEW / "character_model_mediapipe_puppeteer_load_preview.py"
text = main_py.read_text(encoding="utf-8")

# Drop longrun import.
text = text.replace("import longrun_freeze_debug\n", "")

# Remove agent-log block (perf / startup / err / excepthook).
text = re.sub(
    r"\n_PERF_LOG_PATH = r.*?# #endregion\n",
    "\n",
    text,
    count=1,
    flags=re.DOTALL,
)

# Remove _recover_from_external_ui_freeze (only wired from longrun pulse).
text = re.sub(
    r"\n    def _recover_from_external_ui_freeze\(self\).*?"
    r"data=longrun_freeze_debug\.collect_pipeline_snapshot\(self\)\)\n",
    "\n",
    text,
    count=1,
    flags=re.DOTALL,
)

# Timer + heartbeat for longrun debug.
text = re.sub(
    r"\n        self\.longrun_debug_timer = wx\.Timer\(self, wx\.ID_ANY\)\n"
    r"        self\.Bind\(\n"
    r"            wx\.EVT_TIMER,\n"
    r"            self\.on_longrun_debug_heartbeat,\n"
    r"            id=self\.longrun_debug_timer\.GetId\(\)\)\n",
    "\n",
    text,
    count=1,
)

text = re.sub(
    r"\n    def on_longrun_debug_heartbeat\(self, event: Optional\[wx\.Event\] = None\) -> None:\n"
    r"        if getattr\(self, \"_is_closing\", False\):\n"
    r"            return\n"
    r"        longrun_freeze_debug\.maybe_heartbeat\(self\)\n",
    "\n",
    text,
    count=1,
)

# Startup longrun hooks.
text = re.sub(
    r"\n        _startup_record\(\n"
    r"            \"startup_show_full_controls \(UI ready\)\",\n"
    r"            \(time\.perf_counter\(\) - startup_t0\) \* 1000\.0\)\n"
    r"        longrun_freeze_debug\.session_start\(self\)\n"
    r"        longrun_freeze_debug\.register_freeze_recovery\(\n"
    r"            lambda: wx\.CallAfter\(self\._recover_from_external_ui_freeze\)\)\n",
    "\n",
    text,
    count=1,
)

text = text.replace("        longrun_freeze_debug.shutdown()\n", "")

# Strip all longrun_freeze_debug call lines (single-line statements).
text = re.sub(r"^        longrun_freeze_debug\.[^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^                longrun_freeze_debug\.[^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^                    longrun_freeze_debug\.[^\n]+\n", "", text, flags=re.MULTILINE)
text = re.sub(r"^                        longrun_freeze_debug\.[^\n]+\n", "", text, flags=re.MULTILINE)

# Multi-line longrun calls (note_infer_worker with extra=).
text = re.sub(
    r"                        longrun_freeze_debug\.note_infer_worker\(\n"
    r"                            self, \"error\", generation=generation,\n"
    r"                            extra=\{\"error\": repr\(exc\)\}\)\n",
    "",
    text,
    count=1,
)

# Camera slow-read block used longrun constant.
text = re.sub(
    r"\n                elapsed = time\.perf_counter\(\) - start\n"
    r"                if elapsed >= longrun_freeze_debug\.CAMERA_READ_SLOW_SEC:\n"
    r"                    longrun_freeze_debug\.note_camera_capture_slow\(\n"
    r"                        self, elapsed_sec=elapsed\)\n",
    "\n                elapsed = time.perf_counter() - start",
    text,
    count=1,
)

# _startup_record calls.
text = re.sub(r"^        _startup_record\([^\)]*\)[^\n]*\n(?:            [^\n]*\n)*", "", text, flags=re.MULTILINE)
text = re.sub(r"^        _startup_record\([^\n]+\n[^\n]+\n[^\n]+\n", "", text, flags=re.MULTILINE)

# _perf_record calls.
text = re.sub(
    r"                _perf_record\(capture_ms=\(time\.perf_counter\(\) - capture_t0\) \* 1000\.0\)\n",
    "",
    text,
)
text = re.sub(
    r"            _perf_record\(capture_ms=\(time\.perf_counter\(\) - capture_t0\) \* 1000\.0\)\n",
    "",
    text,
)
text = re.sub(
    r"        _perf_record\(\n"
    r"            present_ms=\(time\.perf_counter\(\) - present_t0\) \* 1000\.0,\n"
    r"            fast_present=fast_affine_only,\n"
    r"            stages=getattr\(self, \"_last_present_stages\", None\)\)\n",
    "",
    text,
    count=1,
)

# _err_record -> stderr print (load paths keep user dialog).
_err_simple = (
    '            print(f"ERR {location}: {exc!r}", file=sys.stderr)\n'
)
text = text.replace(
    "            _err_record(\n"
    '                "H-CAP",\n'
    '                "character_model_mediapipe_puppeteer_load_preview.py:_push_transparent_capture_from_cache",\n'
    "                exc)",
    '            print(\n'
    '                "ERR capture push:", exc, file=sys.stderr)',
)
for block in (
    ('                "H-CAP",\n'
     '                "character_model_mediapipe_puppeteer_load_preview.py:_async_premultiply_and_deliver",\n'
     "                exc)"),
    ('                "H-CAP",\n'
     '                "character_model_mediapipe_puppeteer_load_preview.py:_finish_ulw_delivery",\n'
     "                exc)"),
    ('                "H-CAP",\n'
     '                "character_model_mediapipe_puppeteer_load_preview.py:_deliver_capture_premultiplied",\n'
     "                exc)"),
    ('                            "H-WINCAP",\n'
     '                            "character_model_mediapipe_puppeteer_load_preview.py:_window_capture_worker",\n'
     "                            exc,\n"
     '                            data={"hwnd": hwnd})'),
    ('                "H-LOAD",\n'
     '                "character_model_mediapipe_puppeteer_load_preview.py:render_default_pose_load_preview",\n'
     "                exc)"),
):
    text = text.replace(f"            _err_record(\n{block}", '            print(f"ERR: {exc!r}", file=sys.stderr)')

text = re.sub(
    r"            _err_record\(\n"
    r'                "H-LOAD",\n'
    r'                "character_model_mediapipe_puppeteer_load_preview.py:load_model_from_path",\n'
    r"                exc,\n"
    r'                data=\{"model_path": resolved_path\}\)\n',
    '            print(f"ERR load model: {exc!r}", file=sys.stderr)\n',
    text,
    count=1,
)

# Main entry: excepthook + startup + longrun timer start.
text = text.replace("        _install_debug_excepthook()\n", "")
text = re.sub(
    r"\n        _startup_record\(\n"
    r'            "main \(imports done, before MainFrame\)",\n'
    r"            \(time\.perf_counter\(\) - _main_t0\) \* 1000\.0\)\n",
    "\n",
    text,
    count=1,
)
text = re.sub(
    r"\n        main_frame\.longrun_debug_timer\.Start\(\n"
    r"            int\(longrun_freeze_debug\.HEARTBEAT_INTERVAL_SEC \* 1000\)\)\n",
    "\n",
    text,
    count=1,
)

# Remaining _startup_record in constructor.
text = re.sub(
    r"\n        _startup_record\(\n"
    r'            "MainFrame\.__init__ \(constructor, before MainLoop\)",\n'
    r"            \(time\.perf_counter\(\) - self\._startup_init_t0\) \* 1000\.0\)\n",
    "\n",
    text,
    count=1,
)

# Other _startup_record (model load milestones) — grep leftovers.
text = re.sub(
    r"^            _startup_record\([^\n]+\n(?:                [^\n]+\n)*",
    "",
    text,
    flags=re.MULTILINE,
)
text = re.sub(
    r"^        _startup_record\([^\n]+\n(?:            [^\n]+\n)*",
    "",
    text,
    flags=re.MULTILINE,
)

if "longrun_freeze_debug" in text or "_startup_record" in text or "_perf_record" in text:
    for i, line in enumerate(text.splitlines(), 1):
        if any(k in line for k in ("longrun_freeze_debug", "_startup_record", "_perf_record", "_err_record")):
            print(f"WARN leftover line {i}: {line[:100]}")

main_py.write_text(text, encoding="utf-8")
print("updated", main_py)

# transparent_capture_window.py
tcw = PREVIEW / "transparent_capture_window.py"
tcw_text = tcw.read_text(encoding="utf-8")
tcw_text = re.sub(
    r"\n_DEBUG_ERR_LOG_PATH = r.*?# #endregion\n",
    "\n",
    tcw_text,
    count=1,
    flags=re.DOTALL,
)
tcw_text = tcw_text.replace("            _capture_window_err_record(", "            # ")
tcw_text = re.sub(
    r"                    _capture_window_err_record\(\n"
    r'                        "transparent_capture_window\.py:_UlwWindowHost\.frame",\n'
    r"                        exc\)\n",
    "",
    tcw_text,
)
tcw_text = re.sub(
    r"                _capture_window_err_record\(\n"
    r'                    f"transparent_capture_window\.py:_UlwWindowHost\.\{op\}",\n'
    r"                    exc\)\n",
    "",
    tcw_text,
)
tcw_text = tcw_text.replace(
    '_capture_window_err_record("transparent_capture_window.py:update_frame_rgba", exc)',
    'print(f"ERR update_frame_rgba: {exc!r}", file=__import__("sys").stderr)',
)
if "_capture_window_err_record" in tcw_text:
    print("WARN transparent_capture_window leftovers")
tcw.write_text(tcw_text, encoding="utf-8")
print("updated", tcw)
