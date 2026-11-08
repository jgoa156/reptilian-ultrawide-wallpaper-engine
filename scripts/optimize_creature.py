"""Performance pass: one "Creature warp" pass per creature layer instead of 7-27 built-in passes,
and the creature layers cropped to the area the creature can reach. Same look (see the header of
scripts/shader/creature_warp.frag.in for how the chains are reproduced).

Re-runnable: it always starts from the pre-optimisation copy of the project in
backups/2026-11-07_before_optimize/project (scene, layer textures, masks) and rewrites the live
project. If you change the scene's effects in the editor, refresh that copy first (or the change
is lost on the next run).

What it does
  1. reads every replaced effect's values from the scene (and checks all layers agree)
  2. packs the 20 masks into 7 RGBA textures (materials/masks/cw_*.tex, bit-exact copies)
  3. support masks: each layer's alpha, dilated by the largest possible total warp
  4. crops each creature texture to its support (+ warp + chromatic-aberration margin) and to the
     area the lens can spread it to; moves the layer origin so nothing shifts
  5. writes the effect (effects/creature_warp, shaders/effects/creature_warp.*) with the values
     baked in, and replaces the layers' effect lists:
        Shadow, W -> RIG; C, M, C2 -> CSTACK; CB_* -> CBCHEST / CBTAIL2 / CBTAIL (the colour
        layers keep WE's own audio pulse as a first pass, so audio and tint are untouched);
        K -> KPRE, WE's Ink edges (kept), KPOST
     (M's motion blur had rate 1, so it only round-tripped the image through an 8-bit buffer; it is
     dropped and that buffer's alpha cap is kept with "alphamax")
  4b. the cropped layer textures (one flat colour + alpha each) are written as DXT5 with 3 mips
  5b. MandalaK: the mandala texture as R8 (+ mips), WE's solid layer instead of the empty canvas
  6. deletes project files nothing references any more (all are in the backup copy)

Usage: python scripts/optimize_creature.py
"""
import json
import math
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as nd

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE / "scripts"))
sys.path.insert(0, str(HERE / "tools"))
from add_mandalas import PROJ, write_tex  # noqa: E402
from tex_io import read_tex, read_tex_levels, write_dxt5_rgba_tex, write_dxt5_tex, write_raw_tex  # noqa: E402

SRC = HERE / "backups" / "2026-11-07_before_optimize" / "project"
WORK = HERE / "optimized"
SHADER_SRC = HERE / "scripts" / "shader"
FX = "creature_warp"
TW, TH = 5040, 2160                      # full layer size (all creature layers share it)
ASPECT = TW / TH
TAIL_FOLLOW_JS = (HERE / "scripts" / "tail_follow.js").read_text(encoding="utf-8")

LAYOUT = {"RIG": 0, "CSTACK": 1, "KPRE": 2, "KPOST": 3, "CBCHEST": 4, "CBTAIL2": 5, "CBTAIL": 6}
LAYER_LAYOUT = {"Shadow": "RIG", "W": "RIG", "C": "CSTACK", "M": "CSTACK", "C2": "CSTACK",
                "CB_Chest": "CBCHEST", "CB_Tail2": "CBTAIL2", "CB_Tail4": "CBTAIL",
                "CB_Tail3": "CBTAIL", "CB_Tail1": "CBTAIL"}
CREATURE = ["Shadow", "W", "C", "M", "CB_Chest", "CB_Tail4", "CB_Tail3", "CB_Tail2", "CB_Tail1", "C2", "K"]
SUPPORT_SLOT = {"Shadow": ("a", 0), "W": ("a", 1), "C": ("a", 2), "M": ("a", 3), "C2": ("a", 2),
                "CB_Chest": ("b", 0), "CB_Tail4": ("b", 1), "CB_Tail3": ("b", 2), "CB_Tail2": ("b", 3),
                "CB_Tail1": ("c", 0), "K": ("c", 1)}
MASKS = "masks/"
MANDALA_TEX = "masks/mandala_alpha"      # the mandala's alpha as R8 (its RGB is all 0)


def f(v):
    return f"{float(v):.8g}"


def vec(*v):
    return f"vec{len(v)}(" + ", ".join(f(x) for x in v) + ")"


def nums(s):
    return [float(x) for x in str(s).split()]


def cval(v):
    """constantshadervalues entry -> plain value (user bindings and scripts keep their 'value')."""
    return v["value"] if isinstance(v, dict) else v


# ---------------------------------------------------------------- 1. effect values

def effect_values(scene):
    vals = {}
    for o in scene["objects"]:
        if o["name"] not in CREATURE:
            continue
        for e in o["effects"]:
            name = e.get("name") or Path(e["file"]).parent.name
            p = e["passes"][0]
            cv = {k: cval(v) for k, v in (p.get("constantshadervalues") or {}).items()}
            entry = {"cv": cv, "combos": p.get("combos") or {}, "textures": p.get("textures") or [],
                     "file": e["file"]}
            if name.startswith("(") or name.startswith("Blink"):       # per-layer pulses
                vals.setdefault(name, entry)
                continue
            if name in vals and name != "Rig: Tail":
                a, b = vals[name]["cv"], cv
                for k in set(a) | set(b):
                    x, y = a.get(k), b.get(k)
                    same = x == y
                    if not same and x is not None and y is not None:
                        try:
                            same = np.allclose(nums(x), nums(y))
                        except ValueError:
                            pass
                    assert same, f"{name}: {k} differs between layers ({x} vs {y})"
            vals.setdefault(name, entry)
    return vals


def constants(V, boxes, lens):
    L = []
    d = L.append
    d(f"#define ASPECT {f(ASPECT)}")

    def rig(tag, name, extra=None):
        cv = V[name]["cv"]
        assert cv.get("friction", "1 1") == "1 1" and cv.get("bounds", "0 1") == "0 1", name
        d(f"#define {tag}_SPEED {f(cv['speed'])}")
        d(f"#define {tag}_AMP2 {f(float(cv['strength']) ** 2)}")
    rig("HAIR", "Rig: Hair & Tendrils")
    rig("HB", "Rig: Head & Body")
    rig("BELLY", "Rig: Belly")
    rig("FACE", "Rig: Face")
    t = V["Rig: Tail"]["cv"]
    d(f"#define TAIL_SPEED {f(t.get('speed', 1.04))}")
    d(f"#define TAIL_AMP2 {f(float(t.get('strength', 0.074)) ** 2)}")
    d(f"#define TAIL_FOLLOW_AMP2 {f(float(t.get('followstrength', 0.108)) ** 2)}")
    # arm drop: the same field along y, followdrop x the lean, converted to v units
    d(f"#define TAIL_DROP_AMP2 {f(float(t.get('followstrength', 0.108)) ** 2 * float(t.get('followdrop', 0)) * TW / TH)}")

    def spin(tag, name):
        cv = V[name]["cv"]
        a = float(cv["angle"])
        d(f"#define {tag}_CENTER {vec(*nums(cv['center']))}")
        d(f"#define {tag}_AXIS {vec(math.cos(a), math.sin(a))}")
        d(f"#define {tag}_RATIO {f(cv['ratio'])}")
        d(f"#define {tag}_SIZE {f(cv['size'])}")
        d(f"#define {tag}_FEATHER {f(cv['feather'])}")
        d(f"#define {tag}_SPEED {f(cv['speed'])}")
        d(f"#define {tag}_PHASE {f(cv.get('phase', 0))}")
        assert not V[name]["combos"], (name, V[name]["combos"])
    spin("S1", "Olhar #1")
    spin("S2", "Olho #2")
    spin("S3", "Mini Eye #1")
    spin("S4", "Mini Eye #2")

    def twirl(tag, name):
        spin(tag, name)
        d(f"#define {tag}_AMOUNT {f(V[name]['cv']['amount'])}")
    twirl("W1", "Nose twirl")
    twirl("W2", "Honeycomb")

    def iris(tag, name):
        cv = V[name]["cv"]
        d(f"#define {tag}_SPEED {f(cv['speed'])}")
        d(f"#define {tag}_PHASE {f(cv.get('phase', 0))}")
        d(f"#define {tag}_ROUGH {f(cv['rough'])}")
        d(f"#define {tag}_NOISE {f(cv['noiseamount'])}")
        d(f"#define {tag}_SCALE {vec(*nums(cv['scale']))}")
    iris("I1", "Olho menor #1")
    iris("I2", "Little Eyes")

    def foliage(tag, name):
        cv = V[name]["cv"]
        assert not V[name]["combos"]
        a = ASPECT * float(cv["ratio"])
        dr = float(cv["scrolldirection"])
        c, s = math.cos(dr), math.sin(dr)
        nx, ny = 1.0 / a, a
        d(f"#define {tag}_NSCALE {f(cv['scale'])}")
        d(f"#define {tag}_NDIR {vec(nx * c - ny * s, nx * s + ny * c)}")
        d(f"#define {tag}_DIR {vec(c, s)}")
        d(f"#define {tag}_AMP0 {f(float(cv['strength']) ** 2 * 0.005)}")
        d(f"#define {tag}_PHASE {f(cv['phase'])}")
        d(f"#define {tag}_SPEED {f(cv['speeduv'])}")
        d(f"#define {tag}_POWER {f(cv['power'])}")
    foliage("F1", "Guelras")
    foliage("F2", "Strings Hair")
    foliage("F3", "Strings Back")

    cv = V["Tail edge shimmer"]["cv"]
    dr = float(cv["direction"])
    d(f"#define WW_DIR {vec(-math.sin(dr), math.cos(dr))}")
    d(f"#define WW_SPEED {f(cv['speed'])}")
    d(f"#define WW_SCALE {f(cv['scale'])}")
    d(f"#define WW_EXP {f(cv['exponent'])}")
    d(f"#define WW_STRENGTH2 {f(float(cv['strength']) ** 2)}")

    cv = V["Balance (General)"]["cv"]
    assert V["Balance (General)"]["combos"] == {"DIRECTION": 1}
    assert cv.get("friction", "1 1") == "1 1" and cv.get("bounds", "0 1") == "0 1"
    d(f"#define SH_SPEED {f(cv['speed'])}")
    d(f"#define SH_AMP2 {f(float(cv['strength']) ** 2)}")

    b = [V[f"Blink: dot {i}"]["cv"] for i in range(1, 5)] + [V["Blink: ring eye"]["cv"]]
    for k in ("bounds", "speed", "amount", "power", "noiseamount"):
        assert all(str(x[k]) == str(b[0][k]) for x in b), k
    assert float(b[0]["noiseamount"]) == 0
    d(f"#define BLINK_BOUNDS {vec(*nums(b[0]['bounds']))}")
    d(f"#define BLINK_SPEED {f(b[0]['speed'])}")
    d(f"#define BLINK_AMOUNT {f(b[0]['amount'])}")
    d(f"#define BLINK_POWER {f(b[0]['power'])}")
    for i, x in enumerate(b, 1):
        d(f"#define BLINK{i}_PHASE {f(x['phase'])}")

    cv = V["Guelras (2)"]["cv"]
    d(f"#define BLUR_CENTER {vec(*nums(cv['center']))}")
    d(f"#define BLUR_SCALE {f(cv['scale'])}")

    d(f"#define LENS_CENTER {vec(*lens['center'])}")
    d(f"#define LENS_SCALE {vec(*lens['scale'])}")
    d(f"#define LENS_K {f(lens['k'])}")
    d(f"#define LENS_CA {f(lens['ca'])}")
    d(f"#define FOLD_FROM {f(lens['fold'][0])}")
    d(f"#define FOLD_TO {f(lens['fold'][1])}")
    for k, bx in boxes.items():
        d(f"#define BOX_{k} {vec(*bx)}")
    return "\n".join(L)


def lens_params(V):
    cv = V["lens_distortion"]["cv"]
    assert float(cv["zoom"]) == 1 and float(cv["Distorsion 2"]) == 0, cv
    assert float(cv["ui_editor_properties_opacity"]) == 1
    assert not V["lens_distortion"]["combos"], V["lens_distortion"]["combos"]   # CA on, no anamorphic
    g = float(cv["general"])
    size = float(cv["size"])
    center = nums(cv["center"])
    scale = [TH / TW * max(1e-6, size * 4), max(1e-6, size * 4)]
    clip = V["Lens fold clip"]["cv"]
    assert np.allclose(nums(clip["center"]), center, atol=1e-4)
    assert np.allclose(nums(clip["scale"]), scale, atol=1e-4), (clip["scale"], scale)
    d1 = float(cv["Distorsion 1"])
    return {"center": center, "scale": scale, "k": -d1 * g,
            "ca": float(cv["chromaticAberration"]) * 0.1 * -d1 * g, "fold": nums(clip["fold"])}


# ---------------------------------------------------------------- 2. mask packs

def load_mask(name):
    a = read_tex(SRC / "materials" / f"{name}.tex")
    return a


def bbox_uv(nonzero, pad_texels=2.0):
    ys, xs = np.nonzero(nonzero)
    if len(xs) == 0:
        return (2.0, 2.0, -1.0, -1.0)                 # never inside
    h, w = nonzero.shape
    return ((xs.min() - pad_texels) / w, (ys.min() - pad_texels) / h,
            (xs.max() + 1 + pad_texels) / w, (ys.max() + 1 + pad_texels) / h)


def flow_nonzero(rg):
    return np.any(np.abs(rg.astype(np.int16) - 127) > 0, axis=-1)


def follow16(hl):
    """The arm follow field (tools/arm_follow_field.py): x flow in 16 bits, hi/lo bytes."""
    q = hl[..., 0].astype(np.int32) * 256 + hl[..., 1]
    return (q - 32640) / 32640.0


def build_packs(V):
    def tex_of(effect, i):
        return V[effect]["textures"][i]

    hair_f, hair_t = load_mask(tex_of("Rig: Hair & Tendrils", 1)), load_mask(tex_of("Rig: Hair & Tendrils", 2))
    tail_f, tail_t = load_mask(tex_of("Rig: Tail", 1)), load_mask(tex_of("Rig: Tail", 2))
    foll = load_mask(tex_of("Rig: Tail", 3))
    hb_f, hb_t = load_mask(tex_of("Rig: Head & Body", 1)), load_mask(tex_of("Rig: Head & Body", 2))
    be_f, be_t = load_mask(tex_of("Rig: Belly", 1)), load_mask(tex_of("Rig: Belly", 2))
    fa_f, fa_t = load_mask(tex_of("Rig: Face", 1)), load_mask(tex_of("Rig: Face", 2))
    bal = load_mask(tex_of("Balance (General)", 1))
    i1, i2 = load_mask(tex_of("Olho menor #1", 1)), load_mask(tex_of("Little Eyes", 1))
    f1, ww = load_mask(tex_of("Guelras", 1)), load_mask(tex_of("Tail edge shimmer", 1))
    f2, f3 = load_mask(tex_of("Strings Hair", 1)), load_mask(tex_of("Strings Back", 1))
    blur = load_mask(tex_of("Guelras (2)", 1))
    blinks = [load_mask(V[n]["textures"][2]) for n in
              ("Blink: dot 1", "Blink: dot 2", "Blink: dot 3", "Blink: dot 4", "Blink: ring eye")]
    for n, a in [("hair", hair_f), ("tail", tail_f), ("follow", foll), ("hb", hb_f), ("belly", be_f), ("bal", bal)]:
        assert a.shape == (720, 1720, 2), (n, a.shape)
    assert fa_f.shape == (1080, 2520, 2) and fa_t.shape == (1080, 2520, 1)

    def pack(*chans):
        return np.dstack([c if c.ndim == 2 else c[..., 0] for c in chans])

    zero = np.zeros((720, 1720), np.uint8)
    packs = {
        "cw_pack_a": pack(hair_f[..., 0], hair_f[..., 1], hair_t, tail_t),
        "cw_pack_b": pack(tail_f[..., 0], tail_f[..., 1], foll[..., 0], foll[..., 1]),
        "cw_pack_c": pack(hb_f[..., 0], hb_f[..., 1], hb_t, be_t),
        "cw_pack_d": pack(be_f[..., 0], be_f[..., 1], bal[..., 0], bal[..., 1]),
        "cw_pack_face": pack(fa_f[..., 0], fa_f[..., 1], fa_t, np.zeros((1080, 2520), np.uint8)),
        "cw_masks_1": pack(i1, i2, f1, ww),
        "cw_masks_2": pack(f2, f3, blinks[4], blur),
        "cw_blinks": pack(*blinks[:4]),
    }
    # the face pack is only read inside BOX_FACE (2 texels of padding around the face flow): crop it
    # to that box + 4 texels and sample it through BOX_FACE_RECT (x, y, w, h in full uv). Lossless.
    fh, fw = fa_f.shape[:2]
    ys, xs = np.nonzero(flow_nonzero(fa_f))
    fx0, fy0 = max(0, (xs.min() - 4) // 4 * 4), max(0, (ys.min() - 4) // 4 * 4)
    fx1, fy1 = min(fw, -(-(xs.max() + 5) // 4) * 4), min(fh, -(-(ys.max() + 5) // 4) * 4)
    packs["cw_pack_face"] = packs["cw_pack_face"][fy0:fy1, fx0:fx1]
    face_rect = (fx0 / fw, fy0 / fh, (fx1 - fx0) / fw, (fy1 - fy0) / fh)
    print(f"  face pack cropped to {fx1 - fx0}x{fy1 - fy0} of {fw}x{fh}")
    for name, a in packs.items():
        write_raw_tex(PROJ / "materials" / "masks" / f"{name}.tex", a)
    boxes = {
        "HAIR": bbox_uv(flow_nonzero(hair_f)),
        "TAIL": bbox_uv(flow_nonzero(tail_f) | (follow16(foll) != 0)),
        "HB": bbox_uv(flow_nonzero(hb_f)),
        "BELLY": bbox_uv(flow_nonzero(be_f)),
        "FACE": bbox_uv(flow_nonzero(fa_f)),
        "SH": bbox_uv(flow_nonzero(bal)),
        "I1": bbox_uv(i1[..., 0] > 0), "I2": bbox_uv(i2[..., 0] > 0),
        "F1": bbox_uv(f1[..., 0] > 0), "F2": bbox_uv(f2[..., 0] > 0), "F3": bbox_uv(f3[..., 0] > 0),
        "WW": bbox_uv(ww[..., 0] > 0), "BLUR": bbox_uv(blur[..., 0] > 0),
        "BLINK": bbox_uv(np.any(np.dstack([b[..., 0] for b in blinks]) > 0, axis=-1)),
        "FACE_RECT": face_rect,
    }
    fmax = lambda rg: float(np.abs((rg.astype(np.float32) / 255 - 0.498) * 2).max())   # noqa: E731
    return packs, boxes, {"hair": fmax(hair_f), "tail": fmax(tail_f), "follow": float(np.abs(follow16(foll)).max()),
                          "hb": fmax(hb_f), "belly": fmax(be_f), "face": fmax(fa_f), "bal": fmax(bal)}


def max_warp_px(V, fm):
    """Upper bound of the total displacement the continuous warps can apply, in layer px (each
    term uses the long axis, so it also bounds y). The spins and twirls are left out: they only
    move points inside their own small circle, and those circles are added to the support instead
    (see spin_circles)."""
    c = lambda n, k: float(V[n]["cv"][k])           # noqa: E731
    t = V["Rig: Tail"]["cv"]
    parts = {
        "hair": c("Rig: Hair & Tendrils", "strength") ** 2 * fm["hair"] * TW,
        "tail": (float(t.get("strength", 0.074)) ** 2 * fm["tail"]
                 + float(t.get("followstrength", 0.108)) ** 2 * fm["follow"]
                 * (1 + float(t.get("followdrop", 0)))) * TW,
        "head-body": c("Rig: Head & Body", "strength") ** 2 * fm["hb"] * TW,
        "belly": c("Rig: Belly", "strength") ** 2 * fm["belly"] * TW,
        "face": c("Rig: Face", "strength") ** 2 * fm["face"] * TW,
        "balance": c("Balance (General)", "strength") ** 2 * fm["bal"] * TW,
        "shimmer": c("Tail edge shimmer", "strength") ** 2 * TW,
        "blur": 5.21 * c("Guelras (2)", "scale") * 0.025 * TW,
    }
    for n in ("Guelras", "Strings Hair", "Strings Back"):
        a = ASPECT * c(n, "ratio")
        nd_ = max(abs(x) for x in (1 / a, a))
        parts[n] = 4 * c(n, "strength") ** 2 * 0.005 * nd_ * TW
    for n in ("Olho menor #1", "Little Eyes"):
        parts[n] = (4 + c(n, "noiseamount")) * max(nums(V[n]["cv"]["scale"])) * 0.001 * TW
    print("  warp bound by effect (px):", {k: round(v, 1) for k, v in parts.items()})
    return sum(parts.values())


def spin_circles(V):
    """Bounding boxes (full uv) of the spin / twirl circles."""
    out = []
    for n in ("Olhar #1", "Olho #2", "Mini Eye #1", "Mini Eye #2", "Nose twirl", "Honeycomb"):
        cv = V[n]["cv"]
        cx, cy = nums(cv["center"])
        r = (float(cv["size"]) + float(cv["feather"])) / min(1.0, float(cv["ratio"]))   # in aspect-x units
        out.append((cx - r / ASPECT, cy - r, cx + r / ASPECT, cy + r))
    return out


# ---------------------------------------------------------------- 3/4. supports and crops

def layer_texture(o):
    model = json.loads((SRC / o["image"]).read_text(encoding="utf-8"))
    mat = json.loads((SRC / model["material"]).read_text(encoding="utf-8"))
    return mat["passes"][0]["textures"][0]


def lens_point(u, v, lens, k):
    cx, cy = lens["center"]
    bx, by = u - cx, v - cy
    dx, dy = bx / lens["scale"][0], by / lens["scale"][1]
    l2 = dx * dx + dy * dy
    return cx + bx * (1 + k * l2), cy + by * (1 + k * l2), l2


def crops_and_supports(scene, lens, reach_px, circles):
    S = 4                                            # support grid: 1260 x 540
    gw, gh = TW // S, TH // S
    ca_px = 0.0
    supports, rects = {}, {}
    tex_alpha = {}
    for o in scene["objects"]:
        if o["name"] not in CREATURE:
            continue
        tex = layer_texture(o)
        if tex not in tex_alpha:
            a = read_tex(SRC / "materials" / f"{tex}.tex")
            assert a.shape[:2] == (TH, TW), (tex, a.shape)
            tex_alpha[tex] = a
    # chromatic aberration reach inside the visible lens area
    yy, xx = np.mgrid[0:gh, 0:gw]
    U, Vv = (xx + 0.5) / gw, (yy + 0.5) / gh
    gx, gy, l2 = lens_point(U, Vv, lens, lens["k"])
    rx, ry, _ = lens_point(U, Vv, lens, lens["k"] + lens["ca"])
    vis = l2 < lens["fold"][1]
    ca_px = float(np.max(np.hypot((rx - gx)[vis] * TW, (ry - gy)[vis] * TH)))
    dil = int(math.ceil(reach_px / S)) + 2
    for tex, a in tex_alpha.items():
        al = a[..., 3] > 0
        blk = al.reshape(gh, S, gw, S).any(axis=(1, 3))
        for x0, y0, x1, y1 in circles:                 # a spin/twirl can move points anywhere in its circle
            sl = (slice(max(0, int(y0 * gh) - 1), int(math.ceil(y1 * gh)) + 1),
                  slice(max(0, int(x0 * gw) - 1), int(math.ceil(x1 * gw)) + 1))
            if blk[sl].any():
                blk[sl] = True
        sup = nd.binary_dilation(blk, structure=np.ones((3, 3), bool), iterations=dil)
        supports[tex] = sup
        # texture area any sample can reach: support + warp + CA
        big = nd.binary_dilation(sup, structure=np.ones((3, 3), bool), iterations=int(math.ceil(ca_px / S)) + 2)
        ys, xs = np.nonzero(big)
        r = [xs.min() * S, ys.min() * S, (xs.max() + 1) * S, (ys.max() + 1) * S]
        # output area the lens spreads the support to
        sx = np.clip((gx * gw).astype(int), 0, gw - 1)
        sy = np.clip((gy * gh).astype(int), 0, gh - 1)
        out = vis & sup[sy, sx]
        ys, xs = np.nonzero(out)
        if len(xs):
            r = [min(r[0], xs.min() * S), min(r[1], ys.min() * S),
                 max(r[2], (xs.max() + 1) * S), max(r[3], (ys.max() + 1) * S)]
        # 8 px margin, edges on a 16 px grid: DXT5 blocks are 4x4, so mips 0-2 stay block-aligned
        r = [int(max(0, r[0] - 8) // 16 * 16), int(max(0, r[1] - 8) // 16 * 16),
             int(min(TW, -(-(r[2] + 8) // 16) * 16)), int(min(TH, -(-(r[3] + 8) // 16) * 16))]
        rects[tex] = r
    return tex_alpha, supports, rects, ca_px


# ---------------------------------------------------------------- 5. effect + scene

def install_effect(consts):
    for ext in ("frag", "vert"):
        text = (SHADER_SRC / f"{FX}.{ext}.in").read_text(encoding="utf-8").replace("@@CONSTANTS@@", consts)
        (PROJ / "shaders" / "effects" / f"{FX}.{ext}").write_text(text, encoding="utf-8", newline="\n")
    (PROJ / "materials" / "effects" / f"{FX}.json").write_text(json.dumps(
        {"passes": [{"shader": f"effects/{FX}", "blending": "normal", "depthtest": "disabled",
                     "depthwrite": "disabled", "cullmode": "nocull"}]}, indent="\t"))
    d = PROJ / "effects" / FX
    d.mkdir(exist_ok=True)
    (d / "effect.json").write_text(json.dumps({
        "version": 1, "replacementkey": FX, "name": "Creature warp",
        "description": "All of the creature's motion effects, lens and fold clip in one pass",
        "group": "localeffects",
        "passes": [{"material": f"materials/effects/{FX}.json"}],
        "dependencies": [f"materials/effects/{FX}.json", f"shaders/effects/{FX}.frag", f"shaders/effects/{FX}.vert"],
    }, indent="\t"))


def main():
    assert SRC.is_dir(), SRC
    WORK.mkdir(exist_ok=True)
    scene = json.loads((SRC / "scene.json").read_text(encoding="utf-8"))
    V = effect_values(scene)
    lens = lens_params(V)
    packs, boxes, fm = build_packs(V)
    reach = max_warp_px(V, fm)
    tex_alpha, supports, rects, ca_px = crops_and_supports(scene, lens, reach, spin_circles(V))
    print(f"max warp {reach:.0f} px, chromatic aberration reach {ca_px:.0f} px")

    # support textures
    gh, gw = next(iter(supports.values())).shape
    sup_tex = {k: np.zeros((gh, gw, 4), np.uint8) for k in "abc"}
    by_name = {o["name"]: o for o in scene["objects"]}
    for name in CREATURE:
        tex = layer_texture(by_name[name])
        k, ch = SUPPORT_SLOT[name]
        sup_tex[k][..., ch] = np.maximum(sup_tex[k][..., ch], supports[tex].astype(np.uint8) * 255)
    for k, a in sup_tex.items():
        write_raw_tex(PROJ / "materials" / "masks" / f"cw_support_{k}.tex", a)

    # cropped layer textures
    for tex, r in rects.items():
        a = tex_alpha[tex][r[1]:r[3], r[0]:r[2]]
        png = WORK / f"{tex}.png"
        Image.fromarray(a, "RGBA").save(png, optimize=True)
        fmt = write_layer_texture(tex, a, png)
        print(f"  {tex:28} crop {r}  {(r[2]-r[0])*(r[3]-r[1]) / (TW*TH) * 100:5.1f}% of the layer, {fmt}")

    consts = constants(V, boxes, lens)
    install_effect(consts)

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
    next_id = [max(ids) + 1]

    def nid():
        next_id[0] += 1
        return next_id[0] - 1

    k_rect = rects[layer_texture(by_name["K"])]
    k_cx, k_cy = (k_rect[0] + k_rect[2]) / 2, (k_rect[1] + k_rect[3]) / 2
    assert "const TEX_CX = 2520;" in TAIL_FOLLOW_JS and "const TEX_CY = 1080;" in TAIL_FOLLOW_JS
    follow_js = (TAIL_FOLLOW_JS.replace("const TEX_CX = 2520;", f"const TEX_CX = {k_cx:g};")
                 .replace("const TEX_CY = 1080;", f"const TEX_CY = {k_cy:g};"))
    assert "const AXIS = 0;" in follow_js, "tail_follow.js has no AXIS constant"
    follow_down_js = follow_js.replace("const AXIS = 0;", "const AXIS = 1;")

    def uber(layer, layout):
        o = by_name[layer]
        tex = layer_texture(o)
        r = rects[tex]
        k, ch = SUPPORT_SLOT[layer]
        sel = ["0"] * 4
        sel[ch] = "1"
        cv = {"uvrect": f"{r[0]/TW:.8f} {r[1]/TH:.8f} {(r[2]-r[0])/TW:.8f} {(r[3]-r[1])/TH:.8f}",
              "supportsel": " ".join(sel)}
        combos = {"LAYOUT": LAYOUT[layout]}
        names = {e.get("name"): e for e in o["effects"]}
        tail = names.get("Rig: Tail")
        if tail is not None and layout != "KPRE":
            fol = dict(tail["passes"][0]["constantshadervalues"]["follow"])
            fol["script"] = follow_js
            cv["follow"] = fol
            cv["followdown"] = {"script": follow_down_js, "value": 0.0}     # arm drop (cursor below the tip)
        if any(e.get("file", "").endswith("motionblur/effect.json") for e in o["effects"]):
            cv["alphamax"] = 1.0          # the motion blur's 8-bit buffer capped the pulsed alpha
        sup = f"{MASKS}cw_support_{k}"
        T = [None] * 10
        if layout == "KPRE":
            T[1] = sup
            T[6], T[7], T[8] = MASKS + "cw_masks_1", MASKS + "cw_masks_2", MASKS + "cw_blinks"
        else:
            T[1], T[2], T[3], T[4] = (MASKS + "cw_pack_a", MASKS + "cw_pack_b", MASKS + "cw_pack_c", MASKS + "cw_pack_d")
            if layout in ("RIG", "CSTACK", "KPOST"):
                T[5] = MASKS + "cw_pack_face"
            if layout in ("CSTACK", "KPOST", "CBCHEST", "CBTAIL2"):
                T[6] = MASKS + "cw_masks_1"
            if layout in ("CSTACK", "KPOST"):
                T[7] = MASKS + "cw_masks_2"
            T[8] = sup
        while T and T[-1] is None:
            T.pop()
        return {"file": f"effects/{FX}/effect.json", "id": nid(), "name": f"Creature warp ({layout})",
                "passes": [{"combos": combos, "constantshadervalues": cv, "id": nid(), "textures": T}],
                "visible": True}

    for name in CREATURE:
        o = by_name[name]
        if name == "K":
            edges = next(e for e in o["effects"] if e.get("name") == "Ink edges")
            o["effects"] = [uber("K", "KPRE"), edges, uber("K", "KPOST")]
        else:
            pulse = [e for e in o["effects"] if (e.get("name") or "").startswith("(")]   # WE's own audio pulse
            o["effects"] = pulse + [uber(name, LAYER_LAYOUT[name])]
        r = rects[layer_texture(o)]
        sx, sy = (nums(o["scale"])[:2] if o.get("scale") else (1.0, 1.0))
        ox, oy, oz = nums(o["origin"])
        cx, cy = (r[0] + r[2]) / 2, (r[1] + r[3]) / 2
        o["origin"] = f"{ox + (cx - TW / 2) * sx:.5f} {oy + (TH / 2 - cy) * sy:.5f} {oz:.5f}"
        o["size"] = f"{r[2] - r[0]:.5f} {r[3] - r[1]:.5f}"

    optimize_mandala(scene)
    optimize_background()
    (PROJ / "scene.json").write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print("passes per layer:", {n: len(by_name[n]["effects"]) for n in CREATURE})
    cleanup(scene)


# ---------------------------------------------------------------- 4b. layer texture format

def write_layer_texture(tex, rgba, png):
    """Every creature layer is one flat colour plus alpha. Such a layer is stored as DXT5: the
    colour block hits the colour exactly (565 permitting), the alpha is BC3-encoded per 4x4 block
    (~98 % of pixels exact, the rest are anti-aliased edge pixels within a few levels). 1 byte per
    pixel in VRAM instead of 4. Mips: halved alpha (Lanczos, like the PNG imports), as many levels
    as stay multiples of 4. A layer with more than one visible colour keeps the PNG import."""
    vis = rgba[..., 3] > 0
    cols = np.unique(rgba[..., :3][vis].reshape(-1, 3), axis=0)
    meta = PROJ / "materials" / f"{tex}.tex-json"
    if len(cols) != 1 or rgba.shape[0] % 4 or rgba.shape[1] % 4:
        write_tex(PROJ / "materials" / f"{tex}.tex", png)
        fmt = "rgba8888"
    else:
        alpha = rgba[..., 3]
        mips, cur = [], Image.fromarray(alpha, "L")
        while len(mips) < 4 and cur.width % 8 == 0 and cur.height % 8 == 0:
            cur = cur.resize((cur.width // 2, cur.height // 2), Image.LANCZOS)
            mips.append(np.asarray(cur))
        write_dxt5_tex(PROJ / "materials" / f"{tex}.tex", [int(v) for v in cols[0]], alpha, mips)
        fmt = f"dxt5 + {len(mips)} mips"
    m = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {
        "bleedtransparentcolors": True, "clampuvs": True, "nonpoweroftwo": True}
    m["format"] = fmt.split()[0]
    meta.write_text(json.dumps(m, indent="\t"), encoding="utf-8")
    return fmt


# ---------------------------------------------------------------- 5c. background layer

BG_TEX = "kaleidoscope10_15_24120703AM"


def optimize_background():
    """BG (the kaleidoscope) is drawn at layer alpha 0.1 and its own alpha peaks at 169, so it is
    never more than 6.6 % opaque: DXT5's colour error (a few levels) is far below one screen level
    there. Stored as general DXT5 (1/4 of the VRAM), padded 1500 -> 1504 by edge replication
    (image size stays 1500, like WE's own padded import), 4 mip levels."""
    rgba = read_tex(SRC / "materials" / f"{BG_TEX}.tex")
    h, w = rgba.shape[:2]
    pw, ph = -(-w // 16) * 16, -(-h // 16) * 16
    pad = np.pad(rgba, ((0, ph - h), (0, pw - w), (0, 0)), mode="edge")
    levels, cur = [pad], Image.fromarray(pad, "RGBA")
    while len(levels) < 4 and cur.width % 8 == 0 and cur.height % 8 == 0:
        cur = cur.resize((cur.width // 2, cur.height // 2), Image.LANCZOS)
        levels.append(np.asarray(cur))
    write_dxt5_rgba_tex(PROJ / "materials" / f"{BG_TEX}.tex", levels, (w, h))
    back = read_tex(PROJ / "materials" / f"{BG_TEX}.tex").astype(int)
    vis = back[..., 3:4] / 255 * 0.1
    err = np.abs(back[..., :3] * vis - rgba[..., :3].astype(int) * (rgba[..., 3:4] / 255 * 0.1))
    meta = PROJ / "materials" / f"{BG_TEX}.tex-json"
    m = json.loads(meta.read_text(encoding="utf-8")) if meta.exists() else {"clampuvs": True, "nonpoweroftwo": True}
    m["format"] = "dxt5"
    meta.write_text(json.dumps(m, indent="\t"), encoding="utf-8")
    print(f"  BG: dxt5 {pw}x{ph} (image {w}x{h}) + {len(levels) - 1} mips; on-screen error max {err.max():.2f} levels")


# ---------------------------------------------------------------- 5b. mandala layer

def optimize_mandala(scene):
    """MandalaK draws everything in its "Spectrum mandala" shader, which only reads the alpha of
    the mandala texture: store that alpha as R8 with the same five mip levels (bit-exact; 1/4 of
    the VRAM of the RGBA PNG import) and read .r. The layer's own image was an empty 5120x2160
    RGBA texture the shader never reads; WE's texture-less solid layer of the same size replaces
    it."""
    o = next(o for o in scene["objects"] if o["name"] == "MandalaK")
    fx = next(e for e in o["effects"] if e["file"].endswith("mandala_spectrum/effect.json"))
    tex = fx["passes"][0]["textures"]
    levels = read_tex_levels(SRC / "materials" / f"{tex[2]}.tex")
    assert all(int(lv[..., :3].max()) == 0 for lv in levels), "mandala texture has colour, keep it RGBA"
    write_raw_tex(PROJ / "materials" / f"{MANDALA_TEX}.tex", levels[0][..., 3], [lv[..., 3] for lv in levels[1:]])
    tex[2] = MANDALA_TEX
    o["image"] = "models/util/solidlayer.json"
    o["solid"] = True
    o["color"] = "0.00000 0.00000 0.00000"
    # the controller script lives in scripts/ (glitch/datamosh user properties were added there)
    o["alpha"]["script"] = (HERE / "scripts" / "mandala_controller.js").read_text(encoding="utf-8")
    # spin angle set by that script (tempo-following spin); 0 = the shader's own g_Time spin
    fx["passes"][0].setdefault("constantshadervalues", {}).update({"spinphase": 0.0, "spinscripted": 0.0})
    frag =(SHADER_SRC / "mandala_spectrum.frag").read_text(encoding="utf-8")
    out = (frag.replace("0.0).a * inside", "0.0).r * inside")
               .replace("lod).a * step(", "lod).r * step(")
               .replace('"default":"Choronzon_mandala_black"', f'"default":"{MANDALA_TEX}"'))
    assert out.count(").r * ") == 2, "mandala_spectrum.frag samples changed; update optimize_mandala"
    out = "// GENERATED by scripts/optimize_creature.py: mandala alpha read from an R8 texture (.r).\n" + out
    (PROJ / "shaders" / "effects" / "mandala_spectrum.frag").write_text(out, encoding="utf-8", newline="\n")
    print(f"  MandalaK: solid layer, mandala {levels[0].shape[1]}x{levels[0].shape[0]} R8 + {len(levels) - 1} mips")


# ---------------------------------------------------------------- 6. orphans

def cleanup(scene):
    keep = {"project.json", "scene.json", "preview.gif", "scene.pkg"}   # scene.pkg: WE's publish package

    def add_material(rel):
        keep.add(rel)
        m = json.loads((PROJ / rel).read_text(encoding="utf-8"))
        for p in m.get("passes", []):
            sh = p.get("shader")
            if sh:
                keep.update({f"shaders/{sh}.frag", f"shaders/{sh}.vert"})
            for t in p.get("textures") or []:
                if t:
                    add_texture(t)

    def add_texture(t):
        for ext in (".tex", ".tex-json", ".json"):
            if (PROJ / "materials" / f"{t}{ext}").exists() and ext != ".json":
                keep.add(f"materials/{t}{ext}")

    for o in scene["objects"]:
        if o.get("particle"):                       # particle layer (edge smoke): system + material
            keep.add(o["particle"])
            add_material(json.loads((PROJ / o["particle"]).read_text(encoding="utf-8"))["material"])
            continue
        if not (PROJ / o["image"]).exists():
            assert o["image"].startswith("models/util/"), o["image"]     # WE built-in (solid layer)
        else:
            model = json.loads((PROJ / o["image"]).read_text(encoding="utf-8"))
            keep.add(o["image"])
            add_material(model["material"])
        for e in o.get("effects", []):
            keep.add(e["file"])
            ej = json.loads((PROJ / e["file"]).read_text(encoding="utf-8"))
            for dep in ej.get("dependencies", []):
                keep.add(dep)
            for p in ej.get("passes", []):
                if p.get("material"):
                    add_material(p["material"])
            for p in e.get("passes", []):
                for t in p.get("textures") or []:
                    if t:
                        add_texture(t)
    removed = 0
    for f_ in sorted(PROJ.rglob("*")):
        if f_.is_file():
            rel = f_.relative_to(PROJ).as_posix()
            if rel not in keep:
                f_.unlink()
                removed += 1
    for d in sorted((p for p in PROJ.rglob("*") if p.is_dir()), key=lambda p: -len(p.parts)):
        if not any(d.iterdir()):
            d.rmdir()
    print(f"removed {removed} unreferenced files")


if __name__ == "__main__":
    main()
