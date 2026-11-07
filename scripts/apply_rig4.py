"""Apply rig v4 (tools/rig4_face_chest.py output) to the live scene. Safe to re-run.

  * copies rig/v4/tex/*.tex into materials/masks
  * W, C, M, C2, K: "Rig: Head & Body" -> rig4_body maps; adds "Rig: Face" right after it
  * K: forehead-dot + ring-eye blinks (masked alpha pulses) at the top of its stack, so
    they act on the undeformed art and then ride the rig like everything else

Re-run scripts/add_bass_blue.py afterwards so CB_* pick up the new motion.
"""
import copy
import glob
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from we_paths import PROJ  # noqa: E402  (finds the WE project on any machine)
rep = json.loads((HERE / "reports" / "rig4_report.json").read_text())
ART_LAYERS = ["W", "C", "M", "C2", "K"]

for f in glob.glob(str(HERE / "rig" / "v4" / "tex" / "*.tex")):
    shutil.copy(f, PROJ / "materials" / "masks")

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


def shake(name, r):
    return {"file": "effects/shake/effect.json", "id": nid(), "name": name,
            "passes": [{"constantshadervalues": {"bounds": "0 1", "friction": "1 1",
                                                 "speed": r["speed"], "strength": r["strength"]},
                        "id": nid(), "textures": [None, r["flow"], r["time"]]}],
            "visible": True}


by = {o["name"]: o for o in scene["objects"]}
for name in ART_LAYERS:
    L = by[name]
    eff = [e for e in L["effects"] if e.get("name") != "Rig: Face"
           and not e.get("name", "").startswith("Blink: ")]
    i = next(k for k, e in enumerate(eff) if e.get("name") == "Rig: Head & Body")
    body = eff[i]
    c = body["passes"][0]["constantshadervalues"]
    c["strength"], c["speed"] = rep["body"]["strength"], rep["body"]["speed"]
    body["passes"][0]["textures"] = [None, rep["body"]["flow"], rep["body"]["time"]]
    eff.insert(i + 1, shake("Rig: Face", rep["face"]))
    if name == "K":
        b = rep["blinks"]
        labels = ["dot 1", "dot 2", "dot 3", "dot 4", "ring eye"]
        blinks = [{"file": "effects/pulse/effect.json", "id": nid(), "name": f"Blink: {lab}",
                   "passes": [{"combos": {"PULSEALPHA": 1, "PULSECOLOR": 0},
                               "constantshadervalues": {"amount": 1, "bounds": b["bounds"],
                                                        "noiseamount": 0, "noisespeed": 0.5,
                                                        "phase": it["phase"], "power": 1,
                                                        "speed": b["speed"],
                                                        "tinthigh": "1 1 1", "tintlow": "1 1 1"},
                               "id": nid(), "textures": [None, None, it["mask"]]}],
                   "visible": True} for lab, it in zip(labels, b["items"])]
        eff = blinks + eff
    L["effects"] = eff

scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
print({n: len(by[n]["effects"]) for n in ART_LAYERS})
