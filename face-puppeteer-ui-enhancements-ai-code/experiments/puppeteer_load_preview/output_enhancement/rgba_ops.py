"""RGBA helpers for alpha-aware SR and resize."""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore


def premultiply_rgba(rgba: np.ndarray) -> np.ndarray:
    arr = np.asarray(rgba, dtype=np.float32)
    if arr.ndim != 3 or arr.shape[2] != 4:
        raise ValueError("expected HxWx4 RGBA")
    alpha = arr[:, :, 3:4] / 255.0
    out = arr.copy()
    out[:, :, 0:3] *= alpha
    return out


def unpremultiply_rgba(premult: np.ndarray) -> np.ndarray:
    arr = np.asarray(premult, dtype=np.float32)
    alpha = arr[:, :, 3:4]
    safe = np.maximum(alpha, 1.0 / 255.0)
    out = arr.copy()
    out[:, :, 0:3] = np.clip(out[:, :, 0:3] / safe, 0.0, 255.0)
    return out


def rgba_uint8_to_sr_input(rgba: np.ndarray) -> np.ndarray:
    """NHWC float32 batch=1 for ONNX SR (RGB premult, alpha separate)."""
    frame = np.asarray(rgba, dtype=np.uint8)
    if frame.ndim != 3 or frame.shape[2] != 4:
        raise ValueError("expected HxWx4 RGBA uint8")
    rgb = frame[:, :, :3].astype(np.float32) / 255.0
    alpha = frame[:, :, 3:4].astype(np.float32) / 255.0
    rgb = rgb * alpha
    batch = np.expand_dims(np.concatenate([rgb, alpha], axis=2), axis=0)
    return batch


def sr_output_to_rgba_uint8(
        sr_batch: np.ndarray,
        source_alpha: np.ndarray,
        scale: int) -> np.ndarray:
    """Convert SR network output back to HxWx4 uint8."""
    out = np.asarray(sr_batch[0], dtype=np.float32)
    if out.shape[-1] >= 3:
        rgb = np.clip(out[:, :, :3], 0.0, 1.0)
    else:
        rgb = np.clip(out, 0.0, 1.0)
    alpha_src = np.asarray(source_alpha, dtype=np.float32)
    if alpha_src.ndim == 2:
        alpha_src = alpha_src[:, :, np.newaxis]
    if alpha_src.max() > 1.0:
        alpha_src = alpha_src / 255.0
    new_h = rgb.shape[0]
    new_w = rgb.shape[1]
    if cv2 is not None:
        alpha = cv2.resize(alpha_src, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    else:
        alpha_u8 = (np.clip(alpha_src, 0, 1) * 255.0).astype(np.uint8)
        plane = resize_rgba(
            np.dstack([alpha_u8, alpha_u8, alpha_u8, alpha_u8]),
            new_w, new_h)[:, :, 0:1].astype(np.float32) / 255.0
        alpha = plane
    alpha = np.clip(alpha, 0.0, 1.0)
    safe = np.maximum(alpha, 1.0 / 255.0)
    rgb = np.clip(rgb / safe, 0.0, 1.0)
    rgba = np.concatenate([rgb * 255.0, alpha * 255.0], axis=2)
    return rgba.astype(np.uint8)


def resize_rgba(rgba: np.ndarray, new_w: int, new_h: int) -> np.ndarray:
    frame = np.asarray(rgba, dtype=np.uint8)
    new_w = max(1, new_w)
    new_h = max(1, new_h)
    if cv2 is not None:
        return cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    h, w = frame.shape[0], frame.shape[1]
    ys = (np.linspace(0, h - 1, new_h)).astype(np.int32)
    xs = (np.linspace(0, w - 1, new_w)).astype(np.int32)
    return frame[np.ix_(ys, xs)]


def downscale_if_max_edge(rgba: np.ndarray, max_edge: int) -> Tuple[np.ndarray, float]:
    """Downscale for heavy SR; returns (scaled, inverse_scale)."""
    h, w = rgba.shape[0], rgba.shape[1]
    edge = max(h, w)
    if edge <= max_edge:
        return rgba, 1.0
    scale = max_edge / float(edge)
    new_w = max(1, int(round(w * scale)))
    new_h = max(1, int(round(h * scale)))
    return resize_rgba(rgba, new_w, new_h), (w / new_w)


def upscale_rgba(rgba: np.ndarray, inv_scale: float) -> np.ndarray:
    if abs(inv_scale - 1.0) < 1e-3:
        return rgba
    h, w = rgba.shape[0], rgba.shape[1]
    return resize_rgba(rgba, max(1, int(round(w * inv_scale))), max(1, int(round(h * inv_scale))))


def sanitize_transparent_rgb(rgba: np.ndarray) -> np.ndarray:
    arr = np.ascontiguousarray(rgba, dtype=np.uint8)
    transparent = arr[:, :, 3] == 0
    if not np.any(transparent):
        return arr
    out = arr.copy()
    out[transparent, 0:3] = 0
    return out


def rife_prepare_pair(frame0: np.ndarray, frame1: np.ndarray) -> np.ndarray:
    """Two HxWx4 uint8 -> batch 1xHxWx4 float for RIFE inputs (NHWC)."""
    a = np.asarray(frame0, dtype=np.float32) / 255.0
    b = np.asarray(frame1, dtype=np.float32) / 255.0
    return np.stack([a, b], axis=0)


def rife_mid_frames_to_uint8(outputs: np.ndarray, count: int) -> list:
    """Extract intermediate frames from RIFE output batch."""
    frames = []
    batch = np.asarray(outputs)
    if batch.ndim == 4 and batch.shape[0] >= count:
        for i in range(count):
            frame = np.clip(batch[i] * 255.0, 0, 255).astype(np.uint8)
            frames.append(frame)
    return frames
