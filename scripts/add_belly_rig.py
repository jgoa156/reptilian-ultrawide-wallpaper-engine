"""Rig: Belly, slow breathing for the zone nothing else moved (lower body / chest, ~12% of the
silhouette; see tools/motion_coverage.py). Safe to re-run.

Adds a built-in shake right after "Rig: Head & Body" on every layer that has one, so all the
colour copies stay in register. Field from tools/belly_field.py (run it first): radial swell
from the chest, ripple along the coil, ~9 px peak, strain 0.15.

Usage: python scripts/add_belly_rig.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ  # noqa: E402

NAME = "Rig: Belly"
STRENGTH = 0.067       # printed by tools/belly_field.py
SPEED = 0.75           # rad/s: one breath every ~8.4 s


def main():
    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
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

    done = []
    for o in scene["objects"]:
        fx = o.get("effects", [])
        fx[:] = [e for e in fx if e.get("name") != NAME]
        idx = [i for i, e in enumerate(fx) if e.get("name") == "Rig: Head & Body"]
        if not idx:
            continue
        fx.insert(idx[0] + 1, {
            "file": "effects/shake/effect.json", "id": nid(), "name": NAME,
            "passes": [{"id": nid(), "constantshadervalues": {
                "bounds": "0 1", "friction": "1 1", "speed": SPEED, "strength": STRENGTH},
                "textures": [None, "masks/rig5_belly_flow", "masks/rig5_belly_time"]}],
            "visible": True})
        done.append(o["name"])
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("Rig: Belly added to:", done)


if __name__ == "__main__":
    main()
