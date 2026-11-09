"""Still mock: the whole arm slid down along the user's red stroke, its base out of view below the
screen (no stretch), like a tonearm reaching onto the record. Built from mock/arm_stretch_mock.py.
Usage: python mock/arm_slide_mock.py [stroke|centre]

Original notes (arm_stretch_mock.py):

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

# destination: the arm keeps its length and slides along one long track: up from below the
# screen's bottom edge, along the stroke, then on to the mandala centre. TIP picks where the tip
# stops on the track ("stroke" = the stroke's end, "centre" = the mandala centre).
r_pts, r_len = spline(red, 400, s=3000)
r_pts += BASE - r_pts[0]
t0 = r_pts[6] - r_pts[0]; t0 /= np.linalg.norm(t0)
back, p, dvec = [], r_pts[0].copy(), -t0
for i in range(1, 161):                      # 800 px behind the stroke's start, bending down out of view
    k_ = min(i / 80, 1.0); k_ = k_ * k_ * (3 - 2 * k_)
    dv = (1 - k_) * dvec + k_ * np.array([0.25 * np.sign(dvec[0]), 1.0])
    p = p + 5 * dv / np.linalg.norm(dv)
    back.append(p.copy())
fwd = r_pts[-1] + np.outer(np.linspace(0, 1, 40)[1:], CENTRE - r_pts[-1])
fwd2 = CENTRE + np.outer(np.linspace(0, 400, 40)[1:], (CENTRE - r_pts[-1]) / np.linalg.norm(CENTRE - r_pts[-1]))
if (sys.argv[1] if len(sys.argv) > 1 else "stroke") == "centre":
    # straight up from below the bottom edge (in the gap between the coil and the mandala) to the
    # centre, bowed like the stroke
    E = np.array([3950.0, 2700.0])
    q = np.linspace(0, 1, 200)[:, None]
    mid = (E + CENTRE) / 2 + np.array([180.0, 120.0])
    track_pts = (1 - q) ** 2 * E + 2 * (1 - q) * q * mid + q ** 2 * CENTRE
    track_pts = np.vstack([track_pts, CENTRE + np.outer(np.linspace(0, 300, 30)[1:], (CENTRE - mid) / np.linalg.norm(CENTRE - mid))])
    track, tlen = spline(track_pts, 3000, s=0)
else:
    track, tlen = spline(np.vstack([np.array(back[::-1]), r_pts, fwd, fwd2]), 3000, s=8000)
seg = np.r_[0, np.cumsum(np.hypot(*np.diff(track, axis=0).T))]
TIP = sys.argv[1] if len(sys.argv) > 1 else "stroke"
aim = r_pts[-1] if TIP == "stroke" else CENTRE
s_tip = seg[int(np.argmin(np.hypot(*(track - aim).T)))]
uu = np.linspace(s_tip - L, s_tip, N)
dst = np.c_[np.interp(uu, seg, track[:, 0]), np.interp(uu, seg, track[:, 1])]
below = int((dst[:, 1] > TH).sum() / N * 100)
print(f"tip at {TIP}: arm {L:.0f} px, {below}% of its length below the screen edge; tip {dst[-1].round()}, "
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


im = Image.fromarray(np.clip(posed, 0, 255).astype(np.uint8))
dr = ImageDraw.Draw(im)
dr.ellipse([CENTRE[0] - 22, CENTRE[1] - 22, CENTRE[0] + 22, CENTRE[1] + 22], outline=(237, 28, 36), width=8)
ImageOps.mirror(im).crop((0, 300, 3200, TH)).resize((1600, 930), Image.LANCZOS).save(HERE / "mock" / f"arm_slide_{TIP}.png")
np.savez(HERE / "mock" / f"arm_slide_{TIP}.npz", src=src_arm, dst=dst, hw=hw_arm)
print("saved mock/arm_stretch_mock.png")
