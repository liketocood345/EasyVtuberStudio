import torch
import threading
from collections import OrderedDict
from torch import Tensor
from torch.nn.functional import affine_grid, grid_sample


def apply_rgb_change(alpha: Tensor, color_change: Tensor, image: Tensor):
    image_rgb = image[:, 0:3, :, :]
    color_change_rgb = color_change[:, 0:3, :, :]
    output_rgb = color_change_rgb * alpha + image_rgb * (1 - alpha)
    return torch.cat([output_rgb, image[:, 3:4, :, :]], dim=1)


# EVS-PERF-20261030: shape/dtype/device constants are retained, not rebuilt
# through a host->GPU torch.tensor on every warp. Active CUDA graphs also keep
# strong references so LRU eviction cannot invalidate captured addresses.
_BASE_GRID_CACHE = OrderedDict()
_BASE_GRID_LOCK = threading.RLock()


def cached_grid_references():
    with _BASE_GRID_LOCK:
        return list(_BASE_GRID_CACHE.values())


def _base_grid(n, c, h, w, dtype, device, align_corners):
    key = (n, c, h, w, dtype, device, bool(align_corners))
    with _BASE_GRID_LOCK:
        cached = _BASE_GRID_CACHE.get(key)
        if cached is None:
            identity = torch.tensor([[1., 0., 0.], [0., 1., 0.]],
                                    dtype=dtype, device=device).unsqueeze(0).repeat(n, 1, 1)
            grid = affine_grid(identity, [n, c, h, w], align_corners=align_corners)
            event = None
            if device.type == "cuda":
                event = torch.cuda.Event()
                event.record(torch.cuda.current_stream(device))
            cached = (grid, event)
            _BASE_GRID_CACHE[key] = cached
            if len(_BASE_GRID_CACHE) > 32:
                _BASE_GRID_CACHE.popitem(last=False)
        else:
            _BASE_GRID_CACHE.move_to_end(key)
    grid, event = cached
    # Capture is preceded by synchronized warmup; the graph owner retains
    # these constants. Cross-stream eager event bookkeeping must stay outside
    # capture on PyTorch 1.13.
    if event is not None and not torch.cuda.is_current_stream_capturing():
        stream = torch.cuda.current_stream(device)
        stream.wait_event(event)
        grid.record_stream(stream)
    return grid


def apply_grid_change(grid_change, image: Tensor) -> Tensor:
    n, c, h, w = image.shape
    device = grid_change.device
    grid_change = torch.transpose(grid_change.view(n, 2, h * w), 1, 2).view(n, h, w, 2)
    base_grid = _base_grid(n, c, h, w, grid_change.dtype, device, False)
    grid = base_grid + grid_change
    resampled_image = grid_sample(image, grid, mode='bilinear', padding_mode='border', align_corners=False)
    return resampled_image


class GridChangeApplier:
    def __init__(self):
        self.last_n = None
        self.last_device = None
        self.last_identity = None

    def apply(self, grid_change: Tensor, image: Tensor, align_corners: bool = False) -> Tensor:
        n, c, h, w = image.shape
        device = grid_change.device
        grid_change = torch.transpose(grid_change.view(n, 2, h * w), 1, 2).view(n, h, w, 2)

        base_grid = _base_grid(n, c, h, w, grid_change.dtype, device, align_corners)

        grid = base_grid + grid_change
        resampled_image = grid_sample(image, grid, mode='bilinear', padding_mode='border', align_corners=align_corners)
        return resampled_image


def apply_color_change(alpha, color_change, image: Tensor) -> Tensor:
    return color_change * alpha + image * (1 - alpha)
