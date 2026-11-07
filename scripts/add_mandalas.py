"""Install the spectrum mandala into the live Wallpaper Engine scene.

Safe to re-run: existing Mandala* objects are replaced, not duplicated.

One layer, MandalaK, right above BG (behind the creature), with one custom effect,
"Spectrum mandala" (scripts/shader/mandala_spectrum.*). See the shader header for details:
  * the 13-fold black Choronzon mandala (materials/Choronzon_mandala_black.tex) is sampled
    by the effect, spun, and split into 13 pieces (one per figure) with fading sides
  * each piece pulses black with its own part of the spectrum, mirrored in stereo:
    the top arm takes the lowest bands, the right half takes the right channel and the
    left half takes the left channel, both rising in pitch toward the bottom
  * Rainbow Rings-style bulge per piece and a bass swell; Module Visualizer-style datamosh
    and the Leonard slice glitch on beats (all driven by scripts/mandala_controller.js, which is
    bound to MandalaK's alpha and also sets the overall opacity)
The layer image is a transparent canvas-sized texture (materials/mandala_canvas.tex): it only
sets the size the effect renders at.

Retired here (files removed): the cyan/magenta mandala layers (ghosts) and the old shake-based glitch
slice maps; the Leonard slice glitch now runs inside the shader, on the black layer only.
Also refreshes the layout script on layer K from scripts/reptilian_layout.js.

Usage: python scripts/add_mandalas.py
"""
import copy
import io
import json
import struct
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from we_paths import PROJ  # noqa: E402  (finds the WE project on any machine)
CANVAS = (5120, 2160)    # authored scene size
DIAMETER = 3000          # on-screen mandala size in canvas px (same as the BG kaleidoscope)
CENTER = (2560, 1080)
SHADER_SRC = HERE / "scripts" / "shader"
EFFECT = "mandala_spectrum"
EFFECT_NAME = "Spectrum mandala"

CONTROLLER_PROPS = {"period": 7, "depth": 0.6, "musicFloor": 0.15,
                    "moshChance": 1, "moshLevel": 0.7, "glitch": 1}
SHADER_VALUES = {
    "unitscale": f"{CANVAS[0] / (DIAMETER / 2):.5f} {CANVAS[1] / (DIAMETER / 2):.5f}",
    "turnperiod": {"user": "spinperiod", "value": 39.0},   # s per full turn, user-adjustable
    "feather": 0.35,
    "floor": 0.6,
    "bulge": 0.1,
    "bassscale": 0.04,
    **{f"arm{k}": 0 for k in range(13)}, "bass": 0,
    "mosh": 0, "moshseed": 0, "mosherrors": 3, "moshgrid": "160 68",
    "glitchslices": 0, "glitchseed": 0, "glitchshift": 0.1,
    "slice": 0,
    "minopacity": {"user": "mandalaminopacity", "value": 0.0},    # % at piece level 0
    "maxopacity": {"user": "mandalamaxopacity", "value": 15.0},   # % at piece level 1
    "blur": {"user": "mandalablur", "value": 0.0},                # canvas px
}
K_ALPHA_SCRIPT = (HERE / "scripts" / "mandala_controller.js").read_text(encoding="utf-8")
RETIRED_LAYERS = ["MandalaC", "MandalaM"]
RETIRED_FILES = ([f"materials/Choronzon_mandala_{c}.{x}" for c in ("cyan", "magenta")
                  for x in ("tex", "tex-json", "json")]
                 + [f"models/Choronzon_mandala_{c}.json" for c in ("cyan", "magenta")]
                 + [f"materials/masks/mandala_glitch_{i}.tex" for i in range(1, 5)])


def write_tex(path: Path, png_path: Path, mips: int = 5):
    """Embed the PNG (plus a halved mip chain) the way WE stores imported PNGs,
    modelled on materials/C.tex: FreeImage format 13, one PNG blob per mip."""
    im = Image.open(png_path).convert("RGBA")
    w, h = im.size
    levels = [png_path.read_bytes()]
    cur = im
    for _ in range(mips - 1):
        if min(cur.size) < 32:
            break
        cur = cur.resize((cur.width // 2, cur.height // 2), Image.LANCZOS)
        buf = io.BytesIO()
        cur.save(buf, "PNG", optimize=True)
        levels.append(buf.getvalue())
    hdr = b"TEXV0005\0TEXI0001\0" + struct.pack("<6i", 0, 2, w, h, w, h) + b"\xff\xff\xff\xff"
    hdr += b"TEXB0003\0" + struct.pack("<3i", 1, 13, len(levels))  # 1 image, FreeImage PNG
    body = b""
    for i, blob in enumerate(levels):
        body += struct.pack("<5i", w >> i, h >> i, 0, 0, len(blob)) + blob
    path.write_bytes(hdr + body)
    return w, h


def install_effect():
    vert = (SHADER_SRC / f"{EFFECT}.vert.in").read_text(encoding="utf-8")
    frag = (SHADER_SRC / f"{EFFECT}.frag").read_text(encoding="utf-8")
    (PROJ / "shaders" / "effects" / f"{EFFECT}.vert").write_text(vert, encoding="utf-8", newline="\n")
    (PROJ / "shaders" / "effects" / f"{EFFECT}.frag").write_text(frag, encoding="utf-8", newline="\n")
    (PROJ / "materials" / "effects" / f"{EFFECT}.json").write_text(json.dumps(
        {"passes": [{"shader": f"effects/{EFFECT}", "blending": "normal", "depthtest": "disabled",
                     "depthwrite": "disabled", "cullmode": "nocull"}]}, indent="\t"))
    d = PROJ / "effects" / EFFECT
    d.mkdir(exist_ok=True)
    (d / "effect.json").write_text(json.dumps({
        "version": 1,
        "replacementkey": EFFECT,
        "name": EFFECT_NAME,
        "description": "13 spectrum-driven black pieces of the Choronzon mandala, spinning; full when idle, sliced with music; bulge, datamosh, slice glitch",
        "group": "localeffects",
        "passes": [{"material": f"materials/effects/{EFFECT}.json"}],
        "dependencies": [f"materials/effects/{EFFECT}.json",
                         f"shaders/effects/{EFFECT}.frag", f"shaders/effects/{EFFECT}.vert"],
    }, indent="\t"))


def write_image(name: str, png: Path):
    """materials/<name>.tex + .tex-json + .json, models/<name>.json for an image layer."""
    w, h = write_tex(PROJ / "materials" / f"{name}.tex", png)
    (PROJ / "materials" / f"{name}.tex-json").write_text(json.dumps(
        {"bleedtransparentcolors": True, "clampuvs": True,
         "format": "rgba8888", "nonpoweroftwo": True}, indent="\t"))
    (PROJ / "materials" / f"{name}.json").write_text(json.dumps(
        {"passes": [{"blending": "translucent", "combos": {}, "cullmode": "nocull",
                     "depthtest": "disabled", "depthwrite": "disabled",
                     "shader": "genericimage4", "textures": [name]}]}, indent="\t"))
    (PROJ / "models" / f"{name}.json").write_text(json.dumps(
        {"autosize": True, "material": f"materials/{name}.json"}, indent="\t"))
    return w, h


def main():
    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    objs = scene["objects"]
    objs[:] = [o for o in objs if not o["name"].startswith("Mandala")]
    by_name = {o["name"]: o for o in objs}
    bg = by_name["BG"]

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
    next_id = max(ids) + 1

    def nid():
        nonlocal next_id
        next_id += 1
        return next_id - 1

    install_effect()
    # the mandala itself, sampled by the effect (no layer of its own)
    write_image("Choronzon_mandala_black", HERE / "Choronzon_mandala_black.png")
    # transparent canvas: sets the effect's render size
    canvas_png = HERE / "mandala_canvas.png"
    Image.fromarray(np.zeros((CANVAS[1], CANVAS[0], 4), np.uint8), "RGBA").save(canvas_png, optimize=True)
    w, h = write_image("mandala_canvas", canvas_png)

    effect = {"file": f"effects/{EFFECT}/effect.json", "id": nid(), "name": EFFECT_NAME,
              "passes": [{"constantshadervalues": dict(SHADER_VALUES), "id": nid(),
                          "textures": [None, None, "Choronzon_mandala_black"]}],
              "visible": True}
    obj = {
        "alpha": {"script": K_ALPHA_SCRIPT, "scriptproperties": dict(CONTROLLER_PROPS),
                  "value": 1.0},
        "castshadow": False,
        "effects": [effect],
        "id": nid(),
        "image": "models/mandala_canvas.json",
        "name": "MandalaK",
        "origin": f"{CENTER[0]:.5f} {CENTER[1]:.5f} 0.00000",
        "scale": "1.00000 1.00000 1.00000",
        "size": f"{w:.5f} {h:.5f}",
    }
    objs.insert(objs.index(bg) + 1, obj)

    for rel in RETIRED_FILES:
        (PROJ / rel).unlink(missing_ok=True)

    by_name["K"]["visible"]["script"] = (HERE / "scripts" / "reptilian_layout.js").read_text(encoding="utf-8")
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("layers:", [o["name"] for o in objs])

    # user property: mandala spin, seconds per full turn (bound to the effect's "turnperiod")
    proj_path = PROJ / "project.json"
    proj = json.loads(proj_path.read_text(encoding="utf-8"))
    props = proj.setdefault("general", {}).setdefault("properties", {})
    props["spinperiod"] = {"index": 4, "order": 104, "text": "Mandala spin (seconds per turn)",
                           "type": "slider", "min": 1, "max": 600, "step": 1, "precision": 0,
                           "value": SHADER_VALUES["turnperiod"]["value"]}
    props["mandalaminopacity"] = {"index": 5, "order": 105, "text": "Mandala min opacity (%)",
                                  "type": "slider", "min": 0, "max": 100, "step": 1, "precision": 0,
                                  "value": SHADER_VALUES["minopacity"]["value"]}
    props["mandalamaxopacity"] = {"index": 6, "order": 106, "text": "Mandala max opacity (%)",
                                  "type": "slider", "min": 0, "max": 100, "step": 1, "precision": 0,
                                  "value": SHADER_VALUES["maxopacity"]["value"]}
    props["mandalablur"] = {"index": 7, "order": 107, "text": "Mandala blur (px)",
                            "type": "slider", "min": 0, "max": 60, "step": 1, "precision": 0,
                            "value": SHADER_VALUES["blur"]["value"]}
    proj_path.write_text(json.dumps(proj, indent="\t", ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()
