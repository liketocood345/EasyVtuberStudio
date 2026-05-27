"""Verify packaged character_model loads and measure load time."""
import os
import time

import torch

os.environ.setdefault("CUDA_MODULE_LOADING", "LAZY")

YAML = os.path.join(
    os.path.dirname(__file__),
    "character_model",
    "character_model.yaml",
)


def main():
    from tha4.charmodel.character_model import CharacterModel

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print("device:", device)

    t0 = time.perf_counter()
    model = CharacterModel.load(YAML)
    t_load_yaml = time.perf_counter() - t0

    t1 = time.perf_counter()
    model.get_character_image(device)
    t_image = time.perf_counter() - t1

    t2 = time.perf_counter()
    poser = model.get_poser(device)
    t_poser_create = time.perf_counter() - t2

    t2b = time.perf_counter()
    poser.get_modules()  # loads face + body .pt onto GPU
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_weights = time.perf_counter() - t2b

    # one inference warmup
    t3 = time.perf_counter()
    with torch.no_grad():
        pose = torch.zeros(1, 45, device=device)
        image = model.get_character_image(device)
        if image.dim() == 3:
            image = image.unsqueeze(0)
        _ = poser.pose(image, pose)
    if device.type == "cuda":
        torch.cuda.synchronize()
    t_warmup = time.perf_counter() - t3

    print("OK: CharacterModel.load + get_character_image + get_poser")
    print(f"  load yaml + paths:     {t_load_yaml:.3f}s")
    print(f"  character image GPU: {t_image:.3f}s")
    print(f"  poser object create:   {t_poser_create:.3f}s")
    print(f"  load 2x .pt to GPU:    {t_weights:.3f}s")
    print(f"  first pose forward:    {t_warmup:.3f}s")
    ready = t_load_yaml + t_image + t_poser_create + t_weights
    print(f"  total weights on GPU:  {ready:.3f}s  (manual poser Load Model ~this)")
    print(f"  total first frame:     {ready + t_warmup:.3f}s  (puppeteer 1st pose)")


if __name__ == "__main__":
    main()
