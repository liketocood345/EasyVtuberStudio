"""Smoke tests for the output capture backend abstraction (no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

EXPERIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(EXPERIMENT_DIR))

from output_backends import (
    CAPTURE_TOOL_DOUYIN,
    CAPTURE_TOOL_KUAISHOU,
    CAPTURE_TOOL_OBS_WGC,
    CAPTURE_TOOL_OBS_WINDOW,
    OUTPUT_BACKEND_COLOR_KEY,
    OUTPUT_BACKEND_SPOUT_NDI,
    OUTPUT_BACKEND_TRUE_TRANSPARENT,
    backend_for_background_mode,
    backend_label,
    normalize_output_backend,
    recommended_backend_for_tool,
    resolve_output_backend,
)


def test_background_mode_mapping() -> None:
    assert backend_for_background_mode("transparent_capture") == OUTPUT_BACKEND_TRUE_TRANSPARENT
    assert backend_for_background_mode("transparent") == OUTPUT_BACKEND_COLOR_KEY
    assert backend_for_background_mode("color") == OUTPUT_BACKEND_COLOR_KEY
    assert backend_for_background_mode("image") == OUTPUT_BACKEND_COLOR_KEY
    # unknown defaults to true transparent
    assert backend_for_background_mode("???") == OUTPUT_BACKEND_TRUE_TRANSPARENT


def test_normalize_and_resolve() -> None:
    assert normalize_output_backend(OUTPUT_BACKEND_COLOR_KEY) == OUTPUT_BACKEND_COLOR_KEY
    assert normalize_output_backend("bogus") is None
    # explicit persisted override wins
    assert resolve_output_backend(
        OUTPUT_BACKEND_COLOR_KEY, "transparent_capture") == OUTPUT_BACKEND_COLOR_KEY
    # no override -> derive from background mode
    assert resolve_output_backend(None, "transparent_capture") == OUTPUT_BACKEND_TRUE_TRANSPARENT
    assert resolve_output_backend("bogus", "transparent") == OUTPUT_BACKEND_COLOR_KEY


def test_tool_recommendations() -> None:
    assert recommended_backend_for_tool(CAPTURE_TOOL_OBS_WGC) == OUTPUT_BACKEND_TRUE_TRANSPARENT
    assert recommended_backend_for_tool(CAPTURE_TOOL_DOUYIN) == OUTPUT_BACKEND_TRUE_TRANSPARENT
    assert recommended_backend_for_tool(CAPTURE_TOOL_OBS_WINDOW) == OUTPUT_BACKEND_COLOR_KEY
    assert recommended_backend_for_tool(CAPTURE_TOOL_KUAISHOU) == OUTPUT_BACKEND_COLOR_KEY
    assert recommended_backend_for_tool("unknown_tool") is None


def test_labels_present() -> None:
    for backend in (
            OUTPUT_BACKEND_TRUE_TRANSPARENT,
            OUTPUT_BACKEND_COLOR_KEY,
            OUTPUT_BACKEND_SPOUT_NDI):
        assert isinstance(backend_label(backend), str) and backend_label(backend)


def main() -> None:
    test_background_mode_mapping()
    test_normalize_and_resolve()
    test_tool_recommendations()
    test_labels_present()
    print("smoke_output_backends_ok")


if __name__ == "__main__":
    main()
