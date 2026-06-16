"""Unified output enhancement runtime: pose interp, SSAA, NN post-compose."""
from __future__ import annotations

from typing import Any, Dict, Optional

import numpy as np

from output_enhancement.antialiasing import KeyframeRenderCache
from output_enhancement.pipeline import EnhancementPipeline
from output_enhancement.pose_interpolation import PoseInterpolationController


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

    def apply(self, rgba: np.ndarray, *, is_new_real_frame: bool = True) -> np.ndarray:
        return self.pipeline.apply(rgba, is_new_real_frame=is_new_real_frame)

    def pop_rife_frame(self) -> Optional[np.ndarray]:
        return self.pipeline.pop_rife_frame()

    def has_pending_rife(self) -> bool:
        return self.pipeline.has_pending_rife()

    def warmup(self, progress=None) -> None:
        self.pipeline.warmup(progress)

    def shutdown(self) -> None:
        self.pipeline.shutdown()
        self.pose_interpolation.reset()
        self.keyframe_cache.clear()
