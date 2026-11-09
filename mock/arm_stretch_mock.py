"""Still mock: the arm laid along the user's red stroke (screenshot 2026-11-08), like a tonearm.

Skeleton warp. Source skeleton = the arm's centreline from where it leaves the bottom coil to the
spike tip (hand-placed guide points, re-centred between the silhouette edges). Destination = the
red stroke (registered to the line art: scale 0.470, offset -2,-20 on the 1699x993 shot), started
exactly at the source base, blended into it over the first BLEND px so the arm doesn't tear, and
continued past the stroke's end along its last direction so the arm keeps its full length.
Every pixel keeps its offset across the centreline: the arm keeps its width and drawing.
Usage: python mock/arm_stretch_mock.py
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageOps
from scipy import ndimage as ndi
from scipy.interpolate import splev, splprep
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent.parent
TW, TH = 5040, 2160
N = 800
BLEND = 260.0
GUIDE = np.array([[4700, 2150], [4500, 2100], [4300, 2020], [4100, 1920], [3940, 1800], [3860, 1660],
                  [3820, 1500], [3790, 1300], [3760, 1100], [3740, 900], [3712, 640], [3680, 382]], float)
BASE = np.array([4370.0, 2110.0])           # where the stroke starts (on the coil)
CENTRE = np.array([2334.0, 979.0])          # the mandala's centre on the user's screen (texture px)
STRETCH = float(sys.argv[1]) if len(sys.argv) > 1 else 1.0   # arm length along the path / its own length

k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA")).astype(np.float32)
w = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA")).astype(np.float32)
sil = ndi.binary_fill_holes(ndi.binary_closing(np.maximum(k[..., 3], w[..., 3]) > 64, iterations=4))
red = np.load(HERE / "mock" / "red_tex.npy")


def spline(pts, n, s=0):
    tck, _ = splprep(pts.T, s=s)
    p = np.array(splev(np.linspace(0, 1, 4000), tck)).T
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    u = np.linspace(0, seg[-1], n)
    return np.c_[np.interp(u, seg, p[:, 0]), np.interp(u, seg, p[:, 1])], seg[-1]


def frame(p):
    d = np.gradient(p, axis=0); d /= np.linalg.norm(d, axis=1, keepdims=True)
    return d, np.c_[-d[:, 1], d[:, 0]]


def edges(p, nrm, maxw=400):
    """distance to the silhouette edge on each side along the normal"""
    out = np.zeros((len(p), 2))
    r = np.arange(0, maxw, 2.0)
    for i, (q, nv) in enumerate(zip(p, nrm)):
        for j, sgn in enumerate((1, -1)):
            xy = q + sgn * r[:, None] * nv
            xi, yi = np.clip(xy[:, 0].astype(int), 0, TW - 1), np.clip(xy[:, 1].astype(int), 0, TH - 1)
            inside = sil[yi, xi] & (xy[:, 1] < TH)
            out_i = np.argmax(~inside) if (~inside).any() else len(r) - 1
            out[i, j] = r[out_i]
    return out


# source skeleton, re-centred twice
src, _ = spline(GUIDE, N, s=2000)
for _ in range(2):
    tng, nrm = frame(src)
    e = edges(src, nrm)
    src = src + ((e[:, 0] - e[:, 1]) / 2)[:, None] * nrm
    src = np.c_[ndi.gaussian_filter1d(src[:, 0], 6, mode="nearest"), ndi.gaussian_filter1d(src[:, 1], 6, mode="nearest")]
    src, _ = spline(src, N, s=4000)
tng, nrm = frame(src)
hw = ndi.maximum_filter1d(edges(src, nrm).max(axis=1), 15) + 10
tipblend = np.clip((np.arange(N) - (N - 120)) / 100, 0, 1)[:, None]
guide_s, _ = spline(GUIDE, N, s=2000)
src = src * (1 - tipblend) + guide_s * tipblend
i0 = int(np.argmin(np.hypot(*(src - BASE).T)))
src_arm, L = spline(src[i0:], N, s=0)
hw_arm = np.interp(np.linspace(0, 1, N), np.linspace(0, 1, N - i0), hw[i0:])

# destination: the stroke from the base, extended to the arm's length
r_pts, r_len = spline(red, 400, s=3000)
r_pts += BASE - r_pts[0]
target = L * STRETCH
if r_len < target:
    d_end = r_pts[-1] - r_pts[-8]; d_end /= np.linalg.norm(d_end)
    ext = r_pts[-1] + np.outer(np.linspace(0, target - r_len, 80)[1:], d_end)
    r_pts = np.vstack([r_pts, ext])
dst, dlen = spline(r_pts, N, s=500)
if dlen > target * 1.001:                                     # shorter than the stroke: cut it
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(dst, axis=0).T))]
    uu = np.linspace(0, target, N)
    dst = np.c_[np.interp(uu, seg, dst[:, 0]), np.interp(uu, seg, dst[:, 1])]
u = np.linspace(0, L, N)
b = np.clip(u / BLEND, 0, 1); b = b * b * (3 - 2 * b)
dst = src_arm * (1 - b)[:, None] + dst * b[:, None]
dst, _ = spline(dst, N, s=500)
print(f"stretch x{STRETCH}: arm from base {L:.0f} px, stroke {r_len:.0f} px; tip at {dst[-1].round()}, "
      f"{np.hypot(*(dst[-1] - CENTRE)):.0f} px from the mandala centre")

_, ns = frame(src_arm)
_, nd = frame(dst)

# moving region: silhouette pixels within the arm band past the base (full res)
gy, gx = np.mgrid[0:TH, 0:TW]
box = lambda P, pad: (int(max(P[:, 0].min() - pad, 0)), int(min(P[:, 0].max() + pad, TW)),
                      int(max(P[:, 1].min() - pad, 0)), int(min(P[:, 1].max() + pad, TH)))


def project(line, x0, x1, y0, y1):
    pts = np.c_[gx[y0:y1, x0:x1].ravel(), gy[y0:y1, x0:x1].ravel()].astype(float)
    _, j = cKDTree(line).query(pts)
    t_, n_ = frame(line)
    rel = pts - line[j]
    return pts, j, np.einsum("ij,ij->i", rel, n_[j]), np.einsum("ij,ij->i", rel, t_[j])


# moving region: every silhouette pixel of the arm (rig2's tail region) past the base, barbs
# included; its half-width per station comes from those pixels
x0, x1, y0, y1 = box(src_arm, 450)
pts, j, n, a = project(src_arm, x0, x1, y0, y1)
X, Yp = pts[:, 0], pts[:, 1]
region = (X < 3950) | ((Yp > 1500) & (X < 4400)) | ((Yp > 1870) & (X < 4560))
mv = region & sil[Yp.astype(int), X.astype(int)] & ~((j == 0) & (a < 0)) & (np.abs(n) < 450)
moving = np.zeros((TH, TW), bool)
moving[y0:y1, x0:x1] = mv.reshape(y1 - y0, x1 - x0)
moving = ndi.binary_dilation(moving, iterations=4)
hw_arm = np.zeros(N)
np.maximum.at(hw_arm, j[mv], np.abs(n[mv]))
hw_arm = ndi.maximum_filter1d(hw_arm, 21) + 12

x0, x1, y0, y1 = box(dst, hw_arm.max())
pts, j, n, a = project(dst, x0, x1, y0, y1)
ok = (np.abs(n) <= hw_arm[j]) & ~((j == 0) & (a < 0)) & ~((j == N - 1) & (a > 0))
sp = src_arm[j] + n[:, None] * ns[j]
mapx = np.full((TH, TW), -1, np.float32); mapy = np.full((TH, TW), -1, np.float32)
fx_ = np.full(len(pts), -1, np.float32); fy_ = np.full(len(pts), -1, np.float32)
fx_[ok], fy_[ok] = sp[ok, 0], sp[ok, 1]
mapx[y0:y1, x0:x1] = fx_.reshape(y1 - y0, x1 - x0); mapy[y0:y1, x0:x1] = fy_.reshape(y1 - y0, x1 - x0)


def comp(layers, bgv=222):
    out = np.full((TH, TW, 3), bgv, np.float32)
    for Lr in layers:
        al = Lr[..., 3:4] / 255
        out = out * (1 - al) + Lr[..., :3] * al
    return out


arm_only = lambda Lr: Lr * moving[..., None]
still = lambda Lr: Lr * (~moving)[..., None]
warp = lambda Lr: cv2.remap(arm_only(Lr), mapx, mapy, cv2.INTER_LINEAR, borderValue=0)
now = comp([w, k])
posed = comp([still(w), still(k), warp(w), warp(k)])


def show(img, guide):
    im = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    if guide:
        ImageDraw.Draw(im).line([tuple(p) for p in red], fill=(237, 28, 36), width=10)
    return ImageOps.mirror(im).crop((0, 0, 2600, TH)).resize((1300, 1080), Image.LANCZOS)


if STRETCH != 1.0 or len(sys.argv) > 1:
    im = Image.fromarray(np.clip(posed, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    d.ellipse([CENTRE[0] - 22, CENTRE[1] - 22, CENTRE[0] + 22, CENTRE[1] + 22], outline=(237, 28, 36), width=8)
    im = ImageOps.mirror(im).crop((0, 300, 3200, TH)).resize((1600, 930), Image.LANCZOS)
    im.save(HERE / "mock" / f"arm_stretch_x{STRETCH:.2f}.png")
    sys.exit(0)
panels = (show(now, True), show(posed, False), show(posed, True))
sheet = Image.new("RGB", (1300 * 3 + 20, 1080), (40, 40, 40))
for i, im in enumerate(panels):
    sheet.paste(im, (i * 1310, 0))
sheet.save(HERE / "mock" / "arm_stretch_mock.png")
panels[1].save(HERE / "mock" / "arm_stretch_pose.png")
np.savez(HERE / "mock" / "arm_stretch_lines.npz", src=src_arm, dst=dst, hw=hw_arm)
print("saved mock/arm_stretch_mock.png")
