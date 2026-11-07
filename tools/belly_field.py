"""Rig: Belly, a motion field for the part of the creature nothing else moves (the lower body /
chest zone found by tools/motion_coverage.py: x 4270-5040, y 1040-2160).

  * mask: the still zone (peak displacement < 1.5 px over all of K's effects), dilated 60 px and
    blurred (sigma 70 px) so it fades over ~200 px into the neighbouring motion
  * direction: breathing, radially out from the chest centre C, linear inside R0 so the centre
    doesn't pinch
  * time offset: a ripple along the coil (phase grows with x - y), so it slithers instead of pumping
  * amplitude: the largest peak whose worst strain (phase gradient included, like rig2.py) is
    <= TARGET (0.15, headroom for the overlap with the other rigs)

Writes materials/masks/rig5_belly_flow.tex (RG88) + rig5_belly_time.tex (R8) and rig/v5/*.png,
prints the shake strength. Usage: python tools/belly_field.py [--target 0.15]
"""
import argparse
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "tools"))
import motion_coverage as mc  # noqa: E402
from tail_follow_field import lz4_literals  # noqa: E402

PROJ = mc.PROJ
TW, TH, F, GW, GH = mc.TW, mc.TH, mc.F, mc.GW, mc.GH
MW, MH = 1720, 720
CENTER = (4700.0, 1620.0)
R0 = 450.0
RIPPLE = 1.0 / 1400.0          # cycles per px along (x - y)


def write_tex(path, pixels, fmt):
    import struct
    h, w = pixels.shape[:2]
    raw = np.clip(np.round(pixels), 0, 255).astype(np.uint8).tobytes()
    comp = lz4_literals(raw)
    neutral = (0x7f, 0x7f, 0x00, 0xff) if fmt == 8 else (0, 0, 0, 0xff)
    hdr = b'TEXV0005\0TEXI0001\0' + struct.pack('<6i', fmt, 2, w, h, w, h) + bytes(neutral)
    hdr += b'TEXB0003\0' + struct.pack('<5i', 1, -1, 1, w, h) + struct.pack('<3i', 1, len(raw), len(comp))
    path.write_bytes(hdr + comp)


def still_zone():
    """Recompute motion_coverage's still mask WITHOUT any previous Rig: Belly."""
    import json
    scene = json.loads((PROJ / "scene.json").read_text(encoding="utf-8"))
    K = next(o for o in scene["objects"] if o["name"] == "K")
    disp = np.zeros((GH, GW), np.float32)
    binary = np.zeros((GH, GW), bool)
    gy, gx = np.mgrid[0:GH, 0:GW]
    U, V = (gx + 0.5) / GW, (gy + 0.5) / GH
    for e in K["effects"]:
        if e.get("name") == "Rig: Belly":
            continue
        kind = e["file"].split("/")[-2]
        p = e["passes"][0]; cv = p.get("constantshadervalues", {}); tex = p.get("textures") or []
        if kind in ("shake", "tail_follow"):
            fl = mc.load_mask(tex[1]); s2 = float(cv["strength"]) ** 2
            disp += mc.to_grid(np.hypot((fl[..., 0] - 0.498) * 2 * s2 * TW, (fl[..., 1] - 0.498) * 2 * s2 * TH))
        elif kind in ("foliagesway", "waterwaves", "iris"):
            mk = mc.load_mask(tex[1]); mk = mk[..., 0] if mk.ndim == 3 else mk
            binary |= mc.to_grid(mk) > 0.05
        elif kind in ("spin", "twirl"):
            cx, cy = (float(v) for v in cv["center"].split()); r = float(cv["size"]); ratio = float(cv.get("ratio", 1))
            binary |= ((U - cx) / r) ** 2 + ((V - cy) * TH / TW / (r * ratio)) ** 2 < 1
    al = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA"))[..., 3]
    wa = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA"))[..., 3]
    sil = ndi.binary_fill_holes(np.asarray(Image.fromarray(np.maximum(al, wa)).resize((GW, GH), Image.BOX)) > 64)
    return sil & ~((disp >= 1.5) | binary), sil


def strain(dx, dy, ph, sx, sy):
    g = lambda a, ax, s: np.gradient(a, axis=ax) / s
    jd = np.sqrt(g(dx, 1, sx) ** 2 + g(dx, 0, sy) ** 2 + g(dy, 1, sx) ** 2 + g(dy, 0, sy) ** 2)
    gp = np.hypot(g(ph, 1, sx), g(ph, 0, sy))
    return jd + np.hypot(dx, dy) * gp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=float, default=0.15)
    a = ap.parse_args()
    still, sil = still_zone()
    print(f"still zone: {still.sum() / sil.sum() * 100:.1f}% of the silhouette")
    m = ndi.binary_dilation(still, iterations=int(60 / F)).astype(np.float32)
    m = ndi.gaussian_filter(m, 70 / F)
    m = np.clip(m / 0.75, 0, 1)
    m = m * m * (3 - 2 * m)

    gy, gx = np.mgrid[0:GH, 0:GW]
    X, Y = (gx + 0.5) * F, (gy + 0.5) * F
    rx, ry = X - CENTER[0], Y - CENTER[1]
    r = np.hypot(rx, ry)
    k = 1.0 / np.maximum(r, R0)
    ux, uy = rx * k, ry * k                                   # |u| = r/R0 inside R0, 1 outside
    phase = np.mod((X - Y) * RIPPLE, 1.0)
    ph_rad = (X - Y) * RIPPLE * 2 * math.pi                   # unwrapped, for the strain check

    st1 = strain(m * ux, m * uy, ph_rad, F, F).max()          # strain per px of amplitude
    A = a.target / st1
    dx, dy = A * m * ux, A * m * uy
    print(f"peak displacement {np.hypot(dx, dy).max():.1f} px at strain {a.target}")

    rs = lambda z: np.asarray(Image.fromarray(z.astype(np.float32), "F").resize((MW, MH), Image.BILINEAR))
    dxm, dym, phm = rs(dx), rs(dy), rs(phase)
    amp2 = max(np.abs(dxm).max() / TW, np.abs(dym).max() / TH) * 1.02
    strength = math.ceil(math.sqrt(amp2) * 1000) / 1000
    fx = np.clip(dxm / (strength ** 2 * TW), -1, 1)
    fy = np.clip(dym / (strength ** 2 * TH), -1, 1)
    flow = np.dstack([(0.498 + fx / 2) * 255, (0.498 + fy / 2) * 255])
    write_tex(PROJ / "materials" / "masks" / "rig5_belly_flow.tex", flow, 8)
    write_tex(PROJ / "materials" / "masks" / "rig5_belly_time.tex", (phm * 255)[..., None], 9)
    out = HERE / "rig" / "v5"; out.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.clip(np.round(np.dstack([flow, np.zeros(fx.shape)])), 0, 255).astype(np.uint8)).save(out / "rig5_belly_flow.png")
    Image.fromarray((phm * 255).astype(np.uint8)).save(out / "rig5_belly_time.png")
    Image.fromarray((np.clip(np.hypot(dx, dy) / max(np.hypot(dx, dy).max(), 1e-6), 0, 1) * 255).astype(np.uint8)).save(out / "rig5_belly_magnitude.png")
    print(f"strength {strength}")


if __name__ == "__main__":
    main()
