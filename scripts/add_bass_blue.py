"""Install the 5 bass-blue pieces (CB_Chest, CB_Tail1 tip .. CB_Tail4 base) into the live scene.

Regions come from the user's cut map (scripts/bass_regions.py), fading out toward every cut;
each piece pulses on its own part of the spectrum (BANDS). Look: a heavily blurred, faint
cyan glow (blur sigma 6 px, alpha 0.14) so the magenta still reads through.

Safe to re-run: existing CB_* objects are replaced, not duplicated. Re-run it after
any rig change so the layers pick up the right motion effects.

  * cuts full-frame 5040x2160 crops of recovered_original/C.png (cyan ink) with a soft
    alpha edge, so they share the art layers' UV space and every mask/flow map applies
  * writes materials/CB_*.tex (embedded PNG + mips, like C.tex), material + model json
  * inserts the layers between M and C2, placed like C2 (K's origin + (-5, +4), scale 1)
  * effects: a copy of C2's "(C2) Bass" pulse, then ONLY those of C2's motion effects
    that actually move pixels inside the crop (measured from each effect's mask or flow
    map, or its centre/size), in C2's order, then the lens. Fewer shader passes.

Usage: python scripts/add_bass_blue.py [--alpha 0.14] [--soften 6] [--grow 0] [--dry]
"""
import argparse
import copy
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ, write_tex  # noqa: E402

TW, TH = 5040, 2160
OUT = HERE / "bass_blue"


from bass_regions import regions  # noqa: E402  (user's cut map -> 5 soft masks)

# Each piece listens to its own part of the WHOLE song (WE's 16-band spectrum, 0 = lowest),
# so they light up at different moments: bass on the chest, then rising in pitch up the
# tail, highs on the tip. Higher bands carry less energy, so their audio bounds are lower.
#            name:       (band min, band max, audio bounds)
BANDS = {"CB_Chest": (0, 1, "0.25 1.2"),     # sub + bass (kick)
         "CB_Tail4": (2, 4, "0.18 1.0"),     # low mids (bass lines, toms)
         "CB_Tail3": (5, 7, "0.12 0.8"),     # mids (vocals, snare body)
         "CB_Tail2": (8, 10, "0.08 0.6"),    # high mids (guitars, presence)
         "CB_Tail1": (11, 15, "0.05 0.45")}  # highs (hats, cymbals, air)
ORDER = ["CB_Chest", "CB_Tail4", "CB_Tail3", "CB_Tail2", "CB_Tail1"]
RETIRED = ["CB_Tail"]                          # earlier single-tail layer; its files are removed


def decode_masks(tmp: Path):
    subprocess.run([sys.executable, "-I", str(HERE / "tools" / "untex.py"),
                    str(PROJ / "materials" / "masks"), str(tmp)], check=True,
                   stdout=subprocess.DEVNULL)


def effect_moves_region(e, region_small, maskdir: Path):
    """Largest pixel displacement (or 1 for 'affects') the effect can apply inside the region."""
    kind = e["file"].split("/")[-2]
    p = e["passes"][0]
    c = p.get("constantshadervalues", {})
    if "lens_distortion" in e["file"]:
        return math.inf
    MH, MW = region_small.shape
    texs = [t for t in (p.get("textures") or []) if t]
    if kind in ("spin", "twirl"):
        cu, cv = map(float, c["center"].split())
        r = float(c["size"]) * TH / max(float(c.get("ratio", 1)), 1e-3) * 1.2
        yy, xx = np.mgrid[0:MH, 0:MW]
        d = np.hypot((xx + 0.5) / MW * TW - cu * TW, (yy + 0.5) / MH * TH - cv * TH)
        return 1.0 if (region_small[d < r] > 0.05).any() else 0.0
    if not texs:
        return 1.0                                                  # unmasked: assume it does
    m = np.asarray(Image.open(maskdir / (texs[0].split("/")[-1] + ".png")).convert("RGB")
                   .resize((MW, MH), Image.BILINEAR)).astype(np.float32)
    inside = region_small > 0.05
    if kind == "shake":
        s2 = float(c["strength"]) ** 2
        fx = (m[..., 0] / 255 - 0.498) * 2 * s2 * TW
        fy = (m[..., 1] / 255 - 0.498) * 2 * s2 * TH
        return float(np.hypot(fx, fy)[inside].max(initial=0))
    return 1.0 if (m[..., 0] / 255)[inside].max(initial=0) > 0.05 else 0.0   # opacity mask


def main():
    ap = argparse.ArgumentParser()
    # Look matched to the face blue (measured on the user's screenshot): a thin, soft
    # fringe from the offset cyan copy, no thickened strokes, a little less opaque.
    ap.add_argument("--alpha", type=float, default=0.14)   # faint: the magenta must still read through
    ap.add_argument("--grow", type=float, default=0, help="stroke growth in px (0 = face look)")
    ap.add_argument("--soften", type=float, default=6, help="blur sigma in px (a glow, like the face shine)")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    cyan = np.asarray(Image.open(HERE / "recovered_original" / "C.png").convert("RGBA")).copy()
    al = cyan[..., 3].astype(np.float32)
    if a.grow > 0:
        r = int(round(a.grow))
        yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
        al = ndi.grey_dilation(al, footprint=(xx * xx + yy * yy) <= r * r)
    if a.soften > 0:
        al = ndi.gaussian_filter(al, a.soften)
    cyan[..., 3] = np.clip(al, 0, 255).astype(np.uint8)
    cyan[cyan[..., 3] > 0, :3] = (85, 195, 233)                     # C.png's ink colour
    regs = regions()
    regs = {n: regs[n] for n in ORDER}

    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    objs = scene["objects"]
    objs[:] = [o for o in objs if not o["name"].startswith("CB_")]
    by = {o["name"]: o for o in objs}
    c2 = by["C2"]

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

    report = {}
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        decode_masks(tmp)
        new = []
        for name, reg in regs.items():
            rgba = cyan.copy()
            rgba[..., 3] = np.round(rgba[..., 3] * reg).astype(np.uint8)
            png = OUT / f"{name}.png"
            Image.fromarray(rgba, "RGBA").save(png, optimize=True)
            small = np.asarray(Image.fromarray(reg, "F").resize((1720, 720), Image.BILINEAR))
            pulse = next(e for e in c2["effects"] if e.get("name") == "(C2) Bass")
            effects = [fresh(pulse)]
            lo, hi, bounds = BANDS[name]
            effects[0]["name"] = f"({name}) Audio bands {lo}-{hi}"
            csv = effects[0]["passes"][0]["constantshadervalues"]
            csv["frequencymin"], csv["frequencymax"], csv["audiobounds"] = lo, hi, bounds
            kept, dropped = [], []
            for e in c2["effects"]:
                if e is pulse:
                    continue
                amt = effect_moves_region(e, small, tmp)
                label = e.get("name") or e["file"].split("/")[-2]
                if amt >= 0.5:
                    effects.append(fresh(e))
                    kept.append(f"{label} ({'all' if amt == math.inf else round(amt, 1)})")
                else:
                    dropped.append(label)
            report[name] = {"kept": kept, "dropped": dropped,
                            "passes": sum(len(e["passes"]) for e in effects)}
            if a.dry:
                continue
            write_tex(PROJ / "materials" / f"{name}.tex", png)
            (PROJ / "materials" / f"{name}.tex-json").write_text(json.dumps(
                {"bleedtransparentcolors": True, "clampuvs": True,
                 "format": "rgba8888", "nonpoweroftwo": True}, indent="\t"))
            (PROJ / "materials" / f"{name}.json").write_text(json.dumps(
                {"passes": [{"blending": "translucent", "combos": {}, "cullmode": "nocull",
                             "depthtest": "disabled", "depthwrite": "disabled",
                             "shader": "genericimage4", "textures": [name]}]}, indent="\t"))
            (PROJ / "models" / f"{name}.json").write_text(json.dumps(
                {"autosize": True, "material": f"materials/{name}.json"}, indent="\t"))
            o = {k: copy.deepcopy(v) for k, v in c2.items() if k != "effects"}
            o.update(id=nid(), name=name, image=f"models/{name}.json", alpha=a.alpha,
                     effects=effects)
            new.append(o)

    print(json.dumps(report, indent=1, ensure_ascii=False))
    if a.dry:
        return
    i = objs.index(c2)
    objs[i:i] = new
    for name in RETIRED:
        for f in (PROJ / "materials" / f"{name}.tex", PROJ / "materials" / f"{name}.tex-json",
                  PROJ / "materials" / f"{name}.json", PROJ / "models" / f"{name}.json",
                  OUT / f"{name}.png"):
            f.unlink(missing_ok=True)
    # refresh the layout script so the new layers follow the 90%-height layout
    by["K"]["visible"]["script"] = (HERE / "scripts" / "reptilian_layout.js").read_text(encoding="utf-8")
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("layers:", [o["name"] for o in objs])


if __name__ == "__main__":
    main()
