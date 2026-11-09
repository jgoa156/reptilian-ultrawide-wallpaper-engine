"""Calibration of the arm reach (tools/arm_pose.py): seams and distortion at several poses.

For every output pixel of the region around the arm, the source it shows is the moved arm where the
arm has ink, else the rest of the layer (joint fan + pre-arm sink) where that has ink. A seam is a pair
of neighbouring inked pixels whose sources jump apart by more than SEAM px (a continuous map moves
them about 1 px apart). Distortion is the stretch of the map's local Jacobian: max(s1, 1/s2) from its
singular values (1 = undistorted), measured separately on the arm and on the rest.

Writes rig/v7/arm_calibration.png: one column per pose, the overview (seams red, stretch > 1.25
yellow, > 1.5 orange) over the junction close-up at full res. Prints the numbers per pose.
Usage: python tools/arm_calibrate.py [pose ...]   (default 0 0.25 0.5 0.75 1)
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
import arm_pose as ap  # noqa: E402

TW, TH = 5040, 2160
SEAM = 6.0
VIEW = (2100, 300, 4950, 2160)      # overview (2 px cells)
JUNC = (3950, 1450, 4950, 2160)     # junction close-up (full res)

K = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA")).astype(np.float32)
W = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA")).astype(np.float32)
ALPHA = np.maximum(K[..., 3], W[..., 3]) / 255


def sample(img, p):
    xi = np.clip(np.rint(p[..., 0]).astype(int), 0, TW - 1); yi = np.clip(np.rint(p[..., 1]).astype(int), 0, TH - 1)
    out = img[yi, xi]
    bad = (p[..., 0] < 0) | (p[..., 0] >= TW) | (p[..., 1] < 0) | (p[..., 1] >= TH)
    return np.where(bad[..., None] if out.ndim > bad.ndim else bad, 0, out)


def analyse(P, a, box, S):
    x0, y0, x1, y1 = box
    gy, gx = np.mgrid[y0:y1:S, x0:x1:S].astype(float)
    q = np.c_[gx.ravel() + 0.5, gy.ravel() + 0.5]
    shape = gx.shape
    src, arm, rq, hide = ap.pose_map(P, a, q)
    aa = np.where(arm, sample(ALPHA, src), 0.0)
    ra = np.where(~hide, sample(ALPHA, rq), 0.0)
    on_arm = aa > 0.5
    ink = on_arm | (ra > 0.5)
    eff = np.where(on_arm[:, None], src, rq).reshape(*shape, 2)
    on_arm, ink = on_arm.reshape(shape), ink.reshape(shape)
    # seams: neighbouring inked pixels whose sources jump apart
    seam = np.zeros(shape, bool)
    for dy, dx in ((0, 1), (1, 0)):
        a_ = eff[: shape[0] - dy, : shape[1] - dx]; b_ = eff[dy:, dx:]
        both = ink[: shape[0] - dy, : shape[1] - dx] & ink[dy:, dx:]
        jump = np.hypot(*(b_ - a_).transpose(2, 0, 1)) > SEAM * S
        hit = both & jump
        seam[: shape[0] - dy, : shape[1] - dx] |= hit
    # stretch from the Jacobian (central differences, cells where the neighbours are on the same side)
    J = np.zeros(shape + (2, 2))
    J[:, 1:-1, :, 0] = (eff[:, 2:] - eff[:, :-2]) / (2 * S)
    J[1:-1, :, :, 1] = (eff[2:] - eff[:-2]) / (2 * S)
    sv = np.linalg.svd(J, compute_uv=False)
    stretch = np.maximum(sv[..., 0], 1 / np.maximum(sv[..., 1], 1e-6))
    same = np.zeros(shape, bool)
    same[1:-1, 1:-1] = (on_arm[1:-1, 2:] == on_arm[1:-1, :-2]) & (on_arm[2:, 1:-1] == on_arm[:-2, 1:-1]) \
        & (on_arm[1:-1, 2:] == on_arm[1:-1, 1:-1]) & ~seam[1:-1, 1:-1]
    valid = ink & same
    # the composite (K over W on a light ground)
    col = np.full((q.shape[0], 3), 222.0)
    for img in (W, K):
        rest = np.where((~hide)[:, None], sample(img, rq), 0.0)
        armc = np.where(arm[:, None], sample(img, src), 0.0)
        for c in (rest, armc):
            al = c[:, 3:4] / 255
            col = col * (1 - al) + c[:, :3] * al
    col = col.reshape(*shape, 3)
    return col, seam, stretch, valid, on_arm, ink


def stats(name, st, m):
    v = st[m]
    if v.size == 0:
        return f"{name}: no ink"
    return (f"{name}: p50 {np.percentile(v, 50):.3f}  p99 {np.percentile(v, 99):.3f}  max {v.max():.2f}  "
            f">1.25 {np.mean(v > 1.25) * 100:5.2f}%  >1.5 {np.mean(v > 1.5) * 100:5.2f}%")


def paint(col, seam, stretch, valid):
    out = col.copy()
    out[valid & (stretch > 1.25)] = out[valid & (stretch > 1.25)] * 0.4 + np.array([255, 220, 0]) * 0.6
    out[valid & (stretch > 1.5)] = out[valid & (stretch > 1.5)] * 0.3 + np.array([255, 120, 0]) * 0.7
    seam_d = seam.copy()
    seam_d[1:] |= seam[:-1]; seam_d[:, 1:] |= seam[:, :-1]
    out[seam_d] = [230, 0, 0]
    return ImageOps.mirror(Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)))


def main():
    poses = [float(v) for v in sys.argv[1:]] or [0.0, 0.25, 0.5, 0.75, 1.0]
    P = ap.load()
    cols = []
    for a in poses:
        col, seam, st, valid, on_arm, ink = analyse(P, a, VIEW, 2)
        top = paint(col, seam, st, valid)
        jcol, jseam, jst, jvalid, jarm, jink = analyse(P, a, JUNC, 1)
        bot = paint(jcol, jseam, jst, jvalid).resize((top.width, int(top.width * jcol.shape[0] / jcol.shape[1])))
        print(f"pose {a:.2f}  seams: overview {int(seam.sum())} px, junction {int(jseam.sum())} px")
        print("   " + stats("arm ", jst, jvalid & jarm) + "\n   " + stats("rest", jst, jvalid & ~jarm))
        if "line" in P:                                   # nothing above the user's line may move
            x0, y0, x1, y1 = VIEW
            gy, gx = np.mgrid[y0:y1:2, x0:x1:2].astype(float)
            q = np.c_[gx.ravel() + 0.5, gy.ravel() + 0.5]
            p1, n = ap.line_normal(P)
            up = ((q - p1) @ n) < 0
            mv = np.hypot(*(ap.rest_src(P, a, q[up]) - q[up]).T)
            print(f"   above the line: rest moves at most {mv.max():.4f} px")
        c = Image.new("RGB", (top.width, top.height + bot.height + 6), (40, 40, 40))
        c.paste(top, (0, 0)); c.paste(bot, (0, top.height + 6))
        cols.append(c)
    sheet = Image.new("RGB", (sum(c.width for c in cols) + 8 * (len(cols) - 1), cols[0].height), (40, 40, 40))
    x = 0
    for c in cols:
        sheet.paste(c, (x, 0)); x += c.width + 8
    sheet.save(HERE / "rig" / "v7" / "arm_calibration.png")
    print("saved rig/v7/arm_calibration.png")


if __name__ == "__main__":
    main()
