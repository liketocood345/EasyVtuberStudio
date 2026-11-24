import torch
from torch import Tensor
from torch.nn.functional import affine_grid, grid_sample


# EVS-PERF Phase 3 (2026-11-24): pose-independent grids are cached (lossless).
# Rebuilding them every frame cost GPU time (affine_grid/bmm) and, worse, the
# torch.tensor(..., device=cuda) identity is a blocking host->device copy that
# synchronized the stream mid-frame and made the forward un-capturable by CUDA
# Graphs. Cache keys include the autocast state because it can change the
# dtype of the computed grid.
_EVS_CONST_CACHE_LIMIT = 8
# Benchmarks set this False to reproduce the original per-frame rebuild.
EVS_CONST_CACHE_ENABLED = True


def evs_autocast_key():
    enabled = torch.is_autocast_enabled()
    try:
        dtype = torch.get_autocast_gpu_dtype() if enabled else None
    except Exception:
        dtype = None
    return enabled, dtype


def evs_cached_constant(owner, key, build):
    """Return ``build()`` memoized on ``owner`` (a module/object) under ``key``."""
    if not EVS_CONST_CACHE_ENABLED:
        return build()
    cache = owner.__dict__.get("_evs_const_cache")
    if cache is None:
        cache = {}
        owner.__dict__["_evs_const_cache"] = cache
    value = cache.get(key)
    if value is None:
        if len(cache) >= _EVS_CONST_CACHE_LIMIT:
            cache.clear()
        value = build()
        cache[key] = value
    return value


def apply_rgb_change(alpha: Tensor, color_change: Tensor, image: Tensor):
    image_rgb = image[:, 0:3, :, :]
    color_change_rgb = color_change[:, 0:3, :, :]
    output_rgb = color_change_rgb * alpha + image_rgb * (1 - alpha)
    return torch.cat([output_rgb, image[:, 3:4, :, :]], dim=1)


def apply_grid_change(grid_change, image: Tensor) -> Tensor:
    n, c, h, w = image.shape
    device = grid_change.device
    grid_change = torch.transpose(grid_change.view(n, 2, h * w), 1, 2).view(n, h, w, 2)
    identity = torch.tensor(
        [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
        dtype=grid_change.dtype,
        device=device).unsqueeze(0).repeat(n, 1, 1)
    base_grid = affine_grid(identity, [n, c, h, w], align_corners=False)
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

        # EVS-PERF (2026-11-24): the identity used to be cached by (n, device)
        # only, so its dtype was whatever the *first* forward in the process used
        # (FP16 under autocast or FP32). A later pass in the other precision
        # reused it, making output depend on history (precision toggles, ONNX
        # export before the first FP16 frame). Keyed by dtype as well: each
        # precision now matches a fresh process running only that precision.
        identities = self.__dict__.get("_evs_identities")
        if identities is None:
            identities = {}
            self.__dict__["_evs_identities"] = identities
        identity_key = (int(n), device, grid_change.dtype)
        identity = identities.get(identity_key)
        if identity is None:
            identity = torch.tensor(
                [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]],
                dtype=grid_change.dtype,
                device=device,
                requires_grad=False) \
                .unsqueeze(0).repeat(n, 1, 1)
            identities[identity_key] = identity
        self.last_identity = identity
        self.last_n = n
        self.last_device = device
        # EVS-PERF Phase 3: base grid depends only on the cached identity and shape.
        base_grid = evs_cached_constant(
            self, ("base_grid", id(identity), int(c), int(h), int(w), align_corners, evs_autocast_key()),
            lambda: (identity, affine_grid(identity, [n, c, h, w], align_corners=align_corners)))[1]

        grid = base_grid + grid_change
        resampled_image = grid_sample(image, grid, mode='bilinear', padding_mode='border', align_corners=align_corners)
        return resampled_image


def apply_color_change(alpha, color_change, image: Tensor) -> Tensor:
    return color_change * alpha + image * (1 - alpha)
