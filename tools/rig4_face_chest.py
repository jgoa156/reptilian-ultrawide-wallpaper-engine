"""Rig v4: face animation + stronger chest-corner motion, strain-limited.

Builds on rig v2 (run in-process to reuse its fields; its own outputs go to a temp dir):

  * Body pass (rig4_body_*, replaces rig2_body_*, speed 0.9): rig2's limited body field
    plus, each limited on its own before adding:
      - shoulder/back-stripe muscle flex, rippling toward the corner
      - stronger peristalsis in the ribbed tube (4 -> 8 px)
      - stronger coil slither (4 -> 6 px)
      - a slow heave in the lower-right corner
    Horizontal motion fades out over the last 220 px at the right frame edge, and the new
    parts fade out over the last 150 px at the bottom edge.
  * Face pass (rig4_face_*, NEW, speed 1.6), at half texture resolution (2520x1080) so
    small features survive:
      - jaw/snout open-close: rotation about the hinge
      - brow ridge lift
      - four cheek/face-plate twitches with staggered timing
      - ring eye dilation
      - forehead dots: a ripple running down the column
  * Blink masks (rig4_blink_*), for masked alpha pulses on K: the forehead dots and the
    ring eye blink in sequence, revealing the cyan/magenta ink copies underneath.

Then a combined check: all four rig passes + Balance, sampled over time with their real
speeds, worst-case strain reported per region.

Usage: python tools/rig4_face_chest.py <out_tex_dir> <out_png_dir> <report.json>
"""
import json
import math
import os
import runpy
import struct
import sys
import tempfile

import numpy as np
from PIL import Image
from scipy import ndimage

OUT_TEX, OUT_PNG, REPORT = sys.argv[1:4]
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(HERE, 'recovered_original', 'Sem título-1_Prancheta 1.png')
TW, TH = 5040, 2160
STRAIN_MAX = 0.30
os.makedirs(OUT_TEX, exist_ok=True)
os.makedirs(OUT_PNG, exist_ok=True)
report = {}

# ---------------------------------------------------------------- rig v2, in-process
tmp = tempfile.mkdtemp()
_argv = sys.argv
sys.argv = ['rig2.py', ART, os.path.join(HERE, 'recovered_original', 'masks'),
            os.path.join(tmp, 'tex'), os.path.join(tmp, 'png'), os.path.join(tmp, 'r.json')]
import contextlib, io
with contextlib.redirect_stdout(io.StringIO()):
    R = runpy.run_path(os.path.join(HERE, 'tools', 'rig2.py'))
sys.argv = _argv
rep2 = json.load(open(os.path.join(tmp, 'r.json')))
assert abs(rep2['rig']['body']['strength'] - 0.082) < 1e-9, 'rig2 did not reproduce the live body pass'
body_bx, body_by, body_bp = R['bx'], R['by'], R['bp']       # last pass in rig2's loop = body
MW, MH = R['MW'], R['MH']
X, Y = R['X'], R['Y']                                        # rig2 quarter grid, texture px
to_mask = R['to_mask']
bump = R['bump']
NX_S, NY_S = R['NX_S'], R['NY_S']


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def strain(dx, dy, ph, sx, sy):
    """Worst-case strain of a single shake field (dx, dy px; ph radians) on a grid with
    sx, sy texture px per cell."""
    g = lambda a, ax, s: np.gradient(a, axis=ax) / s
    j = np.sqrt(g(dx, 1, sx) ** 2 + g(dx, 0, sy) ** 2 + g(dy, 1, sx) ** 2 + g(dy, 0, sy) ** 2)
    return j + np.hypot(dx, dy) * np.hypot(g(ph, 1, sx), g(ph, 0, sy))


def limit(dx, dy, ph, sx, sy, target):
    """Blur (dx, dy, phase in cycles) until the field is under `target`."""
    sigma = 0.0
    while True:
        f = (lambda a: ndimage.gaussian_filter(a, sigma)) if sigma else (lambda a: a)
        bx, by, bp = f(dx), f(dy), f(ph)
        st = float(strain(bx, by, bp * 2 * math.pi, sx, sy).max())
        if st <= target or sigma > 60:
            return bx, by, bp, sigma, st
        sigma += 0.5


def combine(parts):
    dx = sum(p[0] for p in parts)
    dy = sum(p[1] for p in parts)
    w = sum(np.hypot(p[0], p[1]) for p in parts) + 1e-6
    ph = sum(np.hypot(p[0], p[1]) * p[2] for p in parts) / w
    return dx, dy, ph


def lz4_literals(data):
    n = len(data)
    out = bytearray()
    if n >= 15:
        out.append(0xF0)
        r = n - 15
        while r >= 255:
            out.append(255)
            r -= 255
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
    fx = np.clip(dx / (amp2 * TW), -1, 1)
    fy = np.clip(dy / (amp2 * TH), -1, 1)
    write_tex(name, np.dstack([(0.498 + fx / 2) * 255, (0.498 + fy / 2) * 255]), 8)
    # what the shader will actually reproduce after 8-bit quantisation
    qx = (np.round((0.498 + fx / 2) * 255) / 255 - 0.498) * 2 * amp2 * TW
    qy = (np.round((0.498 + fy / 2) * 255) / 255 - 0.498) * 2 * amp2 * TH
    return strength, qx, qy


# ================================================================ body pass additions
SXM, SYM = TW / MW, TH / MH
right = smooth((TW - X) / 220.0)                              # horizontal fade at the frame edge
bottom = smooth((TH - Y) / 150.0)

# shoulder / back stripes: slow muscle flex, rippling toward the corner
w_sh = bump(4880, 950, 220, 300)
sh = (-4 * w_sh * right, 6 * w_sh * bottom, 0.10 + 0.30 * np.clip((X - 4660) / 380, 0, 1))
# ribbed tube: extra contraction on top of rig2's 4 px (same travelling phase)
wt = np.exp(-((X - 4960) / 70) ** 2) * np.clip((Y - 1640) / 80, 0, 1) * R['body_edge']
tube = (0 * X, 4 * wt * bottom, R['tube_ph'])
# coils: +50% slither, same travelling phase
coil = (0.5 * R['g_dx'], 0.5 * R['g_dy'], R['g_ph'])
# lower-right corner heave
w_co = bump(4930, 2010, 170, 150) * bottom
corner = (-1.5 * w_co * right, -5 * w_co, 0.6 + 0 * X)

new_parts, rep_parts = [], {}
for name, (dx, dy, ph) in {'shoulder_flex': sh, 'tube_extra': tube, 'coil_extra': coil,
                           'corner_heave': corner}.items():
    mdx, mdy, mph = to_mask(dx), to_mask(dy), to_mask(ph)
    bx, by, bp, sg, st = limit(mdx, mdy, mph, SXM, SYM, 0.18)
    new_parts.append((bx, by, bp))
    rep_parts[name] = {'max_px': round(float(np.hypot(bx, by).max()), 1),
                       'smooth_sigma_px': round(sg * SXM, 1), 'strain': round(st, 2)}

scale = 1.0
while True:
    parts = [(body_bx, body_by, body_bp)] + [(p[0] * scale, p[1] * scale, p[2]) for p in new_parts]
    cdx, cdy, cph = combine(parts)
    st = float(strain(cdx, cdy, cph * 2 * math.pi, SXM, SYM).max())
    if st <= STRAIN_MAX or scale < 0.3:
        break
    scale *= 0.93
cph = np.clip(cph, 0, 0.995)
s_body, qx, qy = encode_flow('rig4_body_flow', cdx, cdy)
write_tex('rig4_body_time', cph * 255, 9)
report['body'] = {'flow': 'masks/rig4_body_flow', 'time': 'masks/rig4_body_time', 'speed': 0.9,
                  'strength': s_body, 'strain': round(st, 2), 'new_parts_scale': round(scale, 2),
                  'parts': rep_parts, 'max_px': round(float(np.hypot(cdx, cdy).max()), 1)}
body_final = (qx, qy, cph)

# ================================================================ face pass (half res)
FW, FH = TW // 2, TH // 2
SXF, SYF = TW / FW, TH / FH
gy, gx = np.mgrid[0:FH, 0:FW]
Xf, Yf = (gx + 0.5) * SXF, (gy + 0.5) * SYF


def fbump(cx, cy, rx, ry):
    return np.exp(-(((Xf - cx) / rx) ** 2 + ((Yf - cy) / ry) ** 2))


face = {}
# jaw / snout: rotate the lower snout about the hinge; tendrils ride along
hx, hy = 4340.0, 1150.0
wj = smooth((Yf - 1110) / 90) * smooth((4370 - Xf) / 90) * smooth((Xf - 3990) / 120) * smooth((1450 - Yf) / 130)
th = 0.028
jdx, jdy = -(Yf - hy) * th * wj, (Xf - hx) * th * wj
jm = np.hypot(jdx, jdy)
k = np.where(jm > 0, 8 * np.tanh(jm / 8) / np.maximum(jm, 1e-6), 1)      # cap ~8 px; tapers off before the tendril tips (they swing on their own)
face['jaw'] = (jdx * k, jdy * k, 0.0 + 0 * Xf)
# brow ridge lift
wb = fbump(4200, 540, 130, 70)
face['brow'] = (0.8 * wb, -5 * wb, 0.25 + 0 * Xf)
# cheek / face plates: small staggered twitches
for i, (cx, cy, rx, ry, ax, ay, ph) in enumerate([
        (4040, 950, 45, 110, -2.5, 1.5, 0.10),
        (4250, 1040, 60, 70, 1.5, 2.5, 0.45),
        (4330, 800, 60, 120, 2.5, -1.5, 0.70),
        (4470, 880, 70, 110, -2.0, 2.0, 0.30)]):
    w = fbump(cx, cy, rx, ry)
    face[f'plate{i + 1}'] = (ax * w, ay * w, ph + 0 * Xf)
# ring eye dilation
ex, ey, er = 4152, 822, 18
we = np.exp(-(((Xf - ex) ** 2 + (Yf - ey) ** 2) / er ** 2))
face['ring_eye'] = ((Xf - ex) / er * 4 * we, (Yf - ey) / er * 4 * we, 0.55 + 0 * Xf)
# forehead dots: radial ripple running down the column
DOTS = [(4187, 667), (4188, 691), (4189, 716), (4190, 744)]
for i, (cx, cy) in enumerate(DOTS):
    w = np.exp(-(((Xf - cx) ** 2 + (Yf - cy) ** 2) / 14 ** 2))
    face[f'dot{i + 1}'] = ((Xf - cx) / 14 * 3 * w, (Yf - cy) / 14 * 3 * w, 0.12 * i + 0 * Xf)

rep_face = {}
lim = []
for name, (dx, dy, ph) in face.items():
    bx, by, bp, sg, st = limit(dx, dy, ph, SXF, SYF, 0.2)
    lim.append((bx, by, bp))
    rep_face[name] = {'max_px': round(float(np.hypot(bx, by).max()), 1),
                      'smooth_sigma_px': round(sg * SXF, 1), 'strain': round(st, 2)}
fdx, fdy, fph = combine(lim)
fdx, fdy, fph, sg, st = limit(fdx, fdy, fph, SXF, SYF, 0.24)
fph = np.clip(fph, 0, 0.995)
s_face, fqx, fqy = encode_flow('rig4_face_flow', fdx, fdy)
write_tex('rig4_face_time', fph * 255, 9)
report['face'] = {'flow': 'masks/rig4_face_flow', 'time': 'masks/rig4_face_time', 'speed': 1.6,
                  'strength': s_face, 'strain': round(st, 2), 'smooth_sigma_px': round(sg * SXF, 1),
                  'parts': rep_face, 'max_px': round(float(np.hypot(fdx, fdy).max()), 1)}

# ================================================================ blink masks (opacity, mask grid)
gym, gxm = np.mgrid[0:MH, 0:MW]
Xm, Ym = (gxm + 0.5) * SXM, (gym + 0.5) * SYM
blinks = []
for i, (cx, cy, r) in enumerate([(x, y, 15) for x, y in DOTS] + [(ex, ey, 17)]):
    d = np.hypot(Xm - cx, Ym - cy)
    m = smooth((r + 6 - d) / 8)
    name = f'rig4_blink_{i + 1}'
    write_tex(name, m * 255, 9)
    blinks.append({'mask': f'masks/{name}', 'phase': round(0.9 * i, 3)})
report['blinks'] = {'speed': 1.6, 'bounds': '0 0.15', 'items': blinks}

# ================================================================ combined check over time
def load_flow(png, strength):
    a = np.asarray(Image.open(png).convert('RGB').resize((MW, MH), Image.BILINEAR)).astype(np.float32)
    s2 = strength ** 2
    return (a[..., 0] / 255 - 0.498) * 2 * s2 * TW, (a[..., 1] / 255 - 0.498) * 2 * s2 * TH


def load_time(png):
    return np.asarray(Image.open(png).convert('L').resize((MW, MH), Image.BILINEAR)).astype(np.float32) / 255


rsz = lambda a: np.asarray(Image.fromarray(a.astype(np.float32), 'F').resize((MW, MH), Image.BILINEAR))
V2, V3 = os.path.join(HERE, 'rig', 'v2'), os.path.join(HERE, 'rig', 'v3')
passes = [
    ('hair', *load_flow(os.path.join(V3, 'rig3_appendages_flow.png'), 0.098), load_time(os.path.join(V3, 'rig3_appendages_time.png')), 1.3),
    ('tail', *load_flow(os.path.join(V2, 'rig2_tail_flow.png'), 0.074), load_time(os.path.join(V2, 'rig2_tail_time.png')), 1.04),
    ('body', body_final[0], body_final[1], body_final[2], 0.9),
    ('face', rsz(fqx), rsz(fqy), rsz(fph), 1.6),
    ('balance', *load_flow(os.path.join(V2, 'fix_shake_mask_647b9b30.png'), 0.036), np.zeros((MH, MW), np.float32), 3.18),
]
rng = np.random.default_rng(1)
times = np.concatenate([np.linspace(0, 40, 160), rng.uniform(0, 4000, 160)])
worst = np.zeros((MH, MW), np.float32)
g = lambda a, ax, s: np.gradient(a, axis=ax) / s
for t in times:
    dx = sum(p[1] * np.sin(p[4] * t + p[3] * 2 * math.pi) for p in passes)
    dy = sum(p[2] * np.sin(p[4] * t + p[3] * 2 * math.pi) for p in passes)
    j = np.sqrt(g(dx, 1, SXM) ** 2 + g(dx, 0, SYM) ** 2 + g(dy, 1, SXM) ** 2 + g(dy, 0, SYM) ** 2)
    np.maximum(worst, j, out=worst)
regions = {'face': (3990, 4450, 450, 1450), 'chest_corner': (4700, 5040, 600, 2160),
           'hair': (4080, 5040, 0, 600), 'tail': (3600, 3950, 300, 2160), 'all': (0, TW, 0, TH)}
report['combined_strain'] = {}
for name, (x0, x1, y0, y1) in regions.items():
    sel = (Xm >= x0) & (Xm < x1) & (Ym >= y0) & (Ym < y1)
    report['combined_strain'][name] = round(float(worst[sel].max()), 3)
Image.fromarray(np.clip(worst / 0.5 * 255, 0, 255).astype(np.uint8)).save(os.path.join(OUT_PNG, 'combined_strain.png'))

json.dump(report, open(REPORT, 'w'), indent=1)
print(json.dumps(report, indent=1))
