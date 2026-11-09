"""Mock: two readings of "more movement at the junction" for the arm reach (2026-11-08).

A  slide + pull: the arm slides down along the stroke (tools/arm_pose.py) and the coil from the body
   corner to the arm's base is a root chain that gets pulled under the bottom edge with it.
B  hinge: the arm's base stays put and the arm swings toward the mandala, the bend concentrated at the
   junction (segments near the base turn most, the tip lags), no slide.
Rows A, B; columns pose 0.5, 1 (screen orientation, mirrored like WE shows it).
Usage: python mock/arm_junction_mock.py   (writes mock/arm_junction_mock.png)
"""
import copy
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
import arm_pose as ap  # noqa: E402

TW, TH = 5040, 2160
S = 3
HINGE = math.radians(-48)        # total swing at the junction (negative: toward the mandala)

k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA")).astype(np.float32)
w = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA")).astype(np.float32)
x0, x1, y0, y1 = 2100, 5040, 300, 2160
gy, gx = np.mgrid[y0 // S:y1 // S, x0 // S:x1 // S]
q = np.c_[(gx.ravel() + 0.5) * S, (gy.ravel() + 0.5) * S]


def sample(img, p):
    xi = np.clip(p[:, 0].astype(int), 0, TW - 1); yi = np.clip(p[:, 1].astype(int), 0, TH - 1)
    out = img[yi, xi].copy()
    out[(p[:, 0] < 0) | (p[:, 0] >= TW) | (p[:, 1] < 0) | (p[:, 1] >= TH)] = 0
    return out


def render(P, a):
    src, arm, hide = ap.pose_map(P, a, q)
    col = np.full((len(q), 3), 222.0)
    for img in (w, k):
        rest = sample(img, q); rest[hide] = 0
        armc = sample(img, src); armc[~arm] = 0
        for c in (rest, armc):
            al = c[:, 3:4] / 255
            col = col * (1 - al) + c[:, :3] * al
    return ImageOps.mirror(Image.fromarray(col.reshape(gy.shape[0], gy.shape[1], 3).astype(np.uint8)))


PA = ap.load()
PB = copy.deepcopy(PA)
PB["nroot"] = 0
PB["base_dst"] = PB["base_src"]
n = PB["nseg"]
PB["ang_dst"] = [s + HINGE * (1 - 0.6 * i / (n - 1)) for i, s in enumerate(PB["ang_src"])]

tiles = [[render(P, a) for a in (0.5, 1.0)] for P in (PA, PB)]
tw, th = tiles[0][0].size
sheet = Image.new("RGB", (tw * 2 + 10, th * 2 + 10), (40, 40, 40))
d = ImageDraw.Draw(sheet)
for r, row in enumerate(tiles):
    for c, im in enumerate(row):
        sheet.paste(im, (c * (tw + 10), r * (th + 10)))
        d.text((c * (tw + 10) + 12, r * (th + 10) + 10), f"{'AB'[r]}  pose {(0.5, 1.0)[c]}", fill=(200, 0, 0))
sheet.save(HERE / "mock" / "arm_junction_mock.png")
print("saved mock/arm_junction_mock.png")
