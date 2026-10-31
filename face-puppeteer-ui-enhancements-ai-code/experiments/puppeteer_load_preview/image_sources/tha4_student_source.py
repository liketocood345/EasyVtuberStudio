from __future__ import annotations
# EVS-DESIGN-AUDIT FILE BEGIN
# 设计手册: E:/record/easyvtuberstudio条目设计手册.md
# 提示词证据: E:/record/easyvtuberstudio-prompt-index.json -> entries[id].adopt/resolution/gap；按属性采用最近一次明确说明。
# 2026-10-29 只加注释。静态符合仅指注释限定的局部；待测不等于通过；非运行条目不伪装成功能。
# 历史热点: 本仓 docs/BUG_HOTSPOT_CHECKLIST.md（实际六项）；诊断: E:/EasyVtuberStudio-analysis-2026-10-29.md
# EVS-DESIGN-AUDIT FILE END

from typing import Optional

from image_sources.base import LoadUiSpec
from tha3_paths import IMAGE_SOURCE_THA4


class Tha4StudentSource:
    mode_id = IMAGE_SOURCE_THA4

    def start(self, main_frame) -> None:
        return

    # EVS-DESIGN-AUDIT EVS-A065 BEGIN
    # 设计[f-022, f-063] [静态关联 / 切源待测]
    # 该源负责清理 THA4 student 状态；实际显存/native 资源释放和坏模型切换回落不能只凭清空 Python 引用认定已验证。
    # 历史 bug 热点 #2,#5：仅为回归关联，非声称本次故障已复现。
    # EVS-DESIGN-AUDIT EVS-A065 END
    def stop(self, main_frame) -> None:
        if hasattr(main_frame, "_reset_infer_worker_runtime"):
            main_frame._reset_infer_worker_runtime()
        with main_frame._model_render_lock:
            main_frame.poser = None
            main_frame.character_model = None
            main_frame.torch_source_image = None
            main_frame.wx_source_image = None
            main_frame.last_pose = None
            main_frame._load_preview_shown = False

    def is_ready(self, main_frame) -> bool:
        return main_frame.poser is not None and main_frame.torch_source_image is not None

    def load_asset(self, main_frame, path: str) -> bool:
        return main_frame.load_model_from_path(path)

    def tick(self, main_frame) -> Optional[str]:
        return main_frame.tick_tha4_student_source()

    def get_load_ui_spec(self) -> LoadUiSpec:
        return LoadUiSpec(
            show_yaml_loader=True,
            show_png_loader=False,
            show_tha3_variant=False,
            status_hint="THA4 Student：需 character_model.yaml + 蒸馏权重 / needs distilled student model",
        )
