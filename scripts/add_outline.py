"""Black outline around the creature. Safe to re-run (replaces the Outline layer).

  * silhouette = W (white body fill) + K (line art), holes filled (same as the Shadow)
  * stroke = everything within WIDTH px OUTSIDE the silhouette (anti-aliased), plus a 2 px overlap
    inward so no light seam shows at the edge. WIDTH 12 = the hair stroke (K's hair lines measure
    median 10, p75 15 px; K's own line along the silhouette edge is 12 px)
  * color = K's ink (#242423), so it reads as part of the line art
  * layer "Outline" sits above every colored layer (C, M, CB_*, C2) and right under K, with C2's
    whole motion stack minus C2's bass pulse, so it moves in register with the art
  * also adds "Outline" to the layout script's GROUP list

Then run scripts/add_fold_clip.py (adds the lens fold clip to every lensed layer, Outline too).
Usage: python scripts/add_outline.py [--width 12]
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

NAME = "Outline"
INK = (36, 36, 35)
LAYOUT = HERE / "scripts" / "reptilian_layout.js"


def build(width):
    Wf = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png"))[..., 3]
    Kf = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png"))[..., 3]
    sil = np.maximum(Wf, Kf) > 127
    sil = ndi.binary_fill_holes(sil)
    d_out = ndi.distance_transform_edt(~sil)             # distance outside the silhouette
    d_in = ndi.distance_transform_edt(sil)               # distance inside
    a = np.clip(width + 0.5 - d_out, 0, 1)              # outside stroke, AA at its outer edge
    a = np.where(sil, np.clip(2.5 - d_in, 0, 1), a)      # 2 px overlap inward
    rgba = np.zeros(sil.shape + (4,), np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = INK
    rgba[..., 3] = (a * 255).round().astype(np.uint8)
    out = HERE / "outline"
    out.mkdir(exist_ok=True)
    png = out / f"{NAME}.png"
    Image.fromarray(rgba).save(png, optimize=True)
    return png, rgba


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float, default=12)
    a = ap.parse_args()
    png, rgba = build(a.width)
    print("outline px > 50%:", int((rgba[..., 3] > 127).sum()), "size", rgba.shape[1], rgba.shape[0])

    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    objs = scene["objects"]
    objs[:] = [o for o in objs if o["name"] != NAME]
    by = {o["name"]: o for o in objs}
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
    c2 = by["C2"]
    effects = [fresh(e) for e in c2["effects"]
               if e.get("file") != "effects/pulse/effect.json" and e.get("name") != "Lens fold clip"]
    o = {k: copy.deepcopy(v) for k, v in c2.items() if k != "effects"}
    o.update(id=nid(), name=NAME, image=f"models/{NAME}.json", alpha=1.0, effects=effects)
    objs.insert(objs.index(by["K"]), o)
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")

    js = LAYOUT.read_text(encoding="utf-8")
    if "'Outline'" not in js:
        js = js.replace("'C2', 'K'];", "'C2', 'Outline', 'K'];")
        assert "'Outline'" in js
        js = js.replace("// Shadow: outer drop shadow", "// Outline: black stroke around the creature, under K (scripts/add_outline.py).\n// Shadow: outer drop shadow")
        LAYOUT.write_text(js, encoding="utf-8", newline="\n")
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    k = next(x for x in scene["objects"] if x["name"] == "K")
    k["visible"]["script"] = LAYOUT.read_text(encoding="utf-8")
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("layers:", [x["name"] for x in scene["objects"]])
    print("Outline effects:", [e.get("name") or Path(e["file"]).parts[-2] for e in effects])


if __name__ == "__main__":
    main()
