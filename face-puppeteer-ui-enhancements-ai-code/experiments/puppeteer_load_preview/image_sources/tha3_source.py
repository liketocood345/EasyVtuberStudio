from __future__ import annotations

from typing import List, Optional

import wx

from image_sources.base import LoadUiSpec
from tha3_engine import Tha3Engine
from tha3_paths import IMAGE_SOURCE_THA3, tha3_inference_assets_available
from tha3_pose_adapter import mediapipe_pose_to_tha3_vector, neutral_tha3_pose


class Tha3Source:
    mode_id = IMAGE_SOURCE_THA3

    def __init__(self):
        self.engine: Optional[Tha3Engine] = None
        self.last_pose: Optional[List[float]] = None
        self._default_pose: Optional[List[float]] = None

    def start(self, main_frame) -> None:
        variant = getattr(main_frame, "tha3_model_variant", "separable_half")
        if not tha3_inference_assets_available(variant):
            self.engine = None
            return
        self.engine = Tha3Engine(main_frame.device, model_variant=variant)
        self._default_pose = neutral_tha3_pose(main_frame.pose_converter)
        self.last_pose = None

    def stop(self, main_frame) -> None:
        if self.engine is not None:
            self.engine.stop()
        self.engine = None
        self.last_pose = None
        self._default_pose = None
        main_frame.wx_source_image = None
        main_frame.last_output_wx_image = None
        main_frame.last_pose = None
        main_frame._load_preview_shown = False
        main_frame._invalidate_source_preview_cache()
        main_frame.update_source_image_bitmap(force=True)

    def is_ready(self, main_frame) -> bool:
        return self.engine is not None and self.engine.is_loaded()

    def load_asset(self, main_frame, path: str) -> bool:
        from tha3_assets_prompt import ensure_tha3_assets_available

        variant = getattr(main_frame, "tha3_model_variant", "separable_half")
        if not ensure_tha3_assets_available(main_frame, variant):
            return False
        if self.engine is None:
            self.start(main_frame)
        if self.engine is None:
            return False
        ok = self.engine.load_character_png(path)
        if not ok:
            message_dialog = wx.MessageDialog(
                main_frame.get_dialog_parent(),
                "THA3 立绘加载失败 / Failed to load THA3 PNG\n%s" % (self.engine.last_error or path),
                "Load THA3 PNG",
                wx.OK | wx.ICON_WARNING)
            message_dialog.ShowModal()
            message_dialog.Destroy()
            return False
        main_frame.last_tha3_character_png = path
        if hasattr(main_frame, "save_persistent_ui_state"):
            main_frame.save_persistent_ui_state()
        try:
            import PIL.Image

            pil = PIL.Image.open(path).convert("RGBA")
            if pil.size != (512, 512):
                pil = pil.resize((512, 512), PIL.Image.LANCZOS)
            main_frame.wx_source_image = wx.Bitmap.FromBufferRGBA(512, 512, pil.tobytes())
        except Exception:
            main_frame.wx_source_image = None
        main_frame._invalidate_source_preview_cache()
        main_frame.update_source_image_bitmap(force=True)
        default_pose = self._default_pose or neutral_tha3_pose(main_frame.pose_converter)
        wx_image = self.engine.render_pose(default_pose)
        if wx_image is not None:
            main_frame.last_output_wx_image = wx_image
            main_frame.last_pose = default_pose
            main_frame.draw_result_wx_image(
                wx_image,
                main_frame.LOAD_PREVIEW_BANNER,
                fast_affine_only=not main_frame.is_layer_blend_enabled())
            main_frame._load_preview_shown = True
        main_frame.save_persistent_ui_state()
        if hasattr(main_frame, "refresh_basic_layer_window_if_visible"):
            main_frame.refresh_basic_layer_window_if_visible()
        if hasattr(main_frame, "maybe_open_region_wobble_after_character_load"):
            main_frame.maybe_open_region_wobble_after_character_load()
        return True

    def tick(self, main_frame) -> Optional[str]:
        if self.engine is None or not self.engine.is_loaded():
            return "no_model"

        display_transform_changed = main_frame.update_display_transform_state()
        if main_frame.mediapipe_face_pose is None:
            if display_transform_changed and main_frame.last_output_wx_image is not None:
                main_frame.draw_cached_result_image(main_frame.last_banner_text)
            return "no_face"

        current_pose = mediapipe_pose_to_tha3_vector(
            main_frame.mediapipe_face_pose,
            main_frame.pose_converter,
        )
        current_pose = main_frame.apply_negative_tilt_limit_to_pose(current_pose)
        current_pose = main_frame.apply_invert_tilt_mapping_to_pose(current_pose)
        pose_changed = self.last_pose is None or self.last_pose != current_pose
        background_changed = main_frame.last_background_choice != main_frame.get_output_background_signature()

        if not pose_changed and main_frame.last_output_wx_image is not None and not background_changed:
            if display_transform_changed:
                main_frame.draw_cached_result_image(main_frame.last_banner_text)
            return "cached"

        wx_image = self.engine.render_pose(current_pose)
        if wx_image is None:
            return "render_failed"

        self.last_pose = current_pose
        main_frame.last_pose = current_pose
        main_frame.last_output_wx_image = wx_image
        main_frame.last_background_choice = main_frame.get_output_background_signature()
        main_frame.output_enhancement.pose_interpolation.seed_after_real_infer(current_pose)
        main_frame.draw_result_wx_image(
            wx_image,
            None,
            fast_affine_only=not main_frame.is_layer_blend_enabled())
        main_frame._note_inference_fps_tick()
        return "rendered"

    def get_load_ui_spec(self) -> LoadUiSpec:
        return LoadUiSpec(
            show_yaml_loader=False,
            show_png_loader=True,
            show_tha3_variant=True,
            status_hint="THA3：512 RGBA 立绘即用，实时占用更高 / PNG ready, heavier runtime",
        )
