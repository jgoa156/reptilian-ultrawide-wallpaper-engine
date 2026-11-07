"""Which parts of the creature does no effect move? Paints the silhouette by peak displacement
(over all of K's motion effects) and marks still areas red.

Displacement estimates (texture px, peak over the cycle):
  shake / tail_follow: |flow| * strength^2 * texture size (rig maps; the follow field at |f| = 1)
  foliagesway, waterwaves, iris: mask > 0.05 counts as moving (amplitude not modelled)
  spin / twirl: a disc of radius size * texture width at the centre
Usage: python tools/motion_coverage.py [out.png]
"""
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
PROJ = Path(r"D:\steam\steamapps\common\wallpaper_engine\projects\myprojects\reptilian_ultrawide_5120")
TW, TH = 5040, 2160
F = 4
GW, GH = TW // F, TH // F


def load_mask(name):
    d = (PROJ / "materials" / f"{name}.tex").read_bytes()
    if b"\x89PNG" in d[:200]:
        i = d.index(b"\x89PNG")
        a = np.asarray(Image.open(io.BytesIO(d[i:])).convert("RGBA")).astype(np.float32) / 255
        return a
    fmt, _, w, h = struct.unpack("<4i", d[18:34])
    ch = {8: 2, 9: 1, 0: 4}[fmt]
    raw = np.frombuffer(d[-(w * h * ch):], np.uint8).reshape(h, w, ch).astype(np.float32) / 255
    return raw


def to_grid(a):
    return np.asarray(Image.fromarray(a.astype(np.float32), "F").resize((GW, GH), Image.BILINEAR))


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "reports" / "motion_coverage.png")
    scene = json.loads((PROJ / "scene.json").read_text(encoding="utf-8"))
    K = next(o for o in scene["objects"] if o["name"] == "K")
    gy, gx = np.mgrid[0:GH, 0:GW]
    U, V = (gx + 0.5) / GW, (gy + 0.5) / GH
    disp = np.zeros((GH, GW), np.float32)
    binary = np.zeros((GH, GW), bool)
    rows = []
    for e in K["effects"]:
        kind = e["file"].split("/")[-2]
        p = e["passes"][0]
        cv = p.get("constantshadervalues", {})
        tex = p.get("textures") or []
        name = e.get("name") or kind
        if kind in ("shake", "tail_follow"):
            fl = load_mask(tex[1])
            fx, fy = (fl[..., 0] - 0.498) * 2, (fl[..., 1] - 0.498) * 2
            s2 = float(cv["strength"]) ** 2
            m = to_grid(np.hypot(fx * s2 * TW, fy * s2 * TH))
            if kind == "tail_follow" and len(tex) > 3:
                ff = load_mask(tex[3])
                m = m + to_grid(np.abs((ff[..., 0] - 0.498) * 2) * float(cv["followstrength"]) ** 2 * TW)
            disp += m
            rows.append((name, f"peak {m.max():.0f} px"))
        elif kind in ("foliagesway", "waterwaves", "iris"):
            mk = load_mask(tex[1])
            mk = mk[..., 0] if mk.ndim == 3 else mk
            b = to_grid(mk) > 0.05
            binary |= b
            rows.append((name, f"mask area {b.mean() * 100:.1f}%"))
        elif kind in ("spin", "twirl"):
            cx, cy = (float(v) for v in cv["center"].split())
            r = float(cv["size"])
            ratio = float(cv.get("ratio", 1))
            b = ((U - cx) / r) ** 2 + ((V - cy) * TH / TW / (r * ratio)) ** 2 < 1
            binary |= b
            rows.append((name, f"disc r {r * TW:.0f} px"))
    for r in rows:
        print(f"  {r[0]:24s} {r[1]}")

    al = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA"))
    wa = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA"))[..., 3]
    s = np.asarray(Image.fromarray(np.maximum(al[..., 3], wa)).resize((GW, GH), Image.BOX)) > 64
    sil = ndi.binary_fill_holes(s)
    moving = (disp >= 1.5) | binary
    still = sil & ~moving
    print(f"silhouette still: {still.sum() / sil.sum() * 100:.1f}%")
    lab, n = ndi.label(still)
    sizes = ndi.sum(still, lab, range(1, n + 1))
    for i in np.argsort(-sizes)[:8]:
        ys, xs = np.nonzero(lab == i + 1)
        print(f"  still region {i + 1}: {sizes[i] * F * F / 1e3:.0f}k px, x {xs.min() * F}-{xs.max() * F}, y {ys.min() * F}-{ys.max() * F}")

    art = np.asarray(Image.fromarray(al).resize((GW, GH), Image.BOX)).astype(np.float32) / 255
    base = np.ones((GH, GW, 3), np.float32) * 0.9
    base = base * (1 - art[..., 3:4] * 0.55)
    heat = np.clip(disp / 30, 0, 1)
    col = np.where(sil[..., None], np.stack([0.15 + 0 * heat, 0.35 + 0.5 * heat, 0.3 + 0.6 * heat], -1), base)
    col = np.where(sil[..., None], col * 0.55 + base * 0.45, col)
    col[still] = col[still] * 0.35 + np.array([1.0, 0.1, 0.1]) * 0.65
    Image.fromarray((np.clip(col, 0, 1) * 255).astype(np.uint8)).save(out)
    print("saved", out)


if __name__ == "__main__":
    main()
