"""Unified output enhancement runtime: pose interp, SSAA, NN post-compose."""
from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

from typing import Any, Dict, Optional

import numpy as np

from output_enhancement.antialiasing import KeyframeRenderCache
from output_enhancement.pipeline import EnhancementPipeline
from output_enhancement.pose_interpolation import PoseInterpolationController


# EVS-DESIGN-AUDIT EVS-A077 BEGIN
# 设计[f-055, f-056, f-064] [符合（核查接口）]
# 有 pose interpolation、keyframe cache 与 NN facade；get_config_snapshot / nn_runtime_ready 委托 pipeline。frame_source_tag 仅内部属性，不等于 f-061 文字 HUD 已实现。
# 历史 bug 热点 #1,#2：f-064 监视器不再因缺方法被跳过。
# EVS-DESIGN-AUDIT EVS-A077 END
class OutputEnhancementRuntime:
    """Facade used by MainFrame for all output-quality enhancement paths."""

    def __init__(self, repo_root: Optional[str] = None):
        self.pipeline = EnhancementPipeline(repo_root=repo_root)
        self.pose_interpolation = PoseInterpolationController()
        self.keyframe_cache = KeyframeRenderCache()

    # --- NN post-compose pipeline delegates ---
    @property
    def frame_source_tag(self):
        return self.pipeline.frame_source_tag

    def update_config(self, persistence: Optional[Dict[str, Any]]) -> None:
        self.pipeline.update_config(persistence)

    def is_active(self) -> bool:
        return self.pipeline.is_active()

    def nn_modes_requested(self) -> bool:
        return self.pipeline.nn_modes_requested()

    # （f-064 NN 核查接口）26.10.29 19:40 s
    def get_config_snapshot(self) -> Dict[str, Any]:
        return self.pipeline.get_config_snapshot()
    # （f-064 NN 核查接口）26.10.29 19:40 e

    # bh-1 26.10.29 20:24 s
    def nn_runtime_ready(self) -> bool:
        return self.pipeline.nn_runtime_ready()
    # bh-1 26.10.29 20:24 e

    def apply(self, rgba: np.ndarray, *, is_new_real_frame: bool = True) -> np.ndarray:
        return self.pipeline.apply(rgba, is_new_real_frame=is_new_real_frame)

    def pop_rife_frame(self) -> Optional[np.ndarray]:
        return self.pipeline.pop_rife_frame()

    def has_pending_rife(self) -> bool:
        return self.pipeline.has_pending_rife()

    def target_frame_rate_enabled(self):
        return self.pipeline.target_frame_rate_enabled()

    def target_frame_rate_snapshot(self):
        return self.pipeline.target_frame_rate_snapshot()

    def observe_composition(self, elapsed_ms):
        return self.pipeline.observe_composition(elapsed_ms)

    def set_scene_output_rate(self, hz, *, independent=False):
        return self.pipeline.set_scene_output_rate(hz, independent=independent)

    def offer_character_for_calibration(self, rgba):
        return self.pipeline.offer_character_for_calibration(rgba)

    def set_frame_transformer(self, transformer):
        return self.pipeline.set_frame_transformer(transformer)

    def set_output_callback(self, callback):
        return self.pipeline.set_output_callback(callback)

    def set_buffered_enabled(self, enabled):
        return self.pipeline.set_buffered_enabled(enabled)

    def should_compose_source_frame(self, now=None):
        return self.pipeline.should_compose_source_frame(now)

    def buffered_rife_requested(self):
        return self.pipeline.buffered_rife_requested()

    def is_buffered_rife_active(self):
        return self.pipeline.is_buffered_rife_active()

    def get_source_rate_limit_hz(self):
        return self.pipeline.get_source_rate_limit_hz()

    def get_model_rate_limit_hz(self):
        return self.pipeline.get_model_rate_limit_hz()

    @property
    def last_error(self):
        return self.pipeline.last_error

    def warmup(self, progress=None) -> None:
        self.pipeline.warmup(progress)

    def shutdown(self) -> None:
        self.pipeline.shutdown()
        self.pose_interpolation.reset()
        self.keyframe_cache.clear()
