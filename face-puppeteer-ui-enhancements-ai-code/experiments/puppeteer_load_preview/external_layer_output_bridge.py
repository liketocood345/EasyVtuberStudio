"""
Reserved bridge for an external layer compositor process.

THA4 Load Preview writes frame metadata (and optional future pixel buffers) here
when the user enables "Output to external layer system" in the postprocess panel.
The built-in borderless OutputFrame is hidden while this mode is active.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import wx

FRAME_CONTRACT_VERSION = 1
STATUS_FILE_NAME = "status.json"
CONTRACT_FILE_NAME = "contract.json"


class ExternalLayerOutputBridge:
    """Local filesystem bridge; replace/extend with shared memory or IPC later."""

    SUBDIR_NAME = "external_layer_output"

    @classmethod
    def get_bridge_directory(cls, main_frame: "MainFrame") -> str:
        base_dir = os.path.dirname(main_frame.get_ui_state_file_path())
        return os.path.join(base_dir, cls.SUBDIR_NAME)

    @classmethod
    def ensure_bridge_directory(cls, main_frame: "MainFrame") -> str:
        bridge_dir = cls.get_bridge_directory(main_frame)
        os.makedirs(bridge_dir, exist_ok=True)
        return bridge_dir

    @classmethod
    def get_frame_contract(cls, main_frame: "MainFrame") -> dict[str, Any]:
        width, height = main_frame.get_locked_output_client_size()
        return {
            "contract_version": FRAME_CONTRACT_VERSION,
            "pixel_format": "rgba8",
            "width": width,
            "height": height,
            "coordinate_space": "output_canvas_bottom_center_anchor",
            "anchor_payload_version": 1,
            "notes": (
                "Pixel buffer export is not wired yet; external compositor should "
                "read status.json and wait for frame_rgba_path or shared-memory fields."
            ),
        }

    @classmethod
    def _extract_anchor_payload(cls, main_frame: "MainFrame") -> dict[str, Any]:
        latest = getattr(main_frame, "latest_face_screen_motion", None)
        neutral = getattr(main_frame, "neutral_face_screen_motion", None)
        return {
            "latest_face_anchor": None if latest is None else {
                "center_x": float(latest.center_x),
                "center_y": float(latest.center_y),
                "face_size": float(latest.face_size),
            },
            "neutral_face_anchor": None if neutral is None else {
                "center_x": float(neutral.center_x),
                "center_y": float(neutral.center_y),
                "face_size": float(neutral.face_size),
            },
            "latest_head_roll_deg": getattr(main_frame, "latest_head_roll_deg", None),
            "neutral_head_roll_deg": float(getattr(main_frame, "neutral_head_roll_deg", 0.0)),
            "last_direction_calibration_time": getattr(main_frame, "last_direction_calibration_time", None),
            "last_scale_calibration_time": getattr(main_frame, "last_scale_calibration_time", None),
        }

    @classmethod
    def write_contract_file(cls, main_frame: "MainFrame") -> str:
        bridge_dir = cls.ensure_bridge_directory(main_frame)
        contract_path = os.path.join(bridge_dir, CONTRACT_FILE_NAME)
        with open(contract_path, "w", encoding="utf-8") as fp:
            json.dump(cls.get_frame_contract(main_frame), fp, ensure_ascii=True, indent=2)
        return contract_path

    @classmethod
    def publish_composite_frame(
            cls,
            main_frame: "MainFrame",
            *,
            frame_sequence: int,
            banner_text: Optional[str] = None) -> bool:
        """
        Publish the latest composed frame metadata for an external compositor.

        Returns True when status.json was written. RGBA file export is reserved
        for a later layer-runtime milestone.
        """
        if not main_frame.is_external_layer_output_enabled():
            return False

        bridge_dir = cls.ensure_bridge_directory(main_frame)
        width, height = main_frame.get_locked_output_client_size()
        status = {
            "enabled": True,
            "contract_version": FRAME_CONTRACT_VERSION,
            "frame_sequence": frame_sequence,
            "timestamp_ms": int(time.time() * 1000),
            "width": width,
            "height": height,
            "background_hex": main_frame.get_output_background_hex(),
            "mirror_output": bool(main_frame.mirror_output_checkbox.GetValue()),
            "display_scale": float(main_frame.display_scale),
            "display_offset_x": float(main_frame.display_offset_x),
            "display_offset_y": float(main_frame.display_offset_y),
            "display_rotation_deg": float(main_frame.display_rotation_deg),
            "banner_text": banner_text,
            "anchor_payload": cls._extract_anchor_payload(main_frame),
            "frame_rgba_path": None,
            "layer_state_path": None,
        }
        status_path = os.path.join(bridge_dir, STATUS_FILE_NAME)
        with open(status_path, "w", encoding="utf-8") as fp:
            json.dump(status, fp, ensure_ascii=True, indent=2)
        return True

    @classmethod
    def clear_bridge_status(cls, main_frame: "MainFrame") -> None:
        status_path = os.path.join(cls.get_bridge_directory(main_frame), STATUS_FILE_NAME)
        if os.path.isfile(status_path):
            try:
                os.remove(status_path)
            except OSError:
                pass


# Late import alias for type hints only at runtime.
MainFrame = Any  # noqa: N816 — avoids circular import with puppeteer script
