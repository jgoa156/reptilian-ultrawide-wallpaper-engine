"""CPU port of scripts/shader/mandala_spectrum.frag, to preview frames without Wallpaper Engine.

Writes a contact sheet: silence (breath peak and trough, full mandala), half-way into music,
music (13 pieces by band), glitch + datamosh, plus the reptile with its drop shadow.
Usage: python tools/mandala_preview.py <out.png> [width=1280]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
M = np.asarray(Image.open(HERE / "Choronzon_mandala_black.png").reduce(2))[..., 3].astype(np.float32) / 255
UNIT = np.array([5120 / 1500, 2160 / 1500])


def hash11(x):
    return np.mod(np.sin(x * 12.9898 + 78.233) * 43758.5453, 1.0)


def bilinear(img, u, v, wrap=False):
    h, w = img.shape
    x, y = u * w - 0.5, v * h - 0.5
    if wrap:
        return ndi.map_coordinates(img, [y, x], order=1, mode="grid-wrap")
    return ndi.map_coordinates(img, [y, x], order=1, mode="nearest")


def ink(px, py):
    inside = np.hypot(px, py) < 0.999
    return bilinear(M, px * 0.5 + 0.5, py * 0.5 + 0.5) * inside


def render(U, V, P):
    angle = P["time"] * 2 * np.pi / P["turnperiod"]
    px, py = (U - 0.5) * UNIT[0], (V - 0.5) * UNIT[1]
    if P["glitchslices"] > 0:
        shift = np.zeros_like(px)
        for i in range(int(P["glitchslices"])):
            h = P["glitchseed"] * 3.17 + i * 5.71
            hh = (2 + hash11(h + 2) * 16) / 240
            y0 = -0.8 + 1.6 * hash11(h + 1) - hh * 0.5
            mag = (8 + np.floor(hash11(h + 4) * 23)) / 30
            sgn = -1 if hash11(h + 3) < 0.5 else 1
            shift = np.where((py >= y0) & (py < y0 + hh), sgn * mag * P["glitchshift"], shift)
        px = px - shift
    c, s = np.cos(angle), np.sin(angle)
    qx, qy = px * c - py * s, px * s + py * c
    phi = np.arctan2(qx, -qy)
    w = 2 * np.pi / 13
    k = np.floor(phi / w + 0.5)
    d = phi - k * w
    k = np.mod(k + 13, 13).astype(int)
    lv = P["levels"][k]
    e0, e1 = 0.5 * w, 0.5 * w * (1 - P["feather"])
    t_ = np.clip((np.abs(d) - e0) / (e1 - e0), 0, 1)
    side = t_ * t_ * (3 - 2 * t_)
    side = 1 + (side - 1) * P["slice"]                  # idle: the full mandala
    sc = (1 + P["bulge"] * lv) * (1 + P["bassscale"] * P["bass"])
    a = ink(qx / sc, qy / sc) * side * (P["minop"] + (P["maxop"] - P["minop"]) * (P["floor"] + (1 - P["floor"]) * lv)) / 100
    return a


def mosh(U, V, P):
    gx, gy = P["moshgrid"]
    cx, cy = np.floor(U * gx), np.floor(V * gy)
    ix, iy = U * gx - cx, V * gy - cy
    idx = cy * gx + cx
    total = gx * gy
    shift = np.zeros_like(U)
    gain = np.ones_like(U)
    garbage = np.zeros_like(U)
    for i in range(int(P["mosherrors"])):
        h = P["moshseed"] * 7.31 + i * 13.17
        pos = np.floor(hash11(h) * total * 0.85)
        after = idx >= pos
        shift += after * (np.floor(hash11(h + 1) * 5) - 2)
        gain *= np.where(after, 0.9 + hash11(h + 2) * 0.3, 1)
        hit = after & (idx < pos + 2 + np.floor(hash11(h + 3) * 4))
        garbage = np.where(hit, (hash11(idx * 0.618 + h) >= 0.45).astype(float), garbage)
    s = np.maximum(idx - shift, 0)
    u2 = (np.mod(s, gx) + ix) / gx
    v2 = (np.floor(s / gx) + iy) / gy
    return u2, v2, gain, garbage


def frame(P, W):
    H = int(W * 2160 / 5120)
    V, U = (np.mgrid[0:H, 0:W] + 0.5) / np.array([H, W])[:, None, None]
    a = render(U, V, P)
    if P["mosh"] > 0:
        u2, v2, g, gb = mosh(U, V, P)
        am = np.maximum(np.clip(render(u2, v2, P) * g, 0, 1), gb * 0.3 * P["maxop"] / 100)
        a = a + (am - a) * P["mosh"]
    return np.clip(a, 0, 1)


def main():
    out, W = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1280
    rng = np.random.default_rng(3)
    base = dict(time=200.0, turnperiod=39.0, feather=0.35, floor=0.6, bulge=0.1, bassscale=0.04, bass=0.0,
                levels=np.zeros(13), glitchslices=0, glitchseed=0, glitchshift=0.1, mosh=0, moshseed=0,
                mosherrors=3, moshgrid=(160, 68), slice=0.0, minop=0.0, maxop=15.0)
    music = dict(base, floor=0.15, slice=1.0, bass=0.8, levels=np.clip(rng.random(13) ** 1.5 * 1.1, 0, 1))
    music["levels"][0] = 1.0
    half = dict(music, slice=0.5, floor=0.7 + (0.15 - 0.7) * 0.5)
    cases = [
        ("silence, breath peak (full mandala)", dict(base, floor=1.0)),
        ("silence, breath trough", dict(base, floor=0.4)),
        ("half-way into music (slice 0.5)", half),
        ("music: 13 pieces by band", music),
        ("beat: Leonard slices + datamosh", dict(music, glitchslices=6, glitchseed=417, glitchshift=0.022,
                                                  mosh=0.3, moshseed=133, mosherrors=4)),
    ]
    bg = np.array([168, 150, 190], np.float32)          # stand-in for the kaleidoscope
    tiles = []
    for label, P in cases:
        a = frame(P, W)[..., None]
        img = Image.fromarray((bg * (1 - a)).astype(np.uint8))
        ImageDraw.Draw(img).text((10, 8), label, fill=(255, 255, 255))
        tiles.append(img)
    # creature + shadow
    sh = Image.open(HERE / "shadow" / "Shadow.png")
    wf = Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png")
    kf = Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png")
    canvas = Image.new("RGBA", sh.size, (150, 140, 170, 255))
    for layer in (sh, wf, kf):
        canvas.alpha_composite(layer)
    H = tiles[0].height
    tiles.append(canvas.convert("RGB").crop((3500, 250, 4700, 808)).resize((W, H)))
    ImageDraw.Draw(tiles[-1]).text((10, 8), "drop shadow (outside only)", fill=(255, 255, 255))
    sheet = Image.new("RGB", (W * 2, H * ((len(tiles) + 1) // 2)), (0, 0, 0))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % 2) * W, (i // 2) * H))
    sheet.save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
