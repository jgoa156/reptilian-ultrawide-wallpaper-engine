"""Black smoke rising from behind the creature (its screen edge only; WE's flip mirrors it with
everything else). Idempotent.

Writes, into the optimiser's source project AND the live project:
  particles/edge_smoke.json   WE particle system: Wallpaper Engine's own smoke2 sprite sheet (random
                              frame per puff), black, normal (translucent) blending
  materials/edge_smoke.json   genericparticle material on particle/smoke/smoke2 (a WE asset)
and into the source scene.json:
  layer "Smoke" right above MandalaK (so behind Shadow and every creature layer). Its visibility is
  bound to the user property `edgesmoke`, its instance-override alpha to scripts/smoke_opacity.js
  (`smokeopacity`, %). The layout script (scripts/reptilian_layout.js, refreshed on layer K) moves
  and scales it with the creature.
and into the live project.json: the two user properties.

Authored in the creature's own coordinates (5120x2160 canvas, creature pinned bottom-right): puffs
are born just below the bottom edge across the 1850 px next to the edge, rise ~105 px/s for 11-16 s
(fading out around two-thirds of the height), drift a little inward, grow 3x and turn slowly.
Calibrated on the approved still mock (mock/smoke_mock_compare.png, "light").
Then run scripts/optimize_creature.py.
Usage: python scripts/add_edge_smoke.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from we_paths import PROJ  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "backups" / "2026-11-07_before_optimize" / "project"

CP = [{"flags": 0, "id": i, "offset": "0 0 0"} for i in range(8)]
PARTICLE = {
    "animationmode": "randomframe",
    "children": None,
    "controlpoint": CP,
    "emitter": [{
        "directions": "1 1 0",
        "distancemax": "990 40 0",
        "distancemin": "0 0 0",
        "id": 7,
        "name": "boxrandom",
        "origin": "0 0 0",
        "rate": 8,
        "speedmax": 0,
        "speedmin": 0,
    }],
    "flags": 0,
    "initializer": [
        {"id": 2, "name": "lifetimerandom", "min": 11, "max": 16},
        {"id": 3, "name": "sizerandom", "min": 900, "max": 1300},
        {"id": 4, "name": "colorrandom", "min": "0 0 0", "max": "10 10 12"},
        {"id": 5, "name": "alpharandom", "min": 0.06, "max": 0.11},
        {"id": 6, "name": "velocityrandom", "min": "-75 85 0", "max": "5 125 0"},
        {"id": 12, "name": "rotationrandom", "min": "0 0 0", "max": "0 0 6.2831"},
        {"id": 13, "name": "angularvelocityrandom", "min": "0 0 -0.2", "max": "0 0 0.2"},
    ],
    "material": "materials/edge_smoke.json",
    "maxcount": 200,
    "operator": [
        {"id": 8, "name": "movement", "drag": 0, "gravity": "0 0 0"},
        {"id": 14, "name": "angularmovement", "drag": 0, "force": "0 0 0"},
        {"id": 9, "name": "alphafade", "fadeintime": 0.15, "fadeouttime": 0.6},
        {"id": 10, "name": "sizechange", "starttime": 0, "endtime": 1, "startvalue": 0.33, "endvalue": 1},
        {"id": 11, "name": "turbulence", "scale": 0.002, "speedmin": 8, "speedmax": 25, "timescale": 0.15},
    ],
    "renderer": [{"id": 1, "name": "sprite"}],
    "sequencemultiplier": 1,
    "starttime": 16,            # pre-simulate a full lifetime: the smoke is already there on load
}
MATERIAL = {"passes": [{
    "blending": "translucent",
    "combos": {"REFRACT": 0},
    "constantshadervalues": {"ui_editor_properties_overbright": 1.0},
    "cullmode": "nocull",
    "depthtest": "disabled",
    "depthwrite": "disabled",
    "shader": "genericparticle",
    "textures": ["particle/smoke/smoke2"],
}]}
PROPS = {
    "edgesmoke": {"index": 13, "order": 113, "text": "Smoke behind the creature", "type": "bool", "value": True},
    "smokeopacity": {"index": 14, "order": 114, "text": "Smoke opacity (%)", "type": "slider",
                     "min": 0, "max": 200, "step": 1, "precision": 0, "value": 100,
                     "condition": "edgesmoke.value == true"},
}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent="\t"), encoding="utf-8")


for root in (SRC, PROJ):
    write_json(root / "particles" / "edge_smoke.json", PARTICLE)
    write_json(root / "materials" / "edge_smoke.json", MATERIAL)

scene_path = SRC / "scene.json"
scene = json.loads(scene_path.read_text(encoding="utf-8"))
objs = scene["objects"]
objs[:] = [o for o in objs if o.get("name") != "Smoke"]
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
smoke = {
    "angles": "0.00000 0.00000 0.00000",
    "id": max(ids) + 1,
    "image": None,
    "instanceoverride": {
        "alpha": {"script": (HERE / "scripts" / "smoke_opacity.js").read_text(encoding="utf-8"), "value": 1.0},
        "id": max(ids) + 2,
    },
    "locktransforms": False,
    "model": None,
    "name": "Smoke",
    "origin": "4130.00000 -180.00000 0.00000",
    "parallaxDepth": "1.00000 1.00000",
    "particle": "particles/edge_smoke.json",
    "scale": "1.00000 1.00000 1.00000",
    "visible": {"user": "edgesmoke", "value": True},
}
at = next(i for i, o in enumerate(objs) if o.get("name") == "MandalaK") + 1
objs.insert(at, smoke)
k = next(o for o in objs if o.get("name") == "K")
k["visible"]["script"] = (HERE / "scripts" / "reptilian_layout.js").read_text(encoding="utf-8")
scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")

pj_path = PROJ / "project.json"
pj = json.loads(pj_path.read_text(encoding="utf-8"))
props = pj["general"]["properties"]
for name, v in PROPS.items():
    if name in props:
        v = {**v, "value": props[name].get("value", v["value"])}    # keep the user's setting
    props[name] = v
pj_path.write_text(json.dumps(pj, indent=4, ensure_ascii=False), encoding="utf-8")
print("Smoke layer installed above MandalaK; properties:", ", ".join(PROPS))
