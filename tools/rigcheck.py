"""Combined worst-case strain of the rig shake passes over time.

Usage: python tools/rigcheck.py name=flow.png,time.png|-,strength,speed [...]
Prints the worst strain per region (face, chest_corner, hair, tail, all).
"""
import math, sys
import numpy as np
from PIL import Image
TW, TH, MW, MH = 5040, 2160, 1720, 720
SX, SY = TW / MW, TH / MH
passes = []
for arg in sys.argv[1:]:
    name, spec = arg.split('=')
    f, t, s, w = spec.split(',')
    a = np.asarray(Image.open(f).convert('RGB').resize((MW, MH), Image.BILINEAR)).astype(np.float32)
    s2 = float(s) ** 2
    ph = np.zeros((MH, MW), np.float32) if t == '-' else np.asarray(Image.open(t).convert('L').resize((MW, MH), Image.BILINEAR)).astype(np.float32) / 255
    passes.append(((a[..., 0] / 255 - 0.498) * 2 * s2 * TW, (a[..., 1] / 255 - 0.498) * 2 * s2 * TH, ph, float(w)))
rng = np.random.default_rng(1)
times = np.concatenate([np.linspace(0, 40, 160), rng.uniform(0, 4000, 160)])
worst = np.zeros((MH, MW), np.float32)
g = lambda a, ax, s: np.gradient(a, axis=ax) / s
for t in times:
    dx = sum(p[0] * np.sin(p[3] * t + p[2] * 2 * math.pi) for p in passes)
    dy = sum(p[1] * np.sin(p[3] * t + p[2] * 2 * math.pi) for p in passes)
    np.maximum(worst, np.sqrt(g(dx, 1, SX) ** 2 + g(dx, 0, SY) ** 2 + g(dy, 1, SX) ** 2 + g(dy, 0, SY) ** 2), out=worst)
gy, gx = np.mgrid[0:MH, 0:MW]; X, Y = (gx + 0.5) * SX, (gy + 0.5) * SY
for name, (x0, x1, y0, y1) in {'face': (3990, 4450, 450, 1450), 'chest_corner': (4700, 5040, 600, 2160),
                               'hair': (4080, 5040, 0, 600), 'tail': (3600, 3950, 300, 2160), 'all': (0, TW, 0, TH)}.items():
    sel = (X >= x0) & (X < x1) & (Y >= y0) & (Y < y1)
    i = np.argmax(np.where(sel, worst, -1))
    print(f'{name:13s} {worst[sel].max():.3f}  at ({X.flat[i]:.0f},{Y.flat[i]:.0f})')
