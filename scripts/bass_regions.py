"""Bass-piece regions from the user's hand-drawn cut map.

bass_blue/ref/user_cut_map.webp is an editor screenshot (mirrored by WE's flip option)
with the tail cuts drawn in yellow, one green stroke per tail portion and the area to
exclude from all blue painted red. bass_blue/ref/registration.json maps it onto the
texture (fitted by template matching the line art; see the session notes):

    screenshot (sx, sy)  ->  X = 5039 - (lx - pad + sx) / s,  Y = (ly - pad + sy - tpl_y0) / s

Returns soft full-resolution masks (0..1) for: CB_Chest, CB_Tail1 (tip) .. CB_Tail4 (base).
Tail portions form a partition of unity along the cuts, so neighbours blend over a few px
instead of leaving a seam or a gap.

Run directly to write a preview: python scripts/bass_regions.py <out.png>
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent.parent
REF = HERE / "bass_blue" / "ref"
TW, TH = 5040, 2160
F = 2                                         # work grid: 2 texture px per cell
GW, GH = TW // F, TH // F
FADE = 140.0                                  # px: blue fades out toward every cut (user request)


def _screenshot_masks():
    im = np.asarray(Image.open(REF / "user_cut_map.webp").convert("RGB")).astype(int)
    r, g, b = im[..., 0], im[..., 1], im[..., 2]
    yellow = (r > 180) & (g > 180) & (b < 120)
    green = (g > 110) & (r < 110) & (b < 120) & (g - r > 50)
    red = (r > 180) & (g < 80) & (b < 80)
    green = ndi.binary_opening(green, iterations=1)          # drop stray antialias pixels
    return yellow, green, red


def _to_texture(mask_sc, reg):
    """Sample a screenshot-space mask on the texture work grid."""
    gy, gx = np.mgrid[0:GH, 0:GW]
    X, Y = (gx + 0.5) * F, (gy + 0.5) * F
    sx = (5039 - X) * reg["s"] - (reg["lx"] - reg["pad"])
    sy = Y * reg["s"] - (reg["ly"] - reg["pad"]) + reg["tpl_y0"]
    h, w = mask_sc.shape
    xi, yi = np.round(sx).astype(int), np.round(sy).astype(int)
    ok = (xi >= 0) & (xi < w) & (yi >= 0) & (yi < h)
    out = np.zeros((GH, GW), bool)
    out[ok] = mask_sc[yi[ok], xi[ok]]
    return out, X, Y


def regions(return_debug=False):
    reg = json.loads((REF / "registration.json").read_text())
    ysc, gsc, rsc = _screenshot_masks()
    # red is a scribble: close + fill it into one solid area
    rsc = ndi.binary_fill_holes(ndi.binary_closing(rsc, iterations=6))
    yel, X, Y = _to_texture(ndi.binary_dilation(ysc, iterations=1), reg)
    grn, _, _ = _to_texture(gsc, reg)
    red, _, _ = _to_texture(rsc, reg)
    # the screenshot stops a few px short of the frame's bottom and right edges:
    # carry the red down / right to the edges
    gyv = (np.arange(GH) + 0.5) * F
    gxv = (np.arange(GW) + 0.5) * F
    low, rgt = gyv > 2050, gxv > 4980
    red[low] = np.maximum.accumulate(red[low], axis=0)
    red[:, rgt] = np.maximum.accumulate(red[:, rgt], axis=1)

    k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png")
                   .convert("RGBA"))[..., 3] > 64
    ks = k.reshape(GH, F, GW, F).any(axis=(1, 3))
    sil = ndi.binary_fill_holes(ndi.binary_closing(ks, iterations=4))
    tail = sil & ((X < 3950) | ((Y > 1800) & (X < 4600)))   # rig2 tail region, a bit wider

    # cut the tail along the yellow lines; each green stroke picks its portion
    cut = ndi.binary_dilation(yel, iterations=3)
    lab, n = ndi.label(tail & ~cut)
    glab, gn = ndi.label(grn)
    # order the strokes tip -> base (top -> bottom of the tail)
    cents = sorted(ndi.center_of_mass(grn, glab, range(1, gn + 1)), key=lambda c: c[0])
    portions = []
    for cy, cx in cents:
        stroke = glab == glab[int(round(cy)), int(round(cx))] if glab[int(round(cy)), int(round(cx))] else None
        ids = lab[(stroke if stroke is not None else (glab > 0)) & (lab > 0)]
        if not len(ids):                                     # stroke lies on a cut line: nearest piece
            d, (iy, ix) = ndi.distance_transform_edt(lab == 0, return_indices=True)
            ids = [lab[iy[int(cy), int(cx)], ix[int(cy), int(cx)]]]
        portions.append(int(np.bincount(ids).argmax()))
    if len(set(portions)) != len(portions):
        raise SystemExit(f"tail cuts don't separate the portions: {portions}")

    # hand every other tail cell (cut lines, slivers the strokes didn't mark) to the
    # nearest portion, so the four tile the whole tail
    seed = np.zeros(tail.shape, np.int32)
    for i, p in enumerate(portions):
        seed[lab == p] = i + 1
    _, (iy, ix) = ndi.distance_transform_edt(seed == 0, return_indices=True)
    owner = seed[iy, ix] * tail

    keep = 1 - np.clip(ndi.gaussian_filter(red.astype(np.float32), 6), 0, 1) * 1.0
    keep = np.clip((keep - 0.15) / 0.7, 0, 1)                # solid exclusion inside the red

    neck = np.interp(X, [4380, 4750, 5040], [1180, 1000, 880])
    chest = sil & (X > 4340) & (Y > neck) & ~tail

    out = {}

    def soft(m, sigma):
        return np.clip(ndi.gaussian_filter(m.astype(np.float32), sigma) * 1.0, 0, 1)

    def fade_from(inside, blockers):
        """0 at the slice's cut edges, rising to 1 over FADE px inward. Only the cuts
        (neighbour slices, the red area, the chest cut lines) count as edges, not the
        silhouette outline, so the stroke fringe along the outside keeps its strength."""
        d = ndi.distance_transform_edt(~blockers) * F
        r = np.clip(d / FADE, 0, 1)
        return r * r * (3 - 2 * r) * inside

    # dilate first so the hair-thin tip keeps full strength after softening
    sil_soft = np.clip(soft(ndi.binary_dilation(tail, iterations=2), 2.5) * 1.6, 0, 1)
    red_or_body = red | (sil & ~tail)
    for i in range(len(portions)):
        mine = owner == i + 1
        others = (tail & ~mine) | red_or_body
        out[f"CB_Tail{i + 1}"] = soft(fade_from(mine, others), 2.0) * sil_soft * keep
    below_neck = sil & ~tail & ~chest                        # head side of the chest cut
    chest_soft = np.clip(soft(ndi.binary_dilation(chest, iterations=2), 2.5) * 1.6, 0, 1)
    out["CB_Chest"] = soft(fade_from(chest, tail | red | below_neck), 2.0) * chest_soft * keep
    full = {k: np.asarray(Image.fromarray(v.astype(np.float32), "F").resize((TW, TH), Image.BILINEAR))
            for k, v in out.items()}
    if return_debug:
        return full, {"owner": owner, "red": red, "yellow": yel, "green": grn}
    return full


if __name__ == "__main__":
    masks, dbg = regions(return_debug=True)
    pal = {"CB_Chest": (40, 120, 255), "CB_Tail1": (255, 80, 80), "CB_Tail2": (255, 200, 0),
           "CB_Tail3": (60, 200, 60), "CB_Tail4": (200, 60, 220)}
    k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png")
                   .convert("RGBA"))[..., 3].astype(np.float32) / 255
    img = np.full((TH, TW, 3), 235, np.float32)
    for name, m in masks.items():
        img = img * (1 - m[..., None] * 0.6) + np.array(pal[name]) * m[..., None] * 0.6
    img = img * (1 - k[..., None] * 0.7)
    for key, col in (("red", (255, 0, 0)), ("yellow", (230, 200, 0)), ("green", (0, 150, 0))):
        m = np.asarray(Image.fromarray(dbg[key].astype(np.uint8) * 255).resize((TW, TH))) > 0
        if key == "red":
            img[m] = img[m] * 0.6 + np.array(col) * 0.4
        else:
            img[m] = col
    Image.fromarray(img.clip(0, 255).astype(np.uint8)).crop((3550, 250, 5040, 2160)).resize((745, 955)).save(sys.argv[1])
    for n_, m in masks.items():
        print(n_, "area px", int((m > 0.5).sum()))
