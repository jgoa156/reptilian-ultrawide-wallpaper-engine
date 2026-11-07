"""User-pickable ink colors: "Magenta" (layer M) and "Cyan" (C, C2, CB_*), hex color pickers in
Wallpaper Engine's properties panel.

How the color used to be made: each ink texture was a flat colour (cyan #55C3E9, magenta #E7196A)
multiplied by its audio pulse's tints, with the pulse in Add blend (tex * (low + pulse * high)).
M's tints were bound to two old reddish user colours through a broken script (the source of the
`setTimeout is not defined` log spam).

Now:
  * the textures are white (alpha kept), rebuilt from the pre-change .tex backups so re-runs are safe
  * every one of those pulses uses blend mode 0 (Normal: mix(low, high, pulse)) with low = high =
    the user colour, so the colour on screen is exactly the picked colour; the audio still drives
    the opacity (PULSEALPHA) as before
  * defaults are the colours those layers showed on a typical beat (pulse 0.75):
    magenta #FF124F; cyan #30F6FF (C showed #18EDFF, C2/CB #47FFFF)
  * project.json: colorhigh/colorlow removed, magentacolor/cyancolor added

Usage: python scripts/add_ink_colors.py
"""
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ, write_tex  # noqa: E402

BACKUP = HERE / "backups" / "2026-11-07_before_colors_spin_tail" / "materials"
WORK = HERE / "ink_white"

COLORS = {  # user property -> (label, default hex, layers)
    "magentacolor": ("Magenta", "FF124F", ["M"]),
    "cyancolor": ("Cyan", "30F6FF", ["C", "C2", "CB_Chest", "CB_Tail1", "CB_Tail2", "CB_Tail3", "CB_Tail4"]),
}


def hex_to_we(h):
    return " ".join(f"{int(h[i:i + 2], 16) / 255:.5f}" for i in (0, 2, 4))


def first_png(tex_path: Path) -> Image.Image:
    data = tex_path.read_bytes()
    start = data.index(b"\x89PNG\r\n\x1a\n")
    return Image.open(io.BytesIO(data[start:])).convert("RGBA")


def whiten(name: str):
    im = np.asarray(first_png(BACKUP / f"{name}.tex")).copy()
    im[..., :3] = 255
    WORK.mkdir(exist_ok=True)
    png = WORK / f"{name}.png"
    Image.fromarray(im).save(png, optimize=True)
    write_tex(PROJ / "materials" / f"{name}.tex", png)
    return im.shape[1], im.shape[0]


def main():
    scene_path = PROJ / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    by_name = {o.get("name"): o for o in scene["objects"]}
    done = []
    for key, (label, hexv, layers) in COLORS.items():
        for name in layers:
            o = by_name[name]
            pulses = [e for e in o.get("effects", []) if e.get("file") == "effects/pulse/effect.json"]
            assert len(pulses) == 1, (name, len(pulses))
            p = pulses[0]["passes"][0]
            p.setdefault("combos", {})["BLENDMODE"] = 0
            p["combos"].pop("PULSECOLOR", None)                       # default 1: tint on
            cv = p.setdefault("constantshadervalues", {})
            for t in ("tintlow", "tinthigh"):
                cv[t] = {"user": key, "value": hex_to_we(hexv)}
            tex = Path(o["image"]).stem                               # C2 shares C's texture
            size = whiten(tex)
            done.append(f"{name} ({tex}) -> {key} {size}")
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")

    proj_path = PROJ / "project.json"
    proj = json.loads(proj_path.read_text(encoding="utf-8"))
    props = proj.setdefault("general", {}).setdefault("properties", {})
    for old in ("colorhigh", "colorlow"):
        props.pop(old, None)
    for i, (key, (label, hexv, _)) in enumerate(COLORS.items()):
        props[key] = {"index": 1 + i, "order": 101 + i, "text": label, "type": "color",
                      "value": hex_to_we(hexv)}
    proj_path.write_text(json.dumps(proj, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("\n".join(done))
    print("user properties:", list(props))


if __name__ == "__main__":
    main()
