"""Output capture backend abstraction (how the transparent character output is
delivered to streaming/capture software).

This is the delivery axis, orthogonal to *what* fills the background (solid
color / image / transparent). Two backends are implemented today and one is
reserved:

- TRUE_TRANSPARENT_LAYERED: a per-pixel-alpha Win32 layered window
  (WS_EX_LAYERED + UpdateLayeredWindow / ULW_ALPHA). This is the primitive that
  OBS "Windows Graphics Capture (allow transparency)" / 抖音直播伴侣《透明画布》
  「游戏进程 + 允许窗口透明」and bongocat-style desktop overlays consume.
- COLOR_KEY: render the character on a pure-black canvas and let the capture
  tool chroma/color-key the background out. Universally compatible fallback
  (works with plain Window/Game capture that drops alpha).
- SPOUT2_NDI (reserved): GPU/texture or network video sharing. Out of scope
  here; declared so the abstraction and persisted value have a stable slot.

The runtime currently selects the delivery backend implicitly through the
output background mode dropdown ("透明" => layered ULW; "黑键" =>
color key). This module makes that mapping explicit, records the recommended
backend per capture tool, and resolves a persisted `output_capture_backend`
override so the choice survives restarts and can drive a future dedicated UI.
"""
from __future__ import annotations

from typing import Optional

OUTPUT_BACKEND_TRUE_TRANSPARENT = "true_transparent_layered"
OUTPUT_BACKEND_COLOR_KEY = "color_key"
OUTPUT_BACKEND_SPOUT_NDI = "spout2_ndi"

OUTPUT_BACKEND_VALUES = (
    OUTPUT_BACKEND_TRUE_TRANSPARENT,
    OUTPUT_BACKEND_COLOR_KEY,
    OUTPUT_BACKEND_SPOUT_NDI,
)

# Backends a user can actually select today (Spout/NDI is reserved).
OUTPUT_BACKEND_SELECTABLE = (
    OUTPUT_BACKEND_TRUE_TRANSPARENT,
    OUTPUT_BACKEND_COLOR_KEY,
)

OUTPUT_BACKEND_LABELS = {
    OUTPUT_BACKEND_TRUE_TRANSPARENT: "真透明分层窗 / True-transparent layered window",
    OUTPUT_BACKEND_COLOR_KEY: "色键(纯黑)窗 / Color-key (black) window",
    OUTPUT_BACKEND_SPOUT_NDI: "Spout2/NDI (预留 / reserved)",
}

# Capture tools and the backend we recommend for each.
CAPTURE_TOOL_OBS_WGC = "obs_wgc"
CAPTURE_TOOL_OBS_WINDOW = "obs_window_capture"
CAPTURE_TOOL_DOUYIN = "douyin_live_companion"
CAPTURE_TOOL_KUAISHOU = "kuaishou_live_assistant"

CAPTURE_TOOL_RECOMMENDATION = {
    CAPTURE_TOOL_OBS_WGC: (
        OUTPUT_BACKEND_TRUE_TRANSPARENT,
        "OBS 窗口/游戏捕获 (WGC) 勾选「允许透明」=> 真透明分层窗，无黑边。"),
    CAPTURE_TOOL_OBS_WINDOW: (
        OUTPUT_BACKEND_COLOR_KEY,
        "OBS 传统「窗口捕获(BitBlt)」不保留 alpha => 色键(纯黑)窗 + 颜色键滤镜。"),
    CAPTURE_TOOL_DOUYIN: (
        OUTPUT_BACKEND_TRUE_TRANSPARENT,
        "抖音直播伴侣《透明画布》「游戏进程 + 允许窗口透明」=> 真透明分层窗。"),
    CAPTURE_TOOL_KUAISHOU: (
        OUTPUT_BACKEND_COLOR_KEY,
        "快手直播助手窗口捕获多不保 alpha => 色键(纯黑)窗兜底最稳。"),
}

# Background-mode string -> delivery backend. Imported lazily by callers that
# already hold the OUTPUT_BACKGROUND_* constants to avoid a hard dependency.
_BACKGROUND_MODE_TO_BACKEND = {
    "transparent": OUTPUT_BACKEND_COLOR_KEY,
    "transparent_capture": OUTPUT_BACKEND_TRUE_TRANSPARENT,
    "color": OUTPUT_BACKEND_COLOR_KEY,
    "image": OUTPUT_BACKEND_COLOR_KEY,
}


def normalize_output_backend(value: Optional[str]) -> Optional[str]:
    if value in OUTPUT_BACKEND_VALUES:
        return value
    return None


def backend_for_background_mode(background_mode: Optional[str]) -> str:
    """Derive the delivery backend implied by an output background mode."""
    return _BACKGROUND_MODE_TO_BACKEND.get(
        str(background_mode), OUTPUT_BACKEND_TRUE_TRANSPARENT)


def resolve_output_backend(
        persisted_value: Optional[str],
        background_mode: Optional[str]) -> str:
    """Honor an explicit persisted `output_capture_backend` override, otherwise
    derive the backend from the active background mode."""
    explicit = normalize_output_backend(persisted_value)
    if explicit is not None:
        return explicit
    return backend_for_background_mode(background_mode)


def recommended_backend_for_tool(tool: str) -> Optional[str]:
    entry = CAPTURE_TOOL_RECOMMENDATION.get(tool)
    return entry[0] if entry is not None else None


def backend_label(backend: str) -> str:
    return OUTPUT_BACKEND_LABELS.get(backend, str(backend))
