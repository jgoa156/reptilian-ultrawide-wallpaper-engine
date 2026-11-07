"""Rig v2: strain-limited motion fields + cleaned-up versions of the author's masks.

Rule: no distortion map may change by more than STRAIN_MAX pixels of displacement per pixel of
distance (worst case over the oscillation, phase gradients included). Above ~0.3 the art visibly
stretches; above 1 it folds over itself, which is what made the hair and tail glitch.
"""
import json, math, os, struct, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ART, ORIG_MASKS, OUT_TEX, OUT_PNG, REPORT = sys.argv[1:6]
TW, TH = 5040, 2160
MW, MH = 1720, 720
SX, SY = TW / MW, TH / MH                    # texture px per mask px
STRAIN_MAX = 0.30
F = 4
GW, GH = TW // F, TH // F

alpha_full = np.array(Image.open(ART).convert('RGBA'))[..., 3].astype(np.float32) / 255
alpha = np.array(Image.fromarray((alpha_full * 255).astype(np.uint8)).resize((GW, GH), Image.BOX)).astype(np.float32) / 255
gy, gx = np.mgrid[0:GH, 0:GW]
X = (gx + 0.5) * F
Y = (gy + 0.5) * F
sil = ndimage.binary_fill_holes(ndimage.binary_closing(alpha > 0.25, iterations=2))
sil = ndimage.binary_opening(sil, iterations=1)
report = {'author': {}, 'rig': {}}


# ---------------------------------------------------------------- helpers
def to_mask(a):
    return np.array(Image.fromarray(a.astype(np.float32), 'F').resize((MW, MH), Image.BILINEAR))


def strain_mask(dx, dy, phase=None):
    """Worst-case strain on the mask grid (dx, dy in texture px)."""
    g = lambda a, ax, s: np.gradient(a, axis=ax) / s
    jd = np.sqrt(g(dx, 1, SX) ** 2 + g(dx, 0, SY) ** 2 + g(dy, 1, SX) ** 2 + g(dy, 0, SY) ** 2)
    if phase is None:
        return jd
    gp = np.hypot(g(phase, 1, SX), g(phase, 0, SY))
    return jd + np.hypot(dx, dy) * gp


def limit_vector(dx, dy, phase=None, target=STRAIN_MAX, start=0.0):
    """Blur a displacement field (on the mask grid) until it satisfies the strain limit."""
    sigma = start
    while True:
        bx = ndimage.gaussian_filter(dx, sigma) if sigma else dx
        by = ndimage.gaussian_filter(dy, sigma) if sigma else dy
        bp = (ndimage.gaussian_filter(phase, sigma) if sigma else phase) if phase is not None else None
        st = strain_mask(bx, by, bp).max()
        if st <= target or sigma > 60:
            return bx, by, bp, sigma, float(st)
        sigma += 1.0


def feather_scalar(m, disp_px, target=STRAIN_MAX):
    """Feather an opacity mask until disp_px * |grad m| stays under the strain limit (peak kept at 1)."""
    sigma = 0.0
    while True:
        b = ndimage.gaussian_filter(m, sigma) if sigma else m.copy()
        if b.max() > 0:
            b = b / b.max()
        gm = np.hypot(np.gradient(b, axis=1) / SX, np.gradient(b, axis=0) / SY)
        st = float((gm * disp_px).max())
        if st <= target or sigma > 40:
            return np.clip(b, 0, 1), sigma, st
        sigma += 0.5


def lz4_literals(data):
    n = len(data); out = bytearray()
    if n >= 15:
        out.append(0xF0); r = n - 15
        while r >= 255:
            out.append(255); r -= 255
        out.append(r)
    else:
        out.append(n << 4)
    return bytes(out) + data


def write_tex(name, pixels, fmt):
    h, w = pixels.shape[:2]
    raw = np.clip(np.round(pixels), 0, 255).astype(np.uint8).tobytes()
    comp = lz4_literals(raw)
    neutral = (0x7f, 0x7f, 0x00, 0xff) if fmt == 8 else (0, 0, 0, 0xff)
    hdr = b'TEXV0005\0TEXI0001\0' + struct.pack('<6i', fmt, 2, w, h, w, h) + bytes(neutral)
    hdr += b'TEXB0003\0' + struct.pack('<5i', 1, -1, 1, w, h) + struct.pack('<3i', 1, len(raw), len(comp))
    open(os.path.join(OUT_TEX, name + '.tex'), 'wb').write(hdr + comp)
    img = np.dstack([pixels, np.zeros(pixels.shape[:2])]) if fmt == 8 else pixels
    Image.fromarray(np.clip(np.round(img), 0, 255).astype(np.uint8)).save(os.path.join(OUT_PNG, name + '.png'))


def encode_flow(name, dx, dy):
    amp2 = max(np.abs(dx).max() / TW, np.abs(dy).max() / TH) * 1.02
    strength = math.ceil(math.sqrt(amp2) * 1000) / 1000
    amp2 = strength ** 2
    fx = np.clip(dx / (amp2 * TW), -1, 1); fy = np.clip(dy / (amp2 * TH), -1, 1)
    write_tex(name, np.dstack([(0.498 + fx / 2) * 255, (0.498 + fy / 2) * 255]), 8)
    return strength


def load_mask(n):
    return np.array(Image.open(os.path.join(ORIG_MASKS, n + '.png'))).astype(np.float32)


os.makedirs(OUT_TEX, exist_ok=True); os.makedirs(OUT_PNG, exist_ok=True)

# ================================================================ 1. the author's masks, cleaned
# foliage sway: peak displacement from the shader (amp = strength^2*0.005, 4 summed sines ~2.5x,
# direction vector (1/aspect, aspect) with aspect = 5040/2160 * ratio)
for mask, strength, ratio, label in [('foliagesway_mask_f6655407', 0.31, 2.77, 'Guelras'),
                                     ('foliagesway_mask_135029a1', 0.21, 2.25, 'Strings Hair'),
                                     ('foliagesway_mask_d3944eb2', 0.35, 0.30, 'Strings Back')]:
    m = load_mask(mask) / 255
    asp = TW / TH * ratio
    peak = strength ** 2 * 0.005 * 4.0         # the 4 summed sines can align (power < 2 keeps them near 1)
    disp = max(peak / asp * TW, peak * asp * TH)
    b, sigma, st = feather_scalar(m, disp)
    write_tex('fix_' + mask, b * 255, 9)
    report['author'][label] = {'mask': 'masks/fix_' + mask, 'peak_px': round(disp, 1), 'feather_sigma_px': round(sigma * SX, 1), 'strain': round(st, 2)}

# iris: offset up to ~2.5 * scale * 0.001 UV
for mask, scale, label in [('iris_mask_13f08b0d', 1.0, 'Olho menor #1'), ('iris_mask_71a51a31', 0.38, 'Little Eyes')]:
    m = load_mask(mask) / 255
    disp = 2.5 * scale * 0.001 * TW
    b, sigma, st = feather_scalar(m, disp, target=0.5)       # eyes may stay a little crisper
    write_tex('fix_' + mask, b * 255, 9)
    report['author'][label] = {'mask': 'masks/fix_' + mask, 'peak_px': round(disp, 1), 'feather_sigma_px': round(sigma * SX, 1), 'strain': round(st, 2)}

# waterwaves (tail edge shimmer): strength^2 UV
m = load_mask('waterwaves_mask_c13e3058') / 255
b, sigma, st = feather_scalar(m, 0.02 ** 2 * TW)
write_tex('fix_waterwaves_mask_c13e3058', b * 255, 9)
report['author']['Tail edge shimmer'] = {'mask': 'masks/fix_waterwaves_mask_c13e3058', 'feather_sigma_px': round(sigma * SX, 1), 'strain': round(st, 2)}

# radial blur on the gills: soft mask edge, and the blur centre moved onto the gills themselves
m = load_mask('blur_radial_gaussian_mask_4da4329b') / 255
b = ndimage.gaussian_filter(m, 4); b /= b.max()
write_tex('fix_blur_radial_gaussian_mask_4da4329b', b * 255, 9)
cy, cx = ndimage.center_of_mass(m)
report['author']['Guelras (2)'] = {'mask': 'masks/fix_blur_radial_gaussian_mask_4da4329b',
                                   'center_uv': [round((cx + 0.5) / MW, 5), round((cy + 0.5) / MH, 5)]}

# balance shake: keep the painted directions, smooth the vector field
rg = load_mask('shake_mask_647b9b30')[..., :2] / 255
fl = (rg - 0.498) * 2
amp2 = 0.04 ** 2
bx, by, _, sigma, st = limit_vector(fl[..., 0] * amp2 * TW, fl[..., 1] * amp2 * TH)
s = encode_flow('fix_shake_mask_647b9b30', bx, by)
report['author']['Balance (General)'] = {'flow': 'masks/fix_shake_mask_647b9b30', 'strength': s, 'smooth_sigma_px': round(sigma * SX, 1),
                                         'strain': round(st, 2), 'peak_px': round(float(np.hypot(bx, by).max()), 1)}

# ================================================================ 2. tracked rig (on the quarter grid)
def largest(mask):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return mask
    return lab == (1 + int(np.argmax(ndimage.sum(mask, lab, range(1, n + 1)))))


def geodesic(region, roots):
    idx = -np.ones(region.shape, np.int64); n = int(region.sum()); idx[region] = np.arange(n)
    rows, cols, w = [], [], []
    for dy, dx, c in [(0, 1, 1.0), (1, 0, 1.0), (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2))]:
        a = idx[max(0, -dy):GH - max(0, dy), max(0, -dx):GW - max(0, dx)]
        b = idx[max(0, dy):max(0, dy) + a.shape[0], max(0, dx):max(0, dx) + a.shape[1]]
        ok = (a >= 0) & (b >= 0)
        rows.append(a[ok]); cols.append(b[ok]); w.append(np.full(ok.sum(), c))
    r = np.concatenate(rows); c = np.concatenate(cols); ww = np.concatenate(w)
    g = coo_matrix((np.concatenate([ww, ww]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(n, n)).tocsr()
    d = dijkstra(g, indices=idx[roots & region], min_only=True)
    out = np.full(region.shape, np.nan); out[region] = d * F
    return out


def blur_norm(v, w, sigma):
    return ndimage.gaussian_filter(v * w, sigma) / np.maximum(ndimage.gaussian_filter(w, sigma), 1e-6)


def stroke_axes(sigma=10.0):
    a = ndimage.gaussian_filter(alpha, 1.0)
    gyy, gxx = np.gradient(a)
    jxx = ndimage.gaussian_filter(gxx * gxx, sigma); jyy = ndimage.gaussian_filter(gyy * gyy, sigma)
    jxy = ndimage.gaussian_filter(gxx * gyy, sigma)
    th = 0.5 * np.arctan2(2 * jxy, jxx - jyy)            # across-stroke direction
    return np.cos(th), np.sin(th)


NX_S, NY_S = stroke_axes()
edge = np.clip((TW - X) / 220.0, 0, 1); edge = edge * edge * (3 - 2 * edge)


def appendage(region, roots, dmax, power, lag_along, use_strokes=False, lag_across=0.0, across=None, weight=None):
    region = largest(region)
    s = geodesic(region, roots)
    ok = region & np.isfinite(s)
    u = np.where(ok, s / np.nanmax(s[ok]), 0.0)
    w = ok.astype(np.float32)
    us = blur_norm(u, w, 2.0)
    gyy, gxx = np.gradient(us)
    nrm = np.hypot(gxx, gyy) + 1e-9
    gnx, gny = -gyy / nrm, gxx / nrm                     # bend direction from the shape's own path
    if use_strokes:                                      # follow the drawn strokes, but never against the path
        sgn = np.sign(NX_S * gnx + NY_S * gny); sgn[sgn == 0] = 1
        nx, ny = NX_S * sgn + gnx, NY_S * sgn + gny
        n2 = np.hypot(nx, ny) + 1e-9; nx, ny = nx / n2, ny / n2
    else:
        nx, ny = gnx, gny
    mag = np.clip(u, 0, 1) ** power * dmax * (weight if weight is not None else 1)
    dx, dy = blur_norm(nx * mag, w, 3), blur_norm(ny * mag, w, 3)
    # carry a wide band of the surroundings along with the tips (no tearing at the silhouette)
    dist = ndimage.distance_transform_edt(~ok) * F
    L = max(3.0 * dmax, 60.0)
    fade = np.exp(-(dist / L) ** 2)
    ex, ey = blur_norm(dx, w, L / F), blur_norm(dy, w, L / F)
    dx = np.where(ok, dx, ex * fade); dy = np.where(ok, dy, ey * fade)
    t = lag_along * u
    if across is not None:
        a0, a1 = across
        t = t + lag_across * np.clip((X - a0) / (a1 - a0), 0, 1)
    t = np.where(ok, t, blur_norm(t, w, L / F))
    return dx, dy, t, ok


# tail
tail_region = sil & ((X < 3950) | ((Y > 1870) & (X < 4560)))
t_dx, t_dy, t_ph, t_ok = appendage(tail_region, X >= 4500, dmax=30, power=1.35, lag_along=0.22)

# hair crest + back mane
scalp = np.interp(X, [4080, 4300, 4500, 4700, 4900, 5040], [600, 590, 540, 470, 440, 440])
h_dx, h_dy, h_ph, h_ok = appendage(sil & (Y < scalp) & (X > 4080), (scalp - Y) < 3 * F, dmax=34, power=1.3,
                                   lag_along=0.15, use_strokes=True, lag_across=0.20, across=(4150, 5040), weight=edge)
# mouth tendrils
d_dx, d_dy, d_ph, d_ok = appendage(sil & (X > 3960) & (X < 4190) & (Y > 1300) & (Y < 1450), X >= 4165,
                                   dmax=16, power=1.3, lag_along=0.30)

# head nod: rigid rotation about the neck
P = np.array([4760.0, 1300.0]); hd = np.array([-0.62, -0.78]); hd /= np.linalg.norm(hd)
hh = (X - P[0]) * hd[0] + (Y - P[1]) * hd[1]
wh = np.clip((hh - 80) / 520, 0, 1); wh = wh * wh * (3 - 2 * wh)
wh *= (1 - np.clip(ndimage.gaussian_filter(t_ok.astype(np.float32), 10) * 2, 0, 1)) * edge
nod_dx, nod_dy = -(Y - P[1]) * 0.011 * wh, (X - P[0]) * 0.011 * wh
nm = np.hypot(nod_dx, nod_dy); k = np.where(nm > 0, 14 * np.tanh(nm / 14) / np.maximum(nm, 1e-6), 1)
nod_dx, nod_dy = nod_dx * k, nod_dy * k


def bump(cx, cy, rx, ry):
    return np.exp(-(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2))


body_edge = np.clip((TW - X) / 90.0, 0, 1)
# abdomen: slow breathing, radial about the belly centre
wb = bump(4580, 1560, 230, 330) * body_edge
ab_dx, ab_dy = (X - 4580) / 230 * 6 * wb, (Y - 1560) / 330 * 6 * wb
# guts coils: slither along the drawn bands, travelling around the coil
cxg, cyg = 4935, 1480
wg = bump(cxg, cyg, 150, 170) * body_edge
tx, ty = -NY_S, NX_S                                       # along-stroke direction
ccw = np.sign(tx * -(Y - cyg) + ty * (X - cxg)); ccw[ccw == 0] = 1
g_dx, g_dy = tx * ccw * 4 * wg, ty * ccw * 4 * wg
g_ph = (np.arctan2(Y - cyg, X - cxg) / (2 * math.pi)) % 1 * 0.5
# gut tube: contraction wave travelling down the ribbed tube (vertical only, nothing pushed past the frame edge)
wt = np.exp(-((X - 4960) / 70) ** 2) * np.clip((Y - 1640) / 80, 0, 1) * body_edge
tube_dy = 4 * wt
tube_ph = np.clip((Y - 1640) / 520, 0, 1) * 0.6

# ---------------------------------------------------------------- combine into three passes
def combine(parts):
    """parts: (dx, dy, phase); phase-weighted blend so overlapping parts keep their own timing."""
    dx = sum(p[0] for p in parts); dy = sum(p[1] for p in parts)
    wsum = sum(np.hypot(p[0], p[1]) for p in parts) + 1e-6
    ph = sum(np.hypot(p[0], p[1]) * p[2] for p in parts) / wsum
    return dx, dy, ph


zero = np.zeros_like(X, dtype=np.float64)
passes = {
    'appendages': (combine([(h_dx, h_dy, h_ph), (d_dx, d_dy, d_ph)]), 1.3),
    'tail': (combine([(t_dx, t_dy, t_ph)]), 1.04),
    'body': (combine([(nod_dx, nod_dy, zero), (ab_dx, ab_dy, zero + 0.5), (g_dx, g_dy, g_ph), (zero, tube_dy, tube_ph)]), 0.9),
}
for name, ((dx, dy, ph), speed) in passes.items():
    mdx, mdy, mph = to_mask(dx), to_mask(dy), to_mask(ph)
    before = float(strain_mask(mdx, mdy, mph * 2 * math.pi).max())
    bx, by, bp, sigma, st = limit_vector(mdx, mdy, mph * 2 * math.pi, start=1.0)
    bp = np.clip(bp / (2 * math.pi), 0, 1)
    strength = encode_flow(f'rig2_{name}_flow', bx, by)
    write_tex(f'rig2_{name}_time', bp * 255, 9)
    report['rig'][name] = {'flow': f'masks/rig2_{name}_flow', 'time': f'masks/rig2_{name}_time', 'strength': strength,
                           'speed': speed, 'max_px': round(float(np.hypot(bx, by).max()), 1),
                           'strain_before': round(before, 2), 'strain_after': round(st, 2), 'smooth_sigma_px': round(sigma * SX, 1)}

json.dump(report, open(REPORT, 'w'), indent=1)
print(json.dumps(report, indent=1))
