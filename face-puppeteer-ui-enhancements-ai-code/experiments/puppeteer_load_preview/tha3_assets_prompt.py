"""In-app prompts for one-click upstream asset downloads (THA3/THA4 official)."""

from __future__ import annotations



import wx



from tha3_paths import find_repo_root, tha3_inference_assets_available

from upstream_assets import (

    run_upstream_download,

    tha3_assets_installed,

    tha3_missing_message,

    tha4_training_assets_available,

    tha4_training_missing_message,

)





def ensure_tha3_assets_available(main_frame, variant: str | None = None, *, offer_download: bool = True) -> bool:

    """Return True when THA3 inference assets exist for the selected variant."""

    variant = variant or getattr(main_frame, "tha3_model_variant", "separable_half")

    if tha3_inference_assets_available(variant):

        return True



    parent = main_frame.get_dialog_parent() if hasattr(main_frame, "get_dialog_parent") else main_frame

    message = tha3_missing_message(variant)

    if offer_download:

        message += "\n\n是否现在从 THA3 原作者渠道下载并自动安装？\nDownload from official THA3 author now?"

        dialog = wx.MessageDialog(parent, message, "THA3 模型未安装", wx.YES_NO | wx.ICON_WARNING)

        if dialog.ShowModal() != wx.ID_YES:

            dialog.Destroy()

            return False

        dialog.Destroy()

        run_upstream_download(["tha3_models"], find_repo_root())

        if tha3_assets_installed(variant, find_repo_root()):

            return True

        wx.MessageBox(

            parent,

            tha3_missing_message(variant) + "\n\n下载未完成，请检查网络或稍后重试。",

            "THA3 模型仍缺失",

            wx.OK | wx.ICON_WARNING,

        )

        return False



    wx.MessageBox(parent, message, "THA3 模型未安装", wx.OK | wx.ICON_WARNING)

    return False





def ensure_tha4_training_assets_available(parent=None, *, offer_download: bool = True) -> bool:

    """Return True when THA4 teacher weights and pose_dataset.pt are present."""

    if tha4_training_assets_available(find_repo_root()):

        return True



    message = tha4_training_missing_message()

    if offer_download:

        message += "\n\n是否现在从 THA4 原作者渠道下载并自动安装？\nDownload from official THA4 author now?"

        style = wx.YES_NO | wx.ICON_WARNING

        if parent is None:

            app = wx.GetApp() or wx.App(False)

            parent = app.GetTopWindow() if app else None

        dialog = wx.MessageDialog(parent, message, "THA4 训练包未安装", style)

        if dialog.ShowModal() != wx.ID_YES:

            dialog.Destroy()

            return False

        dialog.Destroy()

        run_upstream_download(["tha4_teacher_training"], find_repo_root())

        if tha4_training_assets_available(find_repo_root()):

            return True

        wx.MessageBox(

            parent,

            tha4_training_missing_message() + "\n\n下载未完成，请检查网络或稍后重试。",

            "THA4 训练包仍缺失",

            wx.OK | wx.ICON_WARNING,

        )

        return False



    wx.MessageBox(parent, message, "THA4 训练包未安装", wx.OK | wx.ICON_WARNING)

    return False





# Backward-compatible re-exports for older imports.

tha3_assets_missing_message = tha3_missing_message

run_tha3_download = lambda portable_root=None: run_upstream_download(["tha3_models"], portable_root or find_repo_root())

