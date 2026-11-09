"""Living-creature extras that live outside the shader. Idempotent.

  * layer "MouthSmoke" (in front of K): a small black smoke puff out of the mouth on strong bass hits.
    WE particle system on WE's own smoke2 sprite sheet (the edge smoke's material); its
    instance-override rate is bound to scripts/mouth_smoke.js, which opens the emitter for 0.22 s
    whenever scripts/creature_driver.js flags a hard hit (shared.creaturePuff, the same hit that
    snaps the jaw). Visibility follows the user property `creaturemusic`.
  * the layout script (scripts/reptilian_layout.js, on layer K) gets MouthSmoke in its GROUP, so it
    moves and scales with the creature.
  * project.json: user property `creaturemusic` (music drives the jaw, heave, split, gills, hair),
    and the mandala's centre eye: `mandalaeye` (on/off) and `mandalaeyeopacity` (%), bound to the
    "Spectrum mandala" effect by optimize_creature.py (the eye itself: scripts/shader/mandala_spectrum.frag,
    its look and blink: scripts/mandala_controller.js).
The per-frame values themselves (scripts/creature_driver.js) and the shader side are installed by
scripts/optimize_creature.py.

Writes particles/mouth_smoke.json into the optimiser's source project and the live project, the
layer into the source scene.json, and the property into the live project.json. Then run scripts/optimize_creature.py.
Usage: python scripts/add_living_creature.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from we_paths import PROJ  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "backups" / "2026-11-07_before_optimize" / "project"
NAME = "MouthSmoke"
# full-layer px -> authored world: K's origin (2600, 1082) sits on the full layer's centre (2520, 1080)
MOUTH_PX = (4205, 1255)
MOUTH_WORLD = (MOUTH_PX[0] + 80, 2162 - MOUTH_PX[1])

PARTICLE = {
    "animationmode": "randomframe",
    "children": None,
    "controlpoint": [{"flags": 0, "id": i, "offset": "0 0 0"} for i in range(8)],
    "emitter": [{
        "directions": "1 1 0",
        "distancemax": "30 30 0",
        "distancemin": "0 0 0",
        "id": 7,
        "name": "boxrandom",
        "origin": "0 0 0",
        "rate": 36,
        "speedmax": 0,
        "speedmin": 0,
    }],
    "flags": 0,
    "initializer": [
        {"id": 2, "name": "lifetimerandom", "min": 1.3, "max": 2.2},
        {"id": 3, "name": "sizerandom", "min": 70, "max": 140},
        {"id": 4, "name": "colorrandom", "min": "0 0 0", "max": "10 10 12"},
        {"id": 5, "name": "alpharandom", "min": 0.22, "max": 0.38},
        {"id": 6, "name": "velocityrandom", "min": "-150 -60 0", "max": "-50 30 0"},
        {"id": 12, "name": "rotationrandom", "min": "0 0 0", "max": "0 0 6.2831"},
        {"id": 13, "name": "angularvelocityrandom", "min": "0 0 -0.8", "max": "0 0 0.8"},
    ],
    "material": "materials/edge_smoke.json",
    "maxcount": 48,
    "operator": [
        {"id": 8, "name": "movement", "drag": 1.4, "gravity": "0 40 0"},
        {"id": 14, "name": "angularmovement", "drag": 0, "force": "0 0 0"},
        {"id": 9, "name": "alphafade", "fadeintime": 0.06, "fadeouttime": 0.7},
        {"id": 10, "name": "sizechange", "starttime": 0, "endtime": 1, "startvalue": 0.4, "endvalue": 1.6},
        {"id": 11, "name": "turbulence", "scale": 0.004, "speedmin": 10, "speedmax": 30, "timescale": 0.4},
    ],
    "renderer": [{"id": 1, "name": "sprite"}],
    "sequencemultiplier": 1,
    "starttime": 0,
}
PROPS = {
    "creaturemusic": {"index": 15, "order": 115, "text": "Creature reacts to music (jaw, breath, colour split)",
                      "type": "bool", "value": True},
    "mandalaeye": {"index": 16, "order": 116, "text": "Eye in the mandala's centre (follows the cursor)",
                   "type": "bool", "value": True},
    "mandalaeyeopacity": {"index": 17, "order": 117, "text": "Mandala eye opacity (%)", "type": "slider",
                          "min": 0, "max": 100, "step": 1, "precision": 0, "value": 35,
                          "condition": "mandalaeye.value == true"},
}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent="\t"), encoding="utf-8")


def main():
    for root in (SRC, PROJ):              # the optimiser reads the scene from SRC but writes only PROJ
        write_json(root / "particles" / "mouth_smoke.json", PARTICLE)
        assert (root / "materials" / "edge_smoke.json").exists(), "run scripts/add_edge_smoke.py first"

    scene_path = SRC / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    objs = scene["objects"]
    objs[:] = [o for o in objs if o.get("name") != NAME]
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
    puff = {
        "angles": "0.00000 0.00000 0.00000",
        "id": max(ids) + 1,
        "image": None,
        "instanceoverride": {
            "rate": {"script": (HERE / "scripts" / "mouth_smoke.js").read_text(encoding="utf-8"), "value": 0.0},
            "id": max(ids) + 2,
        },
        "locktransforms": False,
        "model": None,
        "name": NAME,
        "origin": f"{MOUTH_WORLD[0]:.5f} {MOUTH_WORLD[1]:.5f} 0.00000",
        "parallaxDepth": "1.00000 1.00000",
        "particle": "particles/mouth_smoke.json",
        "scale": "1.00000 1.00000 1.00000",
        "visible": {"user": "creaturemusic", "value": True},
    }
    at = next(i for i, o in enumerate(objs) if o.get("name") == "K") + 1
    objs.insert(at, puff)
    k = next(o for o in objs if o.get("name") == "K")
    js = (HERE / "scripts" / "reptilian_layout.js").read_text(encoding="utf-8")
    assert f"'{NAME}'" in js, "reptilian_layout.js GROUP has no MouthSmoke"
    k["visible"]["script"] = js
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")

    pj_path = PROJ / "project.json"
    pj = json.loads(pj_path.read_text(encoding="utf-8"))
    props = pj["general"]["properties"]
    for name, v in PROPS.items():
        if name in props:
            v = {**v, "value": props[name].get("value", v["value"])}    # keep the user's setting
        props[name] = v
    pj_path.write_text(json.dumps(pj, indent=4, ensure_ascii=False), encoding="utf-8")
    print(f"{NAME} installed after K at world {MOUTH_WORLD}; properties:", ", ".join(PROPS))


if __name__ == "__main__":
    main()
