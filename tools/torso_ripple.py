"""Muscle ripple direction field for the torso (shader op in opBelly, scripts/shader/creature_warp.frag.in).

The ripple slides the torso's stripes along their own direction in a slow travelling wave. The
stripe direction comes from K's line art: structure tensor of the ink (gradient of the blurred
alpha), smoothed heavily, as a doubled-angle vector (cos 2a, sin 2a) weighted by coherence. Texture
slots are all taken, so the field is fitted with a cubic polynomial in (x, y) over the belly rig's
moving zone and baked as 2 x 10 constants (RIP_C, RIP_S). The shader never takes the half angle
(a stripe has no sign: half the zone runs near vertical, where it would flip): it builds the
stripe tensor T = (I + [[c, s], [s, -c]]) / 2 and slides by T * g, g a fixed travel direction
(down-right, neck -> coil), so the wave rolls along the body and every stripe moves along itself.

Writes rig/v8/torso_ripple.json and rig/v8/torso_ripple_preview.png.
Usage: python tools/torso_ripple.py
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
from tex_io import read_tex  # noqa: E402

SRC = HERE / "backups" / "2026-11-07_before_optimize" / "project" / "materials" / "masks"
OUT = HERE / "rig" / "v8"
TW, TH = 5040, 2160
DS = 4                                   # analysis at 1/4 resolution
CX, CY, SC = 4700.0, 1620.0, 600.0       # polynomial centre and scale (px)


def monomials(x, y):
    u, v = (x - CX) / SC, (y - CY) / SC
    return np.stack([np.ones_like(u), u, v, u * u, u * v, v * v, u ** 3, u * u * v, u * v * v, v ** 3], -1)


def flow_magnitude():
    fl = read_tex(SRC / "rig5_belly_flow.tex").astype(np.float32)
    m = np.hypot(fl[..., 0] / 255 - 0.498, fl[..., 1] / 255 - 0.498) * 2
    return np.asarray(Image.fromarray(m).resize((TW // DS, TH // DS), Image.BILINEAR))


def main():
    k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png"))[..., 3]
    k = np.asarray(Image.fromarray(k).resize((TW // DS, TH // DS), Image.BILINEAR)).astype(np.float32) / 255
    k = ndi.gaussian_filter(k, 1.0)
    gx, gy = ndi.sobel(k, 1), ndi.sobel(k, 0)
    s = 90 / DS
    jxx, jyy, jxy = (ndi.gaussian_filter(a, s) for a in (gx * gx, gy * gy, gx * gy))
    # gradient orientation doubled: (jxx - jyy, 2 jxy); stripes run perpendicular -> negate
    c2, s2 = -(jxx - jyy), -2 * jxy
    tr = jxx + jyy + 1e-6
    coh = np.hypot(c2, s2) / tr
    m = flow_magnitude()
    mmax = float(np.percentile(m[m > 0.002], 99))
    w = np.clip(m / mmax, 0, 1) * coh
    yy, xx = np.mgrid[0:TH // DS, 0:TW // DS]
    X, Y = (xx + 0.5) * DS, (yy + 0.5) * DS
    sel = w > 0.05
    A = monomials(X[sel], Y[sel]) * w[sel, None]
    nrm = np.hypot(c2, s2)[sel] + 1e-9
    bc = np.linalg.lstsq(A, (c2[sel] / nrm) * w[sel], rcond=None)[0]
    bs = np.linalg.lstsq(A, (s2[sel] / nrm) * w[sel], rcond=None)[0]
    M = monomials(X, Y)
    fc, fs = M @ bc, M @ bs
    ang = 0.5 * np.degrees(np.arctan2(fs, fc))
    zone = m > 0.1 * mmax
    print(f"flow magnitude 99th pct {mmax:.4f}; fitted stripe angle in the zone: "
          f"p5 {np.percentile(ang[zone], 5):.0f}  p50 {np.percentile(ang[zone], 50):.0f}  p95 {np.percentile(ang[zone], 95):.0f} deg")
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump({"centre": [CX, CY], "scale": SC, "c": bc.tolist(), "s": bs.tolist(), "flow_max": mmax},
              open(OUT / "torso_ripple.json", "w"), indent=1)
    # preview: ink + fitted stripe directions
    x0, y0 = 3900, 900
    img = Image.fromarray(((1 - k[y0 // DS:, x0 // DS:]) * 200 + 40).astype(np.uint8)).convert("RGB").resize(((TW - x0) // 2, (TH - y0) // 2))
    d = ImageDraw.Draw(img)
    for py in range(y0 + 40, TH, 80):
        for px in range(x0 + 40, TW, 80):
            i, j = py // DS, px // DS
            if m[i, j] < 0.1 * mmax:
                continue
            a = np.radians(ang[i, j])
            L = 30 * min(1, m[i, j] / mmax) + 6
            cx, cy = (px - x0) / 2, (py - y0) / 2
            col = (255, 60, 60)
            d.line([(cx - L * np.cos(a), cy - L * np.sin(a)), (cx + L * np.cos(a), cy + L * np.sin(a))], fill=col, width=2)
    img.save(OUT / "torso_ripple_preview.png")


def consts():
    P = json.load(open(OUT / "torso_ripple.json"))
    def f(v):                            # always a float literal (GLSL has no int -> float promotion)
        t = f"{float(v):.7g}"
        return t if any(ch in t for ch in ".e") else t + ".0"
    c, s = P["c"], P["s"]
    return [f"#define RIP_CENTER vec2({f(P['centre'][0] / TW)}, {f(P['centre'][1] / TH)})",
            f"#define RIP_SCALE {f(P['scale'])}",
            f"#define RIP_FLOWMAX {f(P['flow_max'])}",
            f"#define RIP_C0 vec4({', '.join(f(v) for v in c[0:4])})",
            f"#define RIP_C1 vec3({', '.join(f(v) for v in c[4:7])})",
            f"#define RIP_C2 vec3({', '.join(f(v) for v in c[7:10])})",
            f"#define RIP_S0 vec4({', '.join(f(v) for v in s[0:4])})",
            f"#define RIP_S1 vec3({', '.join(f(v) for v in s[4:7])})",
            f"#define RIP_S2 vec3({', '.join(f(v) for v in s[7:10])})"]


if __name__ == "__main__":
    main()
