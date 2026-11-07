"""Build tracked motion fields (shake flow + time-offset maps) for the Reptilian drawing.

All coordinates are texture pixels of the 5040x2160 layer textures (origin top-left, y down),
which is the UV space every effect samples in.
"""
import json, math, os, struct, sys
import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

ART, OUT_TEX, OUT_PNG, REPORT = sys.argv[1:5]
TW, TH = 5040, 2160
F = 4                                   # working grid = quarter resolution
GW, GH = TW // F, TH // F
MW, MH = 1720, 720                      # mask resolution used by the original project

alpha_full = np.array(Image.open(ART).convert('RGBA'))[..., 3].astype(np.float32) / 255
alpha = np.array(Image.fromarray((alpha_full * 255).astype(np.uint8)).resize((GW, GH), Image.BOX)).astype(np.float32) / 255
gy, gx = np.mgrid[0:GH, 0:GW]
X = (gx + 0.5) * F                      # texture-pixel coordinates of each grid cell
Y = (gy + 0.5) * F

sil = ndimage.binary_closing(alpha > 0.25, iterations=2)
sil = ndimage.binary_fill_holes(sil)
sil = ndimage.binary_opening(sil, iterations=1)


def largest(mask):
    lab, n = ndimage.label(mask, structure=np.ones((3, 3)))
    if n == 0:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


def geodesic(region, roots):
    idx = -np.ones(region.shape, np.int64)
    n = int(region.sum())
    idx[region] = np.arange(n)
    rows, cols, w = [], [], []
    for dy, dx, c in [(0, 1, 1.0), (1, 0, 1.0), (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2))]:
        a = idx[max(0, -dy):GH - max(0, dy), max(0, -dx):GW - max(0, dx)]
        b = idx[max(0, dy):max(0, dy) + a.shape[0], max(0, dx):max(0, dx) + a.shape[1]]
        ok = (a >= 0) & (b >= 0)
        rows.append(a[ok]); cols.append(b[ok]); w.append(np.full(ok.sum(), c))
    r = np.concatenate(rows); c = np.concatenate(cols); ww = np.concatenate(w)
    g = coo_matrix((np.concatenate([ww, ww]), (np.concatenate([r, c]), np.concatenate([c, r]))), shape=(n, n)).tocsr()
    src = idx[roots & region]
    d = dijkstra(g, indices=src, min_only=True)
    out = np.full(region.shape, np.nan)
    out[region] = d * F
    return out


def blur_norm(v, w, sigma):
    num = ndimage.gaussian_filter(v * w, sigma)
    den = ndimage.gaussian_filter(w.astype(np.float32), sigma)
    return num / np.maximum(den, 1e-6), den


def stroke_normal(ref, sigma=10.0):
    """Unit vector perpendicular to the drawn strokes (structure tensor), sign aligned with ref."""
    a = ndimage.gaussian_filter(alpha, 1.0)
    gyy, gxx = np.gradient(a)
    jxx = ndimage.gaussian_filter(gxx * gxx, sigma)
    jyy = ndimage.gaussian_filter(gyy * gyy, sigma)
    jxy = ndimage.gaussian_filter(gxx * gyy, sigma)
    theta = 0.5 * np.arctan2(2 * jxy, jxx - jyy)     # dominant gradient direction = across the strokes
    nx, ny = np.cos(theta), np.sin(theta)
    flip = (nx * ref[0] + ny * ref[1]) < 0
    return np.where(flip, -nx, nx), np.where(flip, -ny, ny)


def tracked_field(name, region, roots, dmax, power, lag_along, lag_across=0.0, across_axis=None, sigma=3.0, spread=6.0,
                  normal=None, weight=None):
    region = largest(region)
    s = geodesic(region, roots)
    ok = region & np.isfinite(s)
    smax = float(np.nanmax(s[ok]))
    u = np.where(ok, s / smax, 0.0)
    w = ok.astype(np.float32)
    us, _ = blur_norm(u, w, 2.0)
    gyy, gxx = np.gradient(us)
    norm = np.hypot(gxx, gyy) + 1e-9
    tx, ty = gxx / norm, gyy / norm                 # tangent pointing from root to tip
    nx, ny = -ty, tx                                # bend direction, consistent side
    if normal is not None:
        nx, ny = normal
    mag = np.clip(u, 0, 1) ** power * dmax
    if weight is not None:
        mag = mag * weight
    dx, dy = nx * mag, ny * mag
    dx, _ = blur_norm(dx, w, sigma)
    dy, den = blur_norm(dy, w, sigma)
    # extend slightly past the silhouette so moving edges are not clipped, then fade out
    ex, den2 = blur_norm(dx, w, spread)
    ey, _ = blur_norm(dy, w, spread)
    fade = np.clip(den2 / 0.5, 0, 1) ** 1.5
    dx = np.where(ok, dx, ex * fade)
    dy = np.where(ok, dy, ey * fade)
    t = lag_along * u
    if across_axis is not None:
        a0, a1, coord = across_axis
        t = t + lag_across * np.clip((coord - a0) / (a1 - a0), 0, 1)
    t_ext, _ = blur_norm(t, w, spread)
    t = np.where(ok, t, t_ext)
    t = ndimage.gaussian_filter(t, 1.5)
    return dict(name=name, dx=dx, dy=dy, t=np.clip(t, 0, 1), region=ok, smax=smax,
                tip=np.unravel_index(np.nanargmax(np.where(ok, s, -1)), s.shape))


# ---- pieces -------------------------------------------------------------------------------
tail_region = sil & ((X < 3950) | ((Y > 1870) & (X < 4560)))
tail = tracked_field('tail', tail_region, X >= 4500, dmax=30, power=1.35, lag_along=0.30)

scalp_x = np.array([4080, 4300, 4500, 4700, 4900, 5040])
scalp_y = np.array([600, 590, 540, 470, 440, 440])
scalp = np.interp(X, scalp_x, scalp_y)
hair_region = sil & (Y < scalp) & (X > 4080)
# the body continues past the right edge of the frame, so motion fades out before reaching it
edge = np.clip((TW - X) / 220.0, 0, 1); edge = edge * edge * (3 - 2 * edge)
hair = tracked_field('hair', hair_region, (scalp - Y) < 3 * F, dmax=40, power=1.25, lag_along=0.20,
                     lag_across=0.35, across_axis=(4150, 5040, X), normal=stroke_normal((-0.7, -0.7)), weight=edge)

tendril_region = sil & (X > 3960) & (X < 4190) & (Y > 1300) & (Y < 1450)
tendril = tracked_field('tendrils', tendril_region, X >= 4165, dmax=18, power=1.3, lag_along=0.35, sigma=2.0, spread=4.0)

# head nod: small rigid rotation about the neck, fading out towards the body and away from the tail
P = np.array([4760.0, 1300.0])
head_dir = np.array([-0.62, -0.78]); head_dir /= np.linalg.norm(head_dir)
h = (X - P[0]) * head_dir[0] + (Y - P[1]) * head_dir[1]
wh = np.clip((h - 80) / (600 - 80), 0, 1); wh = wh * wh * (3 - 2 * wh)
tail_soft = ndimage.gaussian_filter(tail['region'].astype(np.float32), 10)
wh = wh * (1 - np.clip(tail_soft * 2, 0, 1)) * edge
theta = 0.012
hdx, hdy = -(Y - P[1]) * theta * wh, (X - P[0]) * theta * wh
hmag = np.hypot(hdx, hdy)
cap = 15.0                               # soft cap: the face moves ~10px, empty texture corners stay small
k = np.where(hmag > 0, cap * np.tanh(hmag / cap) / np.maximum(hmag, 1e-6), 1.0)
head = dict(name='head', dx=hdx * k, dy=hdy * k,
            t=np.zeros_like(wh), region=wh > 0.05, smax=0, tip=None)

# ---- texture writing (same layout as the editor-generated masks) --------------------------
def lz4_literals(data):
    n = len(data)
    out = bytearray()
    if n >= 15:
        out.append(0xF0)
        r = n - 15
        while r >= 255:
            out.append(255); r -= 255
        out.append(r)
    else:
        out.append(n << 4)
    return bytes(out) + data


def write_tex(path, pixels, fmt, neutral):
    h, w = pixels.shape[:2]
    raw = pixels.astype(np.uint8).tobytes()
    comp = lz4_literals(raw)
    hdr = b'TEXV0005\0TEXI0001\0' + struct.pack('<6i', fmt, 2, w, h, w, h) + bytes(neutral)
    hdr += b'TEXB0003\0' + struct.pack('<4i', 1, -1, 1, w) + struct.pack('<i', h)
    hdr += struct.pack('<3i', 1, len(raw), len(comp))
    open(path, 'wb').write(hdr + comp)


def to_mask_res(a):
    return np.array(Image.fromarray(a.astype(np.float32), 'F').resize((MW, MH), Image.BILINEAR))


report = {'fields': {}}
os.makedirs(OUT_TEX, exist_ok=True); os.makedirs(OUT_PNG, exist_ok=True)
for fld, speed in [(tail, 1.04), (hair, 1.3), (tendril, 1.6), (head, 0.8)]:
    dx = to_mask_res(fld['dx']); dy = to_mask_res(fld['dy'])
    amp2 = max(np.abs(dx).max() / TW, np.abs(dy).max() / TH) * 1.02
    strength = math.ceil(math.sqrt(amp2) * 1000) / 1000
    amp2 = strength ** 2
    fx = np.clip(dx / (amp2 * TW), -1, 1); fy = np.clip(dy / (amp2 * TH), -1, 1)
    rg = np.dstack([np.round((0.498 + fx / 2) * 255), np.round((0.498 + fy / 2) * 255)]).clip(0, 255)
    base = f"rig_{fld['name']}"
    write_tex(f'{OUT_TEX}/{base}_flow.tex', rg, 8, (0x7f, 0x7f, 0x00, 0xff))
    Image.fromarray(np.dstack([rg, np.zeros((MH, MW))]).astype(np.uint8)).save(f'{OUT_PNG}/{base}_flow.png')
    entry = {'strength': strength, 'speed': speed, 'max_px': round(float(np.hypot(dx, dy).max()), 1),
             'flow': f'masks/{base}_flow'}
    if fld['t'].max() > 0:
        tm = np.round(to_mask_res(fld['t']) * 255).clip(0, 255)
        write_tex(f'{OUT_TEX}/{base}_time.tex', tm, 9, (0, 0, 0, 0xff))
        Image.fromarray(tm.astype(np.uint8)).save(f'{OUT_PNG}/{base}_time.png')
        entry['time'] = f'masks/{base}_time'
    if fld['tip'] is not None:
        ty_, tx_ = fld['tip']; entry['tip_px'] = [int((tx_ + 0.5) * F), int((ty_ + 0.5) * F)]
        entry['length_px'] = round(fld['smax'])
    report['fields'][fld['name']] = entry
    print(fld['name'], entry)

# ---- spin-centre check: the right centre is where the pattern is most rotation-symmetric ----
def spin_score(c, size, ratio, angle, rot=0.35):
    r = size * TH
    n = int(r) + 2
    yy, xx = np.mgrid[-n:n + 1, -n:n + 1].astype(np.float32)
    ca, sa = math.cos(angle), math.sin(angle)
    ex = (xx * ca - yy * sa) * ratio; ey = xx * sa + yy * ca          # ellipse space (shader order)
    inside = np.hypot(ex, ey) < r * 0.92
    def rot2(a, b, t): return a * math.cos(t) - b * math.sin(t), a * math.sin(t) + b * math.cos(t)
    scores = []
    for t in (rot, -rot):
        rx, ry = rot2(ex, ey, t); rx = rx / ratio
        bx, by = rx * ca + ry * sa, -rx * sa + ry * ca                    # back to image space
        src = ndimage.map_coordinates(alpha_full, [c[1] + by, c[0] + bx], order=1)
        ref = ndimage.map_coordinates(alpha_full, [c[1] + yy, c[0] + xx], order=1)
        detail = ref[inside].std()
        if detail < 0.2:                       # flat ink or empty paper: rotation-invariant for the wrong reason
            return float('inf')
        scores.append(np.abs(src - ref)[inside].mean() / (detail + 0.05))
    return float(np.mean(scores))


SPINS = json.loads(os.environ.get('SPINS', '[]'))
report['spins'] = []
for sp in SPINS:
    c0 = np.array([sp['center'][0] * TW, sp['center'][1] * TH])
    base_score = spin_score(c0, sp['size'], sp['ratio'], sp['angle'])
    best = (base_score, c0)
    for dy_ in range(-24, 25, 2):
        for dx_ in range(-24, 25, 2):
            c = c0 + (dx_, dy_)
            sc = spin_score(c, sp['size'], sp['ratio'], sp['angle'])
            if sc < best[0]:
                best = (sc, c)
    c1 = best[1]
    for dy_ in (-1, 0, 1):
        for dx_ in (-1, 0, 1):
            c = best[1] + (dx_, dy_)
            sc = spin_score(c, sp['size'], sp['ratio'], sp['angle'])
            if sc < best[0]:
                best = (sc, c)
    res = {'name': sp['name'], 'id': sp['id'], 'old_px': [round(float(v), 1) for v in c0], 'new_px': [round(float(v), 1) for v in best[1]],
           'old_score': round(base_score, 4), 'new_score': round(best[0], 4),
           'shift_px': round(float(np.hypot(*(best[1] - c0))), 1),
           'new_uv': [round(float(best[1][0] / TW), 5), round(float(best[1][1] / TH), 5)]}
    res['adopt'] = res['new_score'] < res['old_score'] * 0.8 and res['shift_px'] >= 2
    report['spins'].append(res)
    print('spin', res)

json.dump(report, open(REPORT, 'w'), indent=2)
