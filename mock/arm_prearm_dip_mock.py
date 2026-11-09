"""Pre-arm arch mock: on top of the joint fan, lift the coil floor between the body corner and the
arm's base into an arch (vertical stretch, zero at the bottom edge and at both ends).
Args: xc halfwidth ytop amps...  Columns: pose 1 with each amp. Mirrored like WE."""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

HERE = Path(r"C:\Users\rockb\OneDrive\Área de Trabalho\Reptilian Ultrawide 4K")
sys.path.insert(0, str(HERE / "tools"))
import arm_pose as ap  # noqa: E402

TW, TH = 5040, 2160
XC, HWX, YTOP = (float(v) for v in sys.argv[1:4])
AMPS = [float(v) for v in sys.argv[4:]]
Y0 = YTOP - 300                       # lift fades in from here (top) ...
k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA")).astype(np.float32)
w = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA")).astype(np.float32)
P = ap.load()
x0, x1, y0, y1 = 3300, 4950, 1200, 2160
S = 2
gy, gx = np.mgrid[y0 // S:y1 // S, x0 // S:x1 // S]
q = np.c_[(gx.ravel() + 0.5) * S, (gy.ravel() + 0.5) * S]
sm = lambda t: (lambda c: c * c * (3 - 2 * c))(np.clip(t, 0, 1))


def sample(img, p):
    xi = np.clip(p[:, 0].astype(int), 0, TW - 1); yi = np.clip(p[:, 1].astype(int), 0, TH - 1)
    out = img[yi, xi].copy()
    out[(p[:, 0] < 0) | (p[:, 0] >= TW) | (p[:, 1] < 0) | (p[:, 1] >= TH)] = 0
    return out


tiles = []
for B in AMPS:
    PP = dict(P); PP['base_dst'] = [P['base_src'][0], P['base_src'][1] + B]   # the base sinks with the dip
    src, arm, _, _ = ap.pose_map(PP, 1.0, q)
    JX = P['base_src'][0]
    gxw = 1 - sm((q[:, 0] - JX - 150) / (XC - JX - 150))      # flat around the joint, gone by XC
    hy = sm((q[:, 1] - Y0) / (YTOP - Y0))
    qb = q - np.c_[np.zeros(len(q)), B * gxw * hy]          # content moves down: the arc points down
    rq = ap.fan(P, 1.0, qb)
    vr, vnr = ap.skeleton(P, 0.0)
    hide = ap.project(P, vr, vnr, rq)[3] & ap.region(rq[:, 0], rq[:, 1])
    col = np.full((len(q), 3), 222.0)
    for img in (w, k):
        rest = sample(img, rq); rest[hide] = 0
        armc = sample(img, src); armc[~arm] = 0
        for c in (rest, armc):
            al = c[:, 3:4] / 255
            col = col * (1 - al) + c[:, :3] * al
    tiles.append(ImageOps.mirror(Image.fromarray(col.reshape(gy.shape[0], gy.shape[1], 3).astype(np.uint8))))
tw, th = tiles[0].size
sheet = Image.new("RGB", (tw * len(tiles) + 10 * (len(tiles) - 1), th), (40, 40, 40))
for j, t in enumerate(tiles):
    sheet.paste(t, (j * (tw + 10), 0))
sheet.save(Path(__file__).with_suffix(".png"))
print("ok")
