"""Mouse-follow field for the tail: a sideways bend that grows from the base of the tail spike to its
tip, strain-limited (same rule as tools/rig2.py).

  * w(y): 0 below a bend start height y0, rising to 1 at the tip (y0 and profile searched: the
    barbs at y~1140 sit ~100 px from the head, so a bend that starts above them reaches much further)
  * m(x, y): the tail's territory = points closer to the tail than to the rest of the silhouette
    (background around the tail included, so tips carry their surroundings), blurred so the
    fall-off sits in the gap toward the head
  * displacement = (A * w * m, 0) in texture px; A is the largest value whose worst strain stays
    <= TARGET. The shader mixes it with the idle sway as sway*(1-|f|) + f*follow, so the combined
    strain is <= max(sway 0.284, TARGET).

Writes materials/masks/tail_follow_flow.tex (RG88, format 8, like the rig maps), rig/v5/*.png,
and prints the strength to put in the effect (flow = disp / (strength^2 * size)).
Usage: python tools/tail_follow_field.py [--target 0.25]
"""
import argparse
import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
PROJ = Path(r"D:\steam\steamapps\common\wallpaper_engine\projects\myprojects\reptilian_ultrawide_5120")
TW, TH = 5040, 2160
MW, MH = 1720, 720                       # same grid as the rig maps
F = 4
GW, GH = TW // F, TH // F
BASE_Y, TIP_Y = 1870, 230
POWER = 1.6


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


def write_rg(path, pixels):
    h, w = pixels.shape[:2]
    raw = np.clip(np.round(pixels), 0, 255).astype(np.uint8).tobytes()
    comp = lz4_literals(raw)
    hdr = b'TEXV0005\0TEXI0001\0' + struct.pack('<6i', 8, 2, w, h, w, h) + bytes((0x7f, 0x7f, 0x00, 0xff))
    hdr += b'TEXB0003\0' + struct.pack('<5i', 1, -1, 1, w, h) + struct.pack('<3i', 1, len(raw), len(comp))
    path.write_bytes(hdr + comp)


def strain(dx, dy, sx, sy):
    g = lambda a, ax, s: np.gradient(a, axis=ax) / s
    return np.sqrt(g(dx, 1, sx) ** 2 + g(dx, 0, sy) ** 2 + g(dy, 1, sx) ** 2 + g(dy, 0, sy) ** 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=0.25)
    a = ap.parse_args()

    al = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA"))[..., 3]
    wa = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA"))[..., 3]
    s = np.maximum(al, wa)
    s = np.asarray(Image.fromarray(s).resize((GW, GH), Image.BOX)) > 64
    sil = ndi.binary_fill_holes(ndi.binary_closing(s, iterations=2))
    gy, gx = np.mgrid[0:GH, 0:GW]
    X, Y = (gx + 0.5) * F, (gy + 0.5) * F
    tail = sil & ((X < 3950) | ((Y > 1870) & (X < 4560)))          # rig2.py's tail region
    spike = tail & (Y < BASE_Y)
    rest = sil & ~tail
    d_spike = ndi.distance_transform_edt(~spike) * F
    d_rest = ndi.distance_transform_edt(~rest) * F
    terr = (d_spike < d_rest).astype(np.float32)

    best = None
    for y0, power, sigma in [(y0, pw, sg) for y0 in (1870, 1500, 1300, 1150, 1000) for pw in (1.0, 1.6, 2.2)
                             for sg in (40, 55, 70, 90, 120)]:
        t = np.clip((y0 - Y) / (y0 - TIP_Y), 0, 1)
        w = t * t * (3 - 2 * t) if power == 1.0 else t ** power
        m = ndi.gaussian_filter(terr, sigma / F * 1.0)
        m = np.where(rest, 0.0, m)                                   # the head/body never moves
        m = ndi.gaussian_filter(m, 3)
        m = np.where(rest, 0.0, m)
        shape = w * m
        st = strain(shape, np.zeros_like(shape), F, F).max()        # strain per px of A
        A = a.target / st
        tipdisp = (A * shape)[spike].max()
        if best is None or tipdisp > best[0]:
            best = (tipdisp, sigma, A, shape, y0, power)
            print(f"y0 {y0} power {power} sigma {sigma:3d}px: A {A:6.1f}  tip displacement {tipdisp:6.1f} px")
    tipdisp, sigma, A, shape, y0, power = best
    print(f"bend starts at y {y0}, profile {'smoothstep' if power == 1.0 else f't^{power}'}")
    dx = A * shape
    # verify on the full-res mask grid that the art itself barely moves outside the tail
    print(f"chosen sigma {sigma}px, A {A:.1f}, max tail displacement {tipdisp:.1f} px")
    rest_full = rest
    print("max displacement on non-tail silhouette:", float(dx[rest_full].max()))

    dxm = np.asarray(Image.fromarray(dx.astype(np.float32), "F").resize((MW, MH), Image.BILINEAR))
    st_m = strain(dxm, np.zeros_like(dxm), TW / MW, TH / MH).max()
    amp2 = np.abs(dxm).max() / TW * 1.02
    strength = math.ceil(math.sqrt(amp2) * 1000) / 1000
    fx = np.clip(dxm / (strength ** 2 * TW), -1, 1)
    pix = np.dstack([(0.498 + fx / 2) * 255, np.full_like(fx, 0.498 * 255)])
    write_rg(PROJ / "materials" / "masks" / "tail_follow_flow.tex", pix)
    out = HERE / "rig" / "v5"; out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(np.round(np.dstack([pix, np.zeros(fx.shape)])), 0, 255).astype(np.uint8)).save(out / "tail_follow_flow.png")
    vis = (np.clip(dxm / max(dxm.max(), 1e-6), 0, 1) * 255).astype(np.uint8)
    Image.fromarray(vis).save(out / "tail_follow_magnitude.png")
    print(f"mask-grid strain {st_m:.3f}; strength {strength}  (flow = disp / (strength^2 * {TW}))")


if __name__ == "__main__":
    main()
