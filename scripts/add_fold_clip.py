"""Append the "Lens fold clip" right after the lens distortion on EVERY layer that has one.
Safe to re-run (skips layers that already have it).

Why: the workshop lens folds back past len2 = 2/3, so the art quad's far corners show squashed
copies of the annulus around the lens centre. In the corner's direction that annulus is the gap
between the tail and the head; at rest it is empty (0 alpha, measured), but the tail sway and the
mouse follow push the tail 5-7 px into it, and the corner then shows a sliver per ink layer (the
cyan / black / magenta marks at the top right). The clip zeroes output with len2 > 0.55..0.62.
Measured: no layer has any ink in the source ring the clip removes (r 0.5377-0.544), so all real
art is kept; only the folded duplicates go.

Usage: python scripts/add_fold_clip.py
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
from add_mandalas import PROJ  # noqa: E402
from add_shadow import CLIP, install_clip_effect  # noqa: E402


def main():
    install_clip_effect()
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

    added = []
    for o in scene["objects"]:
        fx = o.get("effects", [])
        li = [i for i, e in enumerate(fx) if "lens_distortion" in e.get("file", "")]
        if not li or any(e.get("name") == "Lens fold clip" for e in fx):
            continue
        lens = fx[li[-1]]
        lc = lens["passes"][0]["constantshadervalues"]
        size = float(lc["size"]) * 4
        tw, th = (float(v) for v in o["size"].split()[:2])
        fx.insert(li[-1] + 1, {
            "file": f"effects/{CLIP}/effect.json", "id": nid(), "name": "Lens fold clip",
            "passes": [{"id": nid(), "constantshadervalues": {
                "center": lc["center"], "scale": f"{th / tw * size:.5f} {size:.5f}", "fold": "0.55 0.62"}}],
            "visible": True})
        added.append(o["name"])
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("fold clip added to:", added)


if __name__ == "__main__":
    main()
