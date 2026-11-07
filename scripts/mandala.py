"""Build 13-fold mandalas from the Choronzon ink layers, with no distortion.

The figure PNG is used as-is: no polar warp, no bending. Each of the `sides`
copies is the figure rotated rigidly about the mandala centre, feet toward the
centre and head outward. Every other copy is mirrored left-right. The copies
are glued by taking the maximum ink alpha wherever they overlap.

With an odd count (13) the mirror pattern can't alternate all the way round,
so one seam has two same-handed neighbours. Choronzon is drawn bilaterally
symmetric, so in practice that seam doesn't show.

Usage:
    python scripts/mandala.py [--size 4096] [--sides 13] [--hub 0]
        [--head out|in] [--colors black cyan magenta] [--src Choronzon_black.png]

--hub   radius of the empty centre (where the feet sit), as a fraction of the
        figure's height. 0 = feet meet at the exact centre.

Writes Choronzon_mandala_<colour>.png next to the source.
"""
import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

NAMED = {"black": "#000000", "white": "#FFFFFF",
         "cyan": "#00FFFF", "magenta": "#FF00FF"}


def hex_rgb(c):
    h = NAMED.get(c.lower(), c).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mandala_alpha(alpha: np.ndarray, size: int, sides: int, head_out: bool,
                  hub: float) -> np.ndarray:
    """Rigidly place `sides` rotated copies of `alpha` around the centre."""
    H, W = alpha.shape
    if not head_out:
        alpha = alpha[::-1]
    # Total radius in source px: hub + figure height. Fit it into the canvas.
    r0 = hub * H
    R_src = math.hypot(r0 + H, W / 2)
    k = (size / 2 - 2) / R_src                 # uniform scale source -> output
    if k < 1:                                  # prefilter before shrinking
        alpha = ndi.gaussian_filter(alpha, 0.45 / k)
    mirrored = alpha[:, ::-1]

    c = size / 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) + 0.5
    dx, dy = (xx - c) / k, (c - yy) / k        # source px, y up
    out = np.zeros((size, size), np.float32)
    for i in range(sides):
        a = 2 * math.pi * i / sides            # copy i points along angle a
        ca, sa = math.cos(a), math.sin(a)
        # Rotate output point into the copy's frame (copy 0 points straight up).
        px = dx * ca - dy * sa
        py = dx * sa + dy * ca
        sx = px + W / 2 - 0.5                  # figure centred on its axis
        sy = (r0 + H) - py - 0.5               # top row (head) at the outer end
        src = mirrored if i % 2 else alpha
        np.maximum(out, ndi.map_coordinates(src, [sy, sx], order=1,
                                            mode="constant", cval=0), out=out)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--src", default="Choronzon_black.png")
    p.add_argument("--size", type=int, default=4096)
    p.add_argument("--sides", type=int, default=13)
    p.add_argument("--head", choices=["out", "in"], default="out")
    p.add_argument("--hub", type=float, default=0.0)
    p.add_argument("--colors", nargs="+", default=["black", "cyan", "magenta"])
    p.add_argument("--prefix", default="Choronzon_mandala")
    a = p.parse_args()

    src = Path(a.src)
    alpha = np.asarray(Image.open(src).convert("RGBA"))[..., 3].astype(np.float32) / 255
    # Crop to the figure's bounding box so the feet sit right at the hub.
    ys, xs = np.nonzero(alpha > 0.02)
    alpha = alpha[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    m = mandala_alpha(alpha, a.size, a.sides, a.head == "out", a.hub)
    A = np.round(np.clip(m, 0, 1) * 255).astype(np.uint8)

    for c in a.colors:
        rgba = np.empty((a.size, a.size, 4), np.uint8)
        rgba[..., :3] = hex_rgb(c)
        rgba[..., 3] = A
        path = src.parent / f"{a.prefix}_{c.lstrip('#').lower()}.png"
        Image.fromarray(rgba, "RGBA").save(path, optimize=True)
        print(f"Saved {path}")


if __name__ == "__main__":
    main()
