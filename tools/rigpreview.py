"""Render a GIF of the rig shake passes (+ K's blink pulses) applied to the composite art.

Usage: python tools/rigpreview.py out.gif x0 y0 x1 y1 seconds frames
"""
import math, sys
import numpy as np
from PIL import Image
from scipy import ndimage
out, x0, y0, x1, y1, secs, nf = sys.argv[1], *map(int, sys.argv[2:6]), float(sys.argv[6]), int(sys.argv[7])
TW, TH = 5040, 2160
ro = 'recovered_original/'
def rgba(p): return np.asarray(Image.open(p).convert('RGBA')).astype(np.float32) / 255
K, C, M, W = rgba(ro + 'Sem título-1_Prancheta 1.png'), rgba(ro + 'C.png'), rgba(ro + 'M.png'), rgba(ro + 'sprite bgpng_Prancheta 1.png')
CB = [rgba('bass_blue/CB_Chest.png'), rgba('bass_blue/CB_Tail.png')]
def flow(f, t, s, w):
    a = np.asarray(Image.open(f).convert('RGB').resize((TW, TH), Image.BILINEAR)).astype(np.float32)[y0:y1, x0:x1]
    ph = np.zeros(a.shape[:2]) if t == '-' else np.asarray(Image.open(t).convert('L').resize((TW, TH), Image.BILINEAR)).astype(np.float32)[y0:y1, x0:x1] / 255
    return (a[..., 0] / 255 - .498) * 2 * s * s * TW, (a[..., 1] / 255 - .498) * 2 * s * s * TH, ph, w
V2, V3, V4 = 'rig/v2/', 'rig/v3/', 'rig/v4/'
P = [flow(V3 + 'rig3_appendages_flow.png', V3 + 'rig3_appendages_time.png', .098, 1.3),
     flow(V2 + 'rig2_tail_flow.png', V2 + 'rig2_tail_time.png', .074, 1.04),
     flow(V4 + 'rig4_body_flow.png', V4 + 'rig4_body_time.png', .082, .9),
     flow(V4 + 'rig4_face_flow.png', V4 + 'rig4_face_time.png', .051, 1.6)]
blinks = [np.asarray(Image.open(V4 + f'rig4_blink_{i}.png').convert('L').resize((TW, TH), Image.BILINEAR)).astype(np.float32)[y0:y1, x0:x1] / 255 for i in range(1, 6)]
gy, gx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
def comp(Ka):
    def ov(dst, src, a):
        al = src[..., 3:] * a; return dst * (1 - al) + src[..., :3] * al
    o = np.full((y1 - y0, x1 - x0, 3), 0.15, np.float32)
    o = ov(o, W[y0:y1, x0:x1], 1); o = ov(o, C[y0:y1, x0:x1], .36)
    o = ov(o, np.roll(M, -15, 1)[y0:y1, x0:x1], .66)
    for cb in CB: o = ov(o, cb[y0:y1, x0:x1], .9)
    o = ov(o, np.roll(np.roll(C, -5, 1), 4, 0)[y0:y1, x0:x1], .45)
    return ov(o, Ka, 1)
frames = []
for i in range(nf):
    t = secs * i / nf
    dx = sum(p[0] * np.sin(p[3] * t + p[2] * 6.283) for p in P); dy = sum(p[1] * np.sin(p[3] * t + p[2] * 6.283) for p in P)
    Kc = K[y0:y1, x0:x1].copy()
    for j, b in enumerate(blinks):
        s = np.sin(1.6 * t + 0.9 * j - math.pi / 2) * .5 + .5; pu = np.clip(s / .15, 0, 1); pu = pu * pu * (3 - 2 * pu)
        Kc[..., 3] *= 1 - b * (1 - pu)
    img = comp(Kc)
    sx, sy = gx + dx - x0, gy + dy - y0
    warped = np.dstack([ndimage.map_coordinates(img[..., c], [sy, sx], order=1, mode='nearest') for c in range(3)])
    frames.append(Image.fromarray((np.clip(warped, 0, 1) * 255).astype(np.uint8)).resize(((x1 - x0) // 2, (y1 - y0) // 2), Image.LANCZOS))
frames[0].save(out, save_all=True, append_images=frames[1:], duration=int(secs / nf * 1000), loop=0)
print('saved', out)
