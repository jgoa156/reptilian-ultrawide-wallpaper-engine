"""Outer drop shadow for the reptile. Safe to re-run (replaces the Shadow layer).

  * silhouette = W (white body fill) + K (line art); holes (the teeth gaps) left open
  * shadow = a tight contact shadow plus a wide soft one, both cast toward the creature's open
    side (texture left = away from the cropped right edge; with WE's flip option it is mirrored
    along with the art) and slightly down. It is clipped to the OUTSIDE of the silhouette, so
    it never darkens the body itself.
  * the layer sits right under W, in the same full-frame UV space, with copies of W's motion
    effects (the rig shakes + lens), so it moves with the creature. The rig flow maps reach
    40-60 px past the outline at full strength (measured), which covers the shadow.

Usage: python scripts/add_shadow.py [--alpha 0.7] [--dx -22] [--dy 18] [--dry]
"""
import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ, write_image  # noqa: E402

CLIP = "lens_fold_clip"
SHADER_SRC = HERE / "scripts" / "shader"


def install_clip_effect():
    """Custom effect that clips the lens distortion's folded far zone (see the .frag header)."""
    (PROJ / "shaders" / "effects" / f"{CLIP}.vert").write_text(
        (SHADER_SRC / f"{CLIP}.vert.in").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (PROJ / "shaders" / "effects" / f"{CLIP}.frag").write_text(
        (SHADER_SRC / f"{CLIP}.frag").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (PROJ / "materials" / "effects" / f"{CLIP}.json").write_text(json.dumps(
        {"passes": [{"shader": f"effects/{CLIP}", "blending": "normal", "depthtest": "disabled",
                     "depthwrite": "disabled", "cullmode": "nocull"}]}, indent="	"))
    d = PROJ / "effects" / CLIP
    d.mkdir(exist_ok=True)
    (d / "effect.json").write_text(json.dumps({
        "version": 1, "replacementkey": CLIP, "name": "Lens fold clip",
        "description": "Clips the folded far zone of the lens distortion (shadow artifact fix)",
        "group": "localeffects",
        "passes": [{"material": f"materials/effects/{CLIP}.json"}],
        "dependencies": [f"materials/effects/{CLIP}.json",
                         f"shaders/effects/{CLIP}.frag", f"shaders/effects/{CLIP}.vert"],
    }, indent="	"))

NAME = "Shadow"


def build(dx, dy, alpha):
    Wf = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png"))[..., 3]
    Kf = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png"))[..., 3]
    # holes are NOT filled: the creature's only enclosed holes are the 8 gaps between the teeth, where
    # the background shows through; filled, they got no shadow and read as bright white slots
    # (user, 2026-11-09). Now the upper jaw casts its shadow into them like onto any background.
    sil = np.maximum(Wf, Kf).astype(np.float32) / 255
    sil = np.maximum(sil, sil > 0.12)                 # antialiased edge pixels count as solid (as before)
    # the art is cropped at the bottom and right frame edges: 'nearest' keeps the shadow full there
    near = ndi.shift(sil, (dy * 0.45, dx * 0.45), order=1, mode="nearest")
    far = ndi.shift(sil, (dy, dx), order=1, mode="nearest")
    contact = np.clip(ndi.gaussian_filter(near, 7, mode="nearest") * 1.15, 0, 1) * 0.6
    soft = np.clip(ndi.gaussian_filter(far, 34, mode="nearest") * 1.1, 0, 1) * 0.45
    sh = 1 - (1 - contact) * (1 - soft)
    outside = 1 - np.clip(ndi.gaussian_filter(sil, 1.2), 0, 1)
    # fade to 0 at the top, left and right texture borders: the lens distortion samples past the
    # quad edge and smeared border shadow into the quad's corner (user-reported artifact)
    H, W = sil.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    def ramp(d, n):
        t = np.clip(d / n, 0, 1)
        return t * t * (3 - 2 * t)
    border = ramp(yy, 90) * ramp(xx, 90) * ramp(W - 1 - xx, 160)
    a = np.clip(sh * outside * alpha * border, 0, 1)
    rgba = np.zeros(sil.shape + (4,), np.uint8)
    rgba[..., 3] = np.round(a * 255).astype(np.uint8)
    return rgba


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--alpha", type=float, default=0.7)
    ap.add_argument("--dx", type=float, default=-22, help="texture px; negative = toward the open side")
    ap.add_argument("--dy", type=float, default=18, help="texture px; positive = down")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    rgba = build(a.dx, a.dy, a.alpha)
    out = HERE / "shadow"
    out.mkdir(exist_ok=True)
    png = out / f"{NAME}.png"
    Image.fromarray(rgba, "RGBA").save(png, optimize=True)
    al = rgba[..., 3]
    print("shadow px > 10%:", int((al > 25).sum()), " max alpha:", int(al.max()))
    if a.dry:
        return

    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    objs = scene["objects"]
    objs[:] = [o for o in objs if o["name"] != NAME]
    by = {o["name"]: o for o in objs}
    w = by["W"]
    ids = []

    def walk(x):
        if isinstance(x, dict):
            if isinstance(x.get("id"), int):
                ids.append(x["id"])
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(scene)
    nxt = [max(ids) + 1]

    def nid():
        nxt[0] += 1
        return nxt[0] - 1

    def fresh(e):
        e = copy.deepcopy(e)
        e["id"] = nid()
        for p in e["passes"]:
            p["id"] = nid()
        return e

    write_image(NAME, png)
    install_clip_effect()
    effects = [fresh(e) for e in w["effects"]]
    lens = next(e for e in effects if "lens_distortion" in e["file"])
    lc = lens["passes"][0]["constantshadervalues"]
    size = float(lc["size"]) * 4
    th, tw = rgba.shape[:2]
    effects.append({"file": f"effects/{CLIP}/effect.json", "id": nid(), "name": "Lens fold clip",
                    "passes": [{"id": nid(), "constantshadervalues": {
                        "center": lc["center"],
                        "scale": f"{th / tw * size:.5f} {size:.5f}",
                        "fold": "0.55 0.62"}}],
                    "visible": True})
    o = {k: copy.deepcopy(v) for k, v in w.items() if k != "effects"}
    o.update(id=nid(), name=NAME, image=f"models/{NAME}.json", alpha=1.0, effects=effects)
    objs.insert(objs.index(w), o)
    by["K"]["visible"]["script"] = (HERE / "scripts" / "reptilian_layout.js").read_text(encoding="utf-8")
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("layers:", [x["name"] for x in objs])


if __name__ == "__main__":
    main()
