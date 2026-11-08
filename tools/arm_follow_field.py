"""Mouse-follow field v2: the whole arm (the spike next to the head AND the coil it grows from)
leans toward the cursor. Replaces tools/tail_follow_field.py (which only bent the spike above
y 1150, 52 px at the tip).

  * bend weight w = t^p, t = geodesic distance along the arm from where the coil joins the body
    (0) to the spike tip (1), so the coil flexes a little and the spike swings as one limb
  * w is carried to the empty space around the arm (nearest arm pixel, then blurred), and a
    territory weight m takes it to 0 across the gap toward the head/body, which never move
  * displacement = (A * w * m, 0). Limits: strain <= INK_STRAIN on any inked pixel (K or W
    silhouette), |d(dx)/dx| <= GAP_COMPRESS everywhere (no fold; the gap is transparent, so its
    stretch is invisible). A is set so the tip moves TIP_PX (or less, if a limit binds first)
  * stored as 16 bits over two channels (hi, lo): 8 bits would step 1.2 px at 150 px of reach.
    Linear filtering commutes with the decode, so bilinear sampling stays exact.
    Decode: q = hi*256 + lo, flow_x = (q - 32640) / 32640 (zero = hi 127, lo 128).

  * drop (v3): when the cursor is below the tip the arm also lowers, dy = DROP * w * m, the same
    shape (so the shader reuses the field: dy = followdrop * dx, no extra texture). Checked together
    with the lean: ink strain <= INK_STRAIN and Jacobian determinant >= MIN_DET (no fold) for full
    drop with full lean either way. With the cursor on the mandala's centre the tip leans left and
    drops onto the "record".

Writes masks/arm_follow_flow16.tex into the pre-optimisation project copy (the optimiser's
source), points every "Rig: Tail" there at it with the new followstrength, and saves previews
(rig/v6/). Then run scripts/optimize_creature.py.
Usage: python tools/arm_follow_field.py [--tip 150] [--drop 120] [--dry]
"""
import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2
import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra

import tex_io

HERE = Path(__file__).resolve().parent.parent
SRC = HERE / "backups" / "2026-11-07_before_optimize" / "project"
OUT = HERE / "rig" / "v6"
TEX = "masks/arm_follow_flow16"
TW, TH = 5040, 2160
MW, MH = 1720, 720                      # the rig maps' grid
F = 4                                   # analysis grid: 4 px cells
GW, GH = TW // F, TH // F
INK_STRAIN = 0.25
GAP_COMPRESS = 0.8
MIN_DET = 0.2                           # same as GAP_COMPRESS 0.8: compressed 5x at most, never folded
Q0 = 32640


def arm_masks():
    k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA"))[..., 3]
    w = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA"))[..., 3]
    s = np.asarray(Image.fromarray(np.maximum(k, w)).resize((GW, GH), Image.BOX)) > 64
    sil = ndi.binary_fill_holes(ndi.binary_closing(s, iterations=2))
    gy, gx = np.mgrid[0:GH, 0:GW]
    X, Y = (gx + 0.5) * F, (gy + 0.5) * F
    arm = sil & ((X < 3950) | ((Y > 1870) & (X < 4560)))          # rig2.py's tail region
    rest = sil & ~arm
    return sil, arm, rest, Y


def geodesic_t(arm, rest, Y):
    """0 where the arm meets the body (bottom), 1 at the farthest point (the spike tip)."""
    idx = -np.ones(arm.shape, int)
    ys, xs = np.nonzero(arm)
    idx[ys, xs] = np.arange(len(ys))
    rows, cols, wts = [], [], []
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        y2, x2 = ys + dy, xs + dx
        ok = (y2 < arm.shape[0]) & (x2 >= 0) & (x2 < arm.shape[1])
        ok[ok] &= arm[y2[ok], x2[ok]]
        rows.append(idx[ys[ok], xs[ok]]); cols.append(idx[y2[ok], x2[ok]])
        wts.append(np.full(ok.sum(), math.hypot(dy, dx)))
    g = coo_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))),
                   shape=(len(ys), len(ys))).tocsr()
    touch = ndi.binary_dilation(rest, iterations=2) & arm
    src = idx[touch & (Y > 1700)]
    above = int((touch & (Y <= 1700)).sum())
    d = dijkstra(g, directed=False, indices=src, min_only=True)
    reach = np.isfinite(d)
    t = np.zeros(arm.shape)
    t[ys[reach], xs[reach]] = d[reach] / d[reach].max()
    return t, len(src), above, int((~reach).sum())


def field(sil, arm, rest, t, p, blur_px, margin_px):
    w = np.where(arm, t ** p, 0.0)
    _, (iy, ix) = ndi.distance_transform_edt(~arm, return_indices=True)
    w = w[iy, ix]                                                   # nearest arm pixel's weight
    w = ndi.gaussian_filter(w, blur_px / F)
    tip = (w * arm).max()
    w = w / tip
    mg = max(1, round(margin_px / F))
    arm_d, rest_d = ndi.binary_dilation(arm, iterations=mg), ndi.binary_dilation(rest, iterations=mg)
    dt = ndi.distance_transform_edt(~arm_d)
    dr = ndi.distance_transform_edt(~rest_d)
    m = np.where(arm_d, 1.0, dr / np.maximum(dt + dr, 1e-6))
    m = np.where(rest_d, 0.0, m)
    m = ndi.gaussian_filter(m, 1.5)
    m = np.where(rest, 0.0, m)
    return w * m


def limits(shape, sil):
    gx = np.gradient(shape, axis=1) / F
    gy = np.gradient(shape, axis=0) / F
    ink = ndi.binary_dilation(sil, iterations=1)
    st_ink = float(np.sqrt(gx ** 2 + gy ** 2)[ink].max())
    comp = float(np.abs(gx).max())
    return st_ink, comp


def combined_check(dx, dy, sil):
    """worst ink strain and min Jacobian determinant of the backward map p - (s*dx, dy), s = 0, +-1"""
    ink = ndi.binary_dilation(sil, iterations=1)
    worst_st, worst_det, worst_ink_det = 0.0, 9.0, 9.0
    for s in (0.0, 1.0, -1.0):
        ux, uy = s * dx, dy
        a, b = np.gradient(ux, axis=1) / F, np.gradient(ux, axis=0) / F
        c, d = np.gradient(uy, axis=1) / F, np.gradient(uy, axis=0) / F
        st = np.sqrt(a * a + b * b + c * c + d * d)
        det = (1 - a) * (1 - d) - b * c
        worst_st = max(worst_st, float(st[ink].max()))
        worst_det = min(worst_det, float(det.min()))
        worst_ink_det = min(worst_ink_det, float(det[ink].min()))
    return worst_st, worst_det, worst_ink_det


def preview(dx_full, out_png, dy_full=None):
    """K over W, still / arm pushed one way / the other (full-res warp of the art); with dy_full,
    two more tiles: dropped only, and leaning toward the centre + dropped (the "needle")."""
    k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA")).astype(np.float32)
    w = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA")).astype(np.float32)
    gy, gx = np.mgrid[0:TH, 0:TW].astype(np.float32)
    tiles = []
    states = [(0.0, 0.0), (1.0, 0.0), (-1.0, 0.0)]
    if dy_full is not None:
        states += [(0.0, 1.0), (-1.0, 1.0)]
    for sgn, dr in states:
        mx = gx - sgn * dx_full                                      # backward map, like the shader
        my = gy if dy_full is None else gy - dr * dy_full
        def warp(a):
            return cv2.remap(a, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        kw, ww = warp(k), warp(w)
        bg = np.full((TH, TW, 3), 200.0, np.float32)
        img = bg * (1 - ww[..., 3:] / 255) + ww[..., :3] * (ww[..., 3:] / 255)
        img = img * (1 - kw[..., 3:] / 255) + kw[..., :3] * (kw[..., 3:] / 255)
        tiles.append(img[:, 2900:5040])
    strip = np.concatenate([np.concatenate([t, np.full((TH, 20, 3), 255, np.float32)], 1) for t in tiles], 1)
    Image.fromarray(np.clip(strip, 0, 255).astype(np.uint8)).resize((strip.shape[1] // 3, TH // 3)).save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tip", type=float, default=150.0)
    ap.add_argument("--drop", type=float, default=120.0, help="tip drop in px when the cursor is well below it")
    ap.add_argument("--dry", action="store_true", help="previews only, do not install")
    a = ap.parse_args()

    sil, arm, rest, Y = arm_masks()
    t, nsrc, above, unreached = geodesic_t(arm, rest, Y)
    print(f"arm cells {int(arm.sum())}, attachment cells {nsrc}, contacts above y 1700 {above}, unreached {unreached}")
    spike_tip = arm & (t > 0.98)

    results = []
    for p in (1.0, 1.4, 1.8, 2.4):
        for blur in (40, 80, 160):
            for margin in (12, 20, 32):
                shape = field(sil, arm, rest, t, p, blur, margin)
                st_ink, comp = limits(shape, sil)
                a_max = min(INK_STRAIN / st_ink, GAP_COMPRESS / comp)
                tipdisp = a_max * float(shape[spike_tip].max())
                results.append((tipdisp, p, blur, margin, st_ink, comp, shape))
                print(f"p {p} blur {blur:3d} margin {margin}: tip up to {tipdisp:6.1f} px "
                      f"(ink strain/px {st_ink:.5f}, compression/px {comp:.5f})")
    ok = [r for r in results if r[0] >= a.tip]
    if ok:      # reaches the target: take the one with the least ink strain at the target
        best = min(ok, key=lambda r: r[4] * a.tip / float(r[6][spike_tip].max()))
        A = a.tip / float(best[6][spike_tip].max())
    else:
        best = max(results, key=lambda r: r[0])
        A = best[0] / float(best[6][spike_tip].max())
    tipdisp, p, blur, margin, st_ink, comp, shape = best
    dx = A * shape
    print(f"chosen p {p}, blur {blur}, margin {margin}: tip {A * float(shape[spike_tip].max()):.1f} px, "
          f"ink strain {A * st_ink:.3f}, max |d(dx)/dx| {A * comp:.3f}, head/body max {float(dx[rest].max()):.2f} px")

    tip_px = A * float(shape[spike_tip].max())
    ratio = a.drop / tip_px
    while True:                                  # the drop is the same shape: dy = ratio * dx
        st, det, ink_det = combined_check(dx, ratio * dx, sil)
        if (st <= INK_STRAIN and det >= MIN_DET) or ratio <= 0:
            break
        ratio = max(0.0, ratio - 0.02)
    gy_, gx_ = np.nonzero(spike_tip)
    print(f"drop: tip {ratio * tip_px:.1f} px (asked {a.drop:g}), worst ink strain {st:.3f}, min det {det:.3f} (on ink {ink_det:.3f}); "
          f"tip at x {(gx_.mean() + 0.5) * F:.0f}, y {(gy_.min() + 0.5) * F:.0f} (full-layer px)")

    dxm = np.asarray(Image.fromarray(dx.astype(np.float32), "F").resize((MW, MH), Image.BILINEAR))
    amp2 = float(np.abs(dxm).max()) / TW * 1.02
    strength = math.ceil(math.sqrt(amp2) * 1000) / 1000
    fx = np.clip(dxm / (strength ** 2 * TW), -1, 1)
    q = np.round(Q0 + fx * Q0).astype(np.int32)
    pix = np.dstack([q >> 8, q & 255]).astype(np.uint8)
    OUT.mkdir(parents=True, exist_ok=True)
    dx_full = np.asarray(Image.fromarray(dxm, "F").resize((TW, TH), Image.BILINEAR))
    preview(dx_full, OUT / "arm_follow_preview.png", ratio * dx_full * (1 if ratio else 0))
    Image.fromarray((np.clip(np.abs(dxm) / max(float(np.abs(dxm).max()), 1e-6), 0, 1) * 255).astype(np.uint8)).save(
        OUT / "arm_follow_magnitude.png")
    report = {"tip_px": round(A * float(shape[spike_tip].max()), 1), "profile_power": p, "blur_px": blur,
              "margin_px": margin, "ink_strain": round(A * st_ink, 3), "max_compression": round(A * comp, 3),
              "followstrength": strength, "drop_px": round(ratio * tip_px, 1), "followdrop": round(ratio, 4),
              "drop_ink_strain": round(st, 3), "drop_min_det": round(det, 3)}
    (OUT / "report.json").write_text(json.dumps(report, indent=1))
    print(f"followstrength {strength}; preview {OUT / 'arm_follow_preview.png'}")
    if a.dry:
        return
    tex_io.write_raw_tex(SRC / "materials" / f"{TEX}.tex", pix)
    scene_path = SRC / "scene.json"
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    n = 0
    for o in scene["objects"]:
        for e in o.get("effects", []):
            if e.get("name") == "Rig: Tail":
                ps = e["passes"][0]
                ps["textures"][3] = TEX
                ps["constantshadervalues"]["followstrength"] = strength
                ps["constantshadervalues"]["followdrop"] = round(ratio, 4)   # read by optimize_creature.py
                n += 1
    scene_path.write_text(json.dumps(scene, indent="\t", ensure_ascii=False), encoding="utf-8")
    print(f"installed in the optimiser source: {n} Rig: Tail effects -> {TEX}, followstrength {strength}, followdrop {ratio:.4f}")


if __name__ == "__main__":
    main()
