"""Tail follows the mouse on the horizontal axis. Safe to re-run.

  * installs the custom effect "tail_follow" (scripts/shader/tail_follow.*): WE's shake for the
    Rig: Tail settings plus a follow term, mixed so the total never exceeds the rig's own peak
    (strain-safe, see the .frag header)
  * swaps every "Rig: Tail" effect (all creature layers, Shadow and Outline included) from the
    built-in shake to it, keeping the same sway flow/time maps, speed and strength, plus the follow
    field masks/tail_follow_flow (run tools/tail_follow_field.py first); "follow" is driven by
    scripts/tail_follow.js
  * adds the user property `tailfollow` (slider, 0-100 %, default 100) to project.json

Re-run after add_shadow.py / add_bass_blue.py / rig scripts, which copy or rebuild the shake.
Usage: python scripts/add_tail_follow.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ  # noqa: E402

FX = "tail_follow"
SHADER_SRC = HERE / "scripts" / "shader"
SCRIPT = (HERE / "scripts" / "tail_follow.js").read_text(encoding="utf-8")
FOLLOW_TEX = "masks/tail_follow_flow"   # built by tools/tail_follow_field.py
FOLLOW_STRENGTH = 0.108                 # printed by tools/tail_follow_field.py


def install_effect():
    (PROJ / "shaders" / "effects" / f"{FX}.vert").write_text(
        (SHADER_SRC / f"{FX}.vert.in").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (PROJ / "shaders" / "effects" / f"{FX}.frag").write_text(
        (SHADER_SRC / f"{FX}.frag").read_text(encoding="utf-8"), encoding="utf-8", newline="\n")
    (PROJ / "materials" / "effects" / f"{FX}.json").write_text(json.dumps(
        {"passes": [{"shader": f"effects/{FX}", "blending": "normal", "depthtest": "disabled",
                     "depthwrite": "disabled", "cullmode": "nocull"}]}, indent="\t"))
    d = PROJ / "effects" / FX
    d.mkdir(exist_ok=True)
    (d / "effect.json").write_text(json.dumps({
        "version": 1, "replacementkey": FX, "name": "Tail rig + mouse follow",
        "description": "Rig: Tail sway plus a mouse-driven push along the same flow map",
        "group": "localeffects",
        "passes": [{"material": f"materials/effects/{FX}.json"}],
        "dependencies": [f"materials/effects/{FX}.json",
                         f"shaders/effects/{FX}.frag", f"shaders/effects/{FX}.vert"],
    }, indent="\t"))


def main():
    install_effect()
    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    done = []
    for o in scene["objects"]:
        for e in o.get("effects", []):
            if e.get("name") != "Rig: Tail":
                continue
            p = e["passes"][0]
            cv = p.get("constantshadervalues", {})
            e["file"] = f"effects/{FX}/effect.json"
            p.pop("combos", None)
            p["constantshadervalues"] = {
                "speed": cv.get("speed", 1.04),
                "strength": cv.get("strength", 0.074),
                "followstrength": FOLLOW_STRENGTH,
                "follow": {"script": SCRIPT, "value": 0.0},
            }
            assert p["textures"][1:3] == ["masks/rig2_tail_flow", "masks/rig2_tail_time"], p["textures"]
            p["textures"] = [None, "masks/rig2_tail_flow", "masks/rig2_tail_time", FOLLOW_TEX]
            done.append(o["name"])
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")

    proj_path = PROJ / "project.json"
    proj = json.loads(proj_path.read_text(encoding="utf-8"))
    props = proj["general"]["properties"]
    props["tailfollow"] = {"index": 3, "order": 103, "text": "Tail follows mouse (%)", "type": "slider",
                           "min": 0, "max": 100, "step": 1, "precision": 0, "value": 100}
    proj_path.write_text(json.dumps(proj, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("Rig: Tail swapped on:", done)
    print("user properties:", list(props))


if __name__ == "__main__":
    main()
