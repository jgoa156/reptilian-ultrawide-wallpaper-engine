"""Rig v3 for the hair crest + mouth tendrils: big, wavy, tear-free.

Hair: the crest moves as one coherent mass of fronds. Displacement grows with smooth distance from the
scalp (not per-spike path length, which made neighbouring spikes disagree), bends perpendicular to the
heavily smoothed stroke flow, and a travelling wave runs from root to tip.
Tendrils: geodesic bend as before, limited on their own so the hair's smoothing doesn't flatten them.
"""
import json, math, os, struct, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ART, OUT_TEX, OUT_PNG, REPORT = sys.argv[1:5]
HAIR_TIP, HAIR_LAG, HAIR_ACROSS = (float(x) for x in sys.argv[5:8])
TW, TH = 5040, 2160; MW, MH = 1720, 720; SX, SY = TW / MW, TH / MH
STRAIN_MAX = 0.30
F = 4; GW, GH = TW // F, TH // F
alpha = np.array(Image.open(ART).convert('RGBA').resize((GW, GH), Image.BOX))[..., 3].astype(np.float32) / 255
gy, gx = np.mgrid[0:GH, 0:GW]; X = (gx + 0.5) * F; Y = (gy + 0.5) * F
sil = ndimage.binary_opening(ndimage.binary_fill_holes(ndimage.binary_closing(alpha > 0.25, iterations=2)), iterations=1)
smooth = lambda x, e0, e1: np.clip((x - e0) / (e1 - e0), 0, 1) ** 2 * (3 - 2 * np.clip((x - e0) / (e1 - e0), 0, 1))
to_mask = lambda a: np.array(Image.fromarray(a.astype(np.float32), 'F').resize((MW, MH), Image.BILINEAR))


def strain(dx, dy, ph=None):
    g = lambda a, ax, s: np.gradient(a, axis=ax) / s
    j = np.sqrt(g(dx, 1, SX) ** 2 + g(dx, 0, SY) ** 2 + g(dy, 1, SX) ** 2 + g(dy, 0, SY) ** 2)
    return j if ph is None else j + np.hypot(dx, dy) * np.hypot(g(ph, 1, SX), g(ph, 0, SY))


def limit(dx, dy, ph, target=STRAIN_MAX):
    sigma = 0.0
    while True:
        f = (lambda a: ndimage.gaussian_filter(a, sigma)) if sigma else (lambda a: a)
        bx, by, bp = f(dx), f(dy), f(ph)
        st = float(strain(bx, by, bp).max())
        if st <= target or sigma > 60:
            return bx, by, bp, sigma, st
        sigma += 0.5


# ---------------------------------------------------------------- hair crest
scalp_x = np.array([4080, 4300, 4500, 4700, 4900, 5040]); scalp_y = np.array([600, 590, 540, 470, 440, 440])
scalp = np.interp(X, scalp_x, scalp_y)
line = np.zeros_like(sil)
for xi in range(GW):
    yi = int(np.interp((xi + 0.5) * F, scalp_x, scalp_y) / F)
    if 4080 <= (xi + 0.5) * F:
        line[max(0, yi - 1):yi + 1, xi] = True
h = ndimage.distance_transform_edt(~line) * F * (Y < scalp)            # smooth height above the scalp
H = float(np.percentile(h[sil & (Y < scalp) & (X > 4080)], 99.5))
u = np.clip(h / H, 0, 1.15)
# outward direction = gradient of height; bend reference = perpendicular to it
hs = ndimage.gaussian_filter(h, 6)
oy, ox = np.gradient(hs); on = np.hypot(ox, oy) + 1e-9; ox, oy = ox / on, oy / on
rx, ry = -oy, ox
# stroke flow, smoothed over ~100px, aligned with the reference so neighbours never oppose
a = ndimage.gaussian_filter(alpha, 1.0); gyy, gxx = np.gradient(a)
J = [ndimage.gaussian_filter(q, 25) for q in (gxx * gxx, gyy * gyy, gxx * gyy)]
th = 0.5 * np.arctan2(2 * J[2], J[0] - J[1]); nx, ny = np.cos(th), np.sin(th)
sg = np.sign(nx * rx + ny * ry); sg[sg == 0] = 1
bx_, by_ = nx * sg + rx, ny * sg + ry; bn = np.hypot(bx_, by_) + 1e-9; bx_, by_ = bx_ / bn, by_ / bn
bx_, by_ = ndimage.gaussian_filter(bx_, 12), ndimage.gaussian_filter(by_, 12)
bn = np.hypot(bx_, by_) + 1e-9; bx_, by_ = bx_ / bn, by_ / bn
w = smooth(X, 3980, 4160) * smooth(TW - X, 0, 220) * (Y < scalp + 40)   # fade toward the face front and the frame edge
w = ndimage.gaussian_filter(w.astype(np.float32), 6)
mag = HAIR_TIP * u ** 1.2 * w
hdx, hdy = bx_ * mag, by_ * mag
hph = (HAIR_LAG * np.clip(u, 0, 1) + HAIR_ACROSS * np.clip((X - 4150) / 890, 0, 1)) * 2 * math.pi

# ---------------------------------------------------------------- tendrils (geodesic bend)
def geodesic(region, roots):
    idx = -np.ones(region.shape, np.int64); n = int(region.sum()); idx[region] = np.arange(n)
    rows, cols, wt = [], [], []
    for dy, dx, c in [(0, 1, 1.0), (1, 0, 1.0), (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2))]:
        A = idx[max(0, -dy):GH - max(0, dy), max(0, -dx):GW - max(0, dx)]
        B = idx[max(0, dy):max(0, dy) + A.shape[0], max(0, dx):max(0, dx) + A.shape[1]]
        ok = (A >= 0) & (B >= 0); rows.append(A[ok]); cols.append(B[ok]); wt.append(np.full(ok.sum(), c))
    r = np.concatenate(rows); c = np.concatenate(cols); ww = np.concatenate(wt)
    g = coo_matrix((np.concatenate([ww, ww]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(n, n)).tocsr()
    d = dijkstra(g, indices=idx[roots & region], min_only=True)
    out = np.full(region.shape, np.nan); out[region] = d * F; return out

treg = sil & (X > 3960) & (X < 4190) & (Y > 1300) & (Y < 1450)
lab, n = ndimage.label(treg, structure=np.ones((3, 3)))
treg = lab == (1 + int(np.argmax(ndimage.sum(treg, lab, range(1, n + 1)))))
s = geodesic(treg, X >= 4165); ok = treg & np.isfinite(s)
tu = np.where(ok, s / np.nanmax(s[ok]), 0.0); wt_ = ok.astype(np.float32)
bn_ = lambda v, sg_: ndimage.gaussian_filter(v * wt_, sg_) / np.maximum(ndimage.gaussian_filter(wt_, sg_), 1e-6)
us = bn_(tu, 2.0); gy2, gx2 = np.gradient(us); nn = np.hypot(gx2, gy2) + 1e-9
tnx, tny = -gy2 / nn, gx2 / nn
tm = tu ** 1.2 * 18
tdx, tdy = bn_(tnx * tm, 2), bn_(tny * tm, 2)
dist = ndimage.distance_transform_edt(~ok) * F; L = 70.0
fade = np.exp(-(dist / L) ** 2)
tdx = np.where(ok, tdx, bn_(tdx, L / F) * fade); tdy = np.where(ok, tdy, bn_(tdy, L / F) * fade)
tph = np.where(ok, 0.6 * tu, bn_(0.6 * tu, L / F)) * 2 * math.pi

# ---------------------------------------------------------------- limit each part on its own, then combine
report = {}
H_ = limit(to_mask(hdx), to_mask(hdy), to_mask(hph))
T_ = limit(to_mask(tdx), to_mask(tdy), to_mask(tph))
report['hair'] = {'tip_target_px': HAIR_TIP, 'max_px': round(float(np.hypot(H_[0], H_[1]).max()), 1), 'smooth_sigma_px': round(H_[3] * SX, 1), 'strain': round(H_[4], 2)}
report['tendrils'] = {'max_px': round(float(np.hypot(T_[0], T_[1]).max()), 1), 'smooth_sigma_px': round(T_[3] * SX, 1), 'strain': round(T_[4], 2)}
dx = H_[0] + T_[0]; dy = H_[1] + T_[1]
wh, wtd = np.hypot(H_[0], H_[1]), np.hypot(T_[0], T_[1])
ph = (wh * H_[2] + wtd * T_[2]) / (wh + wtd + 1e-6)
report['combined_strain'] = round(float(strain(dx, dy, ph).max()), 2)


def lz4_literals(data):
    n = len(data); out = bytearray()
    if n >= 15:
        out.append(0xF0); r = n - 15
        while r >= 255: out.append(255); r -= 255
        out.append(r)
    else:
        out.append(n << 4)
    return bytes(out) + data


def write_tex(name, pixels, fmt):
    hgt, wid = pixels.shape[:2]
    raw = np.clip(np.round(pixels), 0, 255).astype(np.uint8).tobytes(); comp = lz4_literals(raw)
    neutral = (0x7f, 0x7f, 0x00, 0xff) if fmt == 8 else (0, 0, 0, 0xff)
    hdr = b'TEXV0005\0TEXI0001\0' + struct.pack('<6i', fmt, 2, wid, hgt, wid, hgt) + bytes(neutral)
    hdr += b'TEXB0003\0' + struct.pack('<5i', 1, -1, 1, wid, hgt) + struct.pack('<3i', 1, len(raw), len(comp))
    open(os.path.join(OUT_TEX, name + '.tex'), 'wb').write(hdr + comp)
    img = np.dstack([pixels, np.zeros(pixels.shape[:2])]) if fmt == 8 else pixels
    Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8)).save(os.path.join(OUT_PNG, name + '.png'))


os.makedirs(OUT_TEX, exist_ok=True); os.makedirs(OUT_PNG, exist_ok=True)
amp2 = max(np.abs(dx).max() / TW, np.abs(dy).max() / TH) * 1.02
strength = math.ceil(math.sqrt(amp2) * 1000) / 1000; amp2 = strength ** 2
fx = np.clip(dx / (amp2 * TW), -1, 1); fy = np.clip(dy / (amp2 * TH), -1, 1)
write_tex('rig3_appendages_flow', np.dstack([(0.498 + fx / 2) * 255, (0.498 + fy / 2) * 255]), 8)
phase01 = np.clip(ph / (2 * math.pi), 0, 1)
write_tex('rig3_appendages_time', phase01 * 255, 9)
report.update({'strength': strength, 'speed': 1.3, 'flow': 'masks/rig3_appendages_flow', 'time': 'masks/rig3_appendages_time',
               'phase_range': [round(float(phase01.min()), 3), round(float(phase01.max()), 3)]})
json.dump(report, open(REPORT, 'w'), indent=1)
print(json.dumps(report, indent=1))
