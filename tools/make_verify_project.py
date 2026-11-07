"""Temporary A/B project: the original creature (every layer with its original effect chain, full
textures) and the optimized one, rendered side by side in the same frame, so the same g_Time,
audio and inputs drive both. Compare a screen capture of the two halves.

  * new layers stay where they are; REF_* copies of the original layers sit OFFSET px to the left
  * background and mandala hidden, layout script off (both groups at authored scale 1)
  * tail follow forced to 0 on both (the original script reads layer K, which moved when cropped)

Writes projects/myprojects/reptilian_verify (delete it afterwards).
--grid writes projects/myprojects/reptilian_verify_grid instead: the colour layers in isolation,
old and new side by side at half scale (row 1: C old, C new, M old, M new; row 2: the five CB
bands old, new, C2 old, new), everything else hidden.
Usage: python tools/make_verify_project.py [--grid]
"""
import copy
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ  # noqa: E402

SRC = HERE / "backups" / "2026-11-07_before_optimize" / "project"
GRID = "--grid" in sys.argv
_suffix = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--suffix=")), "")
OUT = PROJ.parent / (("reptilian_verify_grid" if GRID else "reptilian_verify") + _suffix)
GRID_SLOTS = {"C": 0, "M": 2, "CB_Chest": 4, "CB_Tail4": 4, "CB_Tail3": 4, "CB_Tail2": 4, "CB_Tail1": 4, "C2": 6}
CREATURE_CX = 4100          # creature centre x in full-layer px
CREATURE = ["Shadow", "W", "C", "M", "CB_Chest", "CB_Tail4", "CB_Tail3", "CB_Tail2", "CB_Tail1", "C2", "K"]
OFFSET = 2000


def no_follow(o):
    for e in o.get("effects", []):
        for p in e.get("passes", []):
            cv = p.get("constantshadervalues") or {}
            if "follow" in cv:
                cv["follow"] = 0.0


def main():
    if OUT.exists():
        shutil.rmtree(OUT, ignore_errors=True)      # WE keeps handles on folders it has scanned
    shutil.copytree(PROJ, OUT, dirs_exist_ok=True)
    for d in ("effects", "shaders", "materials/effects", "materials/masks", "materials/workshop"):
        if (SRC / d).exists():
            shutil.copytree(SRC / d, OUT / d, dirs_exist_ok=True)
    proj = json.loads((OUT / "project.json").read_text(encoding="utf-8"))
    proj["title"] = ("Reptilian VERIFY GRID" if GRID else "Reptilian VERIFY") + (" " + _suffix.strip("_") if _suffix else "") + " (temporary)"
    proj.pop("workshopid", None)
    (OUT / "project.json").write_text(json.dumps(proj, indent="\t", ensure_ascii=False), encoding="utf-8")

    scene = json.loads((OUT / "scene.json").read_text(encoding="utf-8"))
    old = {o["name"]: o for o in json.loads((SRC / "scene.json").read_text(encoding="utf-8"))["objects"]}
    ids = []

    def walk(x, fn=None):
        if isinstance(x, dict):
            if isinstance(x.get("id"), int):
                if fn:
                    x["id"] = fn()
                else:
                    ids.append(x["id"])
            for v in x.values():
                walk(v, fn)
        elif isinstance(x, list):
            for v in x:
                walk(v, fn)
    walk(scene)
    nxt = [max(ids) + 1]

    def nid():
        nxt[0] += 1
        return nxt[0] - 1

    objs = scene["objects"]
    for o in objs:
        if o["name"] in ("BG", "MandalaK"):
            o["visible"] = False
        if o["name"] == "K":
            o["visible"] = True
        if o["name"] in CREATURE:
            no_follow(o)
    refs = []
    for name in CREATURE:
        r = copy.deepcopy(old[name])
        r["name"] = "REF_" + name
        model = json.loads((SRC / r["image"]).read_text(encoding="utf-8"))
        mat = json.loads((SRC / model["material"]).read_text(encoding="utf-8"))
        tex = mat["passes"][0]["textures"][0]
        shutil.copy(SRC / "materials" / f"{tex}.tex", OUT / "materials" / f"ref_{tex}.tex")
        shutil.copy(SRC / "materials" / f"{tex}.tex-json", OUT / "materials" / f"ref_{tex}.tex-json")
        mat["passes"][0]["textures"][0] = f"ref_{tex}"
        (OUT / "materials" / f"ref_{tex}.json").write_text(json.dumps(mat, indent="\t", ensure_ascii=False), encoding="utf-8")
        model["material"] = f"materials/ref_{tex}.json"
        (OUT / "models" / f"ref_{tex}.json").write_text(json.dumps(model, indent="\t", ensure_ascii=False), encoding="utf-8")
        r["image"] = f"models/ref_{tex}.json"
        x, y, z = (float(v) for v in r["origin"].split())
        r["origin"] = f"{x - OFFSET:.5f} {y:.5f} {z:.5f}"
        if isinstance(r.get("visible"), dict):
            r["visible"] = True
        no_follow(r)
        walk(r, nid)
        refs.append(r)
    first = min(i for i, o in enumerate(objs) if o["name"] in CREATURE)
    objs[first:first] = refs
    if GRID:
        def place(o, slot, tcx, tcy):
            col, row = slot % 4, slot // 4
            sx, sy = 640 + 1280 * col, 1620 - 1080 * row
            sc0 = float(o["scale"].split()[0]) if o.get("scale") else 1.0
            sc = 0.5 * sc0
            o["scale"] = f"{sc:.5f} {sc:.5f} 1.00000"
            z = o["origin"].split()[2]
            o["origin"] = f"{sx - (CREATURE_CX - tcx) * sc:.5f} {sy - (tcy - 1080) * sc:.5f} {z}"
        for o in objs:
            base = o["name"][4:] if o["name"].startswith("REF_") else o["name"]
            if base not in GRID_SLOTS:
                o["visible"] = False
                continue
            if o["name"].startswith("REF_"):
                place(o, GRID_SLOTS[base], 2520, 1080)
            else:
                warp = next(e for e in o["effects"] if "uvrect" in (e.get("passes") or [{}])[0].get("constantshadervalues", {}))
                r = [float(v) for v in warp["passes"][0]["constantshadervalues"]["uvrect"].split()]
                tcx = (r[0] + r[2] / 2) * 5040
                tcy = (r[1] + r[3] / 2) * 2160
                place(o, GRID_SLOTS[base] + 1, tcx, tcy)
    (OUT / "scene.json").write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("wrote", OUT, "layers:", [o["name"] for o in objs])


if __name__ == "__main__":
    main()
