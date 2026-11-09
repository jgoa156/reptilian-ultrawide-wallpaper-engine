"""Arm reach: the arm swings from its junction toward the mandala (hinge, the bend concentrated at the
junction, the tip lagging) and the junction opens like a joint: the abdomen next to it fans out
angularly so the arm stays attached. No stretch along the arm: it keeps its length and drawing.

The arm is a 32-segment skeleton of equal segment length from where it leaves the coil (BASE, the
joint J) to the spike tip. A pose a in 0..1 turns every segment by a * HINGE * (1 - TAPER * i / (n - 1))
around the fixed base, so the length never changes. A pixel q maps to the arm through its (s, n)
coordinates on the posed skeleton: segment i, parameter t and the offset n along the vertex normals
blended by t (continuous across joints), then back onto the rest skeleton at the same (s, n).

Joint fan: the rest of the layer turns around J by a * HINGE * s(psi) * fr(r). psi is the angle from
the coil direction (away from the arm): on the arm's side of the base normal line s = 1 (it turns with
the arm's first segment, so the seam closes), across the coil/abdomen side s eases to 0 at the coil
direction (the abdomen's wedge opens on top and closes underneath, off screen); fr fades the turn out
between FAN_R1 and FAN_R2 px from J.

Pre-arm sink: the joint and the coil around it sink by a * SINK px (the arm's base with them), so the
pre-arm's arc points down and its bottom goes under the screen edge.

Both the sink and the fan only act below LINE (the user's line, 2026-11-08: from the body's lower
corner up across the U toward the arm): w = smoothstep over FADE px below it, so nothing above the
line moves; around the joint w = 1 so the arm, the fan and the rest stay in register. Rest source of
an output point: undo the sink, then the fan. Pixels in the rest arm's band (measured at that turned source)
that the posed arm no longer covers are hidden. The shader (scripts/shader/creature_warp.frag.in,
armPose/armFan) does the same per pixel; this module is the reference, and the optimiser uses it to
grow the layers' supports over every pose.

Writes rig/v7/arm_pose.json (skeletons, band half-widths) and rig/v7/arm_pose_preview.png.
Usage: python tools/arm_pose.py [--margin 70]
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "rig" / "v7"
JSON = OUT / "arm_pose.json"
NSEG = 32
TW, TH = 5040, 2160
HINGE = math.radians(-42)     # swing at the junction (negative: toward the mandala)
TAPER = 0.6                   # the tip turns (1 - TAPER) of the junction's swing
BASE_FRAC, RAMP = 0.55, 5     # the first segment turns BASE_FRAC of it, full from segment RAMP (the
                              # bend spreads over the arm's root so the joint opens less)
FAN_R1, FAN_R2 = 200.0, 560.0 # joint fan: full turn within R1 of the joint, none past R2
SINK = 70.0                   # px the joint and the pre-arm sink at full reach
SINK_X1, SINK_X2 = 4420.0, 4900.0   # full sink up to X1 (just past the joint), none past X2 (body)
LINE = ((5035.0, 2107.0), (3990.0, 1553.0))   # nothing above this line moves (texture px)
FADE = 140.0                  # px below the line over which the sink and the fan fade in
# Head side of the band (n > 0): the arm casts its shadow away from the head, so on that side the
# margin only held the head's own shadow, and hiding the rest arm erased it up to a straight cut at
# region()'s x = 3950 (user's screenshot 2026-11-09). There the band is the arm's measured ink + MARGIN_IN
# (> the ~27 px tail sway, so no sliver of the old arm is left), then the old place fades back in over
# FEATHER_IN px (hide only). The joint keeps the full band (vertices < IN_FROM[0], full limit from IN_FROM[1]).
MARGIN_IN = 30.0
FEATHER_IN = 30.0
IN_FROM = (6.0, 9.0)


def region(x, y):
    """rig2's tail region (+ the coil near the base): only these pixels belong to the arm"""
    return (x < 3950) | ((y > 1500) & (x < 4400)) | ((y > 1870) & (x < 4560))


def resample(p, n):
    seg = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    u = np.linspace(0, seg[-1], n)
    return np.c_[np.interp(u, seg, p[:, 0]), np.interp(u, seg, p[:, 1])]


def build(margin):
    d = np.load(HERE / "mock" / "arm_slide_stroke.npz")
    src, hw = d["src"], d["hw"]
    vs = resample(src, NSEG + 1)
    L = float(np.hypot(*np.diff(src, axis=0).T).sum())
    a_s = np.arctan2(np.diff(vs[:, 1]), np.diff(vs[:, 0]))
    i = np.arange(NSEG)
    a_d = a_s + HINGE * (1 - TAPER * i / (NSEG - 1)) * (BASE_FRAC + (1 - BASE_FRAC) * smooth(i / RAMP))
    # band half-width at each vertex: the widest station within half a segment, + margin (shadow)
    st = np.linspace(0, NSEG, len(hw))
    hv = np.array([hw[(st >= i - 0.5) & (st <= i + 0.5)].max() for i in range(NSEG + 1)]) + margin
    return {"nseg": NSEG, "seglen": L / NSEG, "base_src": vs[0].tolist(),
            "base_dst": (vs[0] + [0.0, SINK]).tolist(), "ang_src": a_s.tolist(), "ang_dst": a_d.tolist(),
            "hw": hv.tolist(), "margin": margin, "fan_r1": FAN_R1, "fan_r2": FAN_R2,
            "sink": SINK, "sink_x": [SINK_X1, SINK_X2], "line": [list(LINE[0]), list(LINE[1])], "fade": FADE}


def head_side_limits(P):
    """hw_in: band half-width on the head side (n > 0) per vertex = the arm's own ink there (K or W, the
    widest within a segment either way) + MARGIN_IN, never wider than hw; the full hw at the joint"""
    from PIL import Image
    al = lambda f: np.asarray(Image.open(HERE / "recovered_original" / f).convert("RGBA"))[..., 3] > 16
    ink = al("Sem título-1_Prancheta 1.png") | al("sprite bgpng_Prancheta 1.png")
    ys, xs = np.nonzero(ink[300:TH, 3300:4700])
    q = np.c_[xs + 3300.5, ys + 300.5]
    v, vn = skeleton(P, 0.0)
    i, t, n, ok = project(P, v, vn, q)
    m = ok & region(q[:, 0], q[:, 1]) & (n > 0)
    s = i + t
    inner = np.array([n[m & (np.abs(s - k) <= 0.5)].max(initial=0.0) for k in range(P["nseg"] + 1)])
    inner = np.maximum.reduce([inner, np.r_[inner[1:], 0], np.r_[0, inner[:-1]]])   # widest of the neighbours
    hw = np.array(P["hw"])
    b = smooth((np.arange(P["nseg"] + 1) - IN_FROM[0]) / (IN_FROM[1] - IN_FROM[0]))
    return (hw * (1 - b) + np.minimum(hw, inner + MARGIN_IN) * b).tolist()


def load():
    return json.loads(JSON.read_text(encoding="utf-8"))


def smooth(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def line_normal(P):
    """(point on the line, unit normal pointing below it)"""
    p1, p2 = np.array(P["line"][0]), np.array(P["line"][1])
    d = (p2 - p1) / np.linalg.norm(p2 - p1)
    n = np.array([-d[1], d[0]])
    return p1, (n if n[1] > 0 else -n)


def below(P, q):
    """weight of the sink and the fan: 0 above the line, 1 from FADE px below it"""
    p1, n = line_normal(P)
    return smooth(((q - p1) @ n) / P["fade"])


def sink(P, a, q, w):
    """undo the pre-arm sink: output points q (m, 2) -> points before the sink, at pose a"""
    g = 1 - smooth((q[:, 0] - P["sink_x"][0]) / (P["sink_x"][1] - P["sink_x"][0]))
    return q - np.c_[np.zeros(len(q)), a * P["sink"] * w * g]


def rest_src(P, a, q):
    """rest source of output points q at pose a: undo the sink, then the joint fan"""
    w = below(P, q)
    return fan(P, a, sink(P, a, q, w), w)


def fan(P, a, q, w):
    """rest source point of output points q (m, 2) at pose a: the joint fan around the base"""
    J = np.array(P["base_src"])
    turn = a * (P["ang_dst"][0] - P["ang_src"][0])                # the first segment's turn (< 0)
    ac = P["ang_src"][0] + math.pi                                 # coil direction, away from the arm
    d = q - J
    r = np.hypot(d[:, 0], d[:, 1])
    psi = (np.arctan2(d[:, 1], d[:, 0]) - ac + math.pi) % (2 * math.pi) - math.pi
    # output-space limits of the fan: the base normal line, turned with the arm
    lim = np.where(psi < 0, -math.pi / 2 + turn, math.pi / 2 + turn)
    s = smooth(psi / lim)                                         # the opening spread over the whole quarter
    fr = 1 - smooth((r - P["fan_r1"]) / (P["fan_r2"] - P["fan_r1"]))
    th = -turn * s * fr * w                                        # backward: turn the other way
    c, sn = np.cos(th), np.sin(th)
    return J + np.c_[c * d[:, 0] - sn * d[:, 1], sn * d[:, 0] + c * d[:, 1]]


def skeleton(P, a):
    """vertices (n+1, 2) and vertex normal angles (n+1) at pose a; the shader rebuilds it the same way"""
    a_s, a_d = np.array(P["ang_src"]), np.array(P["ang_dst"])
    th = a_s + a * (a_d - a_s)
    b = np.array(P["base_src"]) + a * (np.array(P["base_dst"]) - np.array(P["base_src"]))
    v = np.vstack([b, b + np.cumsum(P["seglen"] * np.c_[np.cos(th), np.sin(th)], axis=0)])
    vn = np.r_[th[0], (th[:-1] + th[1:]) / 2, th[-1]] + math.pi / 2
    return v, vn


def project(P, v, vn, q, inner="hw_in"):
    """(segment, t, n, ok) of points q (m, 2) on the skeleton (v, vn); ok = inside the band (head side:
    P[inner], "hw_in" = the narrowed material band, "hw" = the full band used to find the moved arm)"""
    m = len(q)
    best_n = np.full(m, np.inf); best_i = np.zeros(m, int); best_t = np.zeros(m)
    cr = lambda u, w: u[..., 0] * w[..., 1] - u[..., 1] * w[..., 0]
    for i in range(P["nseg"]):
        A, D = v[i], v[i + 1] - v[i]
        NA = np.array([math.cos(vn[i]), math.sin(vn[i])]); NB = np.array([math.cos(vn[i + 1]), math.sin(vn[i + 1])])
        E = NB - NA
        Q = q - A
        c2 = -cr(D, E); c1 = cr(Q, E) - cr(D, NA); c0 = cr(Q, NA)
        real = np.ones(m, bool)
        if abs(c2) < 1e-9:
            t = -c0 / np.where(np.abs(c1) < 1e-12, 1e-12, c1)
        else:
            dd = c1 * c1 - 4 * c2 * c0
            real = dd >= 0                       # no real root: q is not on this segment's normal fan
            disc = np.sqrt(np.maximum(dd, 0))
            t1, t2 = (-c1 - disc) / (2 * c2), (-c1 + disc) / (2 * c2)
            t = np.where((t1 >= 0) & (t1 <= 1), t1, t2)
        N = NA + t[:, None] * E
        n = np.einsum("ij,ij->i", Q - t[:, None] * D, N) / np.linalg.norm(N, axis=1)
        ok = real & (t >= 0) & (t <= 1) & (np.abs(n) < np.abs(best_n))
        best_n = np.where(ok, n, best_n); best_t = np.where(ok, t, best_t); best_i = np.where(ok, i, best_i)
    found = np.isfinite(best_n)
    n = np.where(found, best_n, 0.0)
    h = np.where(n > 0, half_width(P, inner, best_i, best_t), half_width(P, "hw", best_i, best_t))
    return best_i, best_t, n, found & (np.abs(n) <= h)


def half_width(P, key, i, t):
    hw = np.array(P.get(key, P["hw"]))
    return hw[i] + t * (hw[np.minimum(i + 1, P["nseg"])] - hw[i])


def hide_weight(P, a, q):
    """how much of the rest layer at output points q is hidden at pose a: 1 in the rest arm's band, then
    on the head side a fade over FEATHER_IN px (ramped in over the first 0.2 of the pose, so nothing pops)"""
    rq = rest_src(P, a, q)
    vr, vnr = skeleton(P, 0.0)
    i, t, n, ok = project(P, vr, vnr, rq)
    reg = region(rq[:, 0], rq[:, 1])
    soft = (n > 0) * (1 - smooth((n - half_width(P, "hw_in", i, t)) / P.get("feather_in", FEATHER_IN)))
    return np.where(reg, np.maximum(ok.astype(float), soft * min(1.0, a / 0.2)), 0.0)


def point_at(v, vn, i, t, n):
    A, B = v[i], v[np.minimum(i + 1, len(v) - 1)]
    th = vn[i] + t * (vn[np.minimum(i + 1, len(vn) - 1)] - vn[i])
    return A + t[:, None] * (B - A) + n[:, None] * np.c_[np.cos(th), np.sin(th)]


def pose_map(P, a, q):
    """for points q (layer px): (arm source point, arm valid, rest source point, rest hidden)"""
    vr, vnr = skeleton(P, 0.0)
    vp, vnp = skeleton(P, a)
    i, t, n, ok = project(P, vp, vnp, q, inner="hw")
    src = point_at(vr, vnr, i, t, n)
    # drawn only where arm material is read (the shader tests it after the rigs; here they are still)
    arm = ok & region(src[:, 0], src[:, 1]) & project(P, vr, vnr, src)[3]
    rq = rest_src(P, a, q)
    okr = project(P, vr, vnr, rq)[3]
    hide = okr & region(rq[:, 0], rq[:, 1])
    return src, arm, rq, hide


def sweep(P, S, steps=11):
    """for a support grid of S px cells: per pose a (steps from 0 to 1) the arm source cell and the rest
    source cell of every cell, where the arm is and where the rest shows; plus the box (full uv)
    holding every posed and rest band"""
    gh, gw = TH // S, TW // S
    gy, gx = np.mgrid[0:gh, 0:gw]
    q = np.c_[(gx.ravel() + 0.5) * S, (gy.ravel() + 0.5) * S]
    cell = lambda p: (np.clip((p[:, 1] / S).astype(int), 0, gh - 1).reshape(gh, gw),
                      np.clip((p[:, 0] / S).astype(int), 0, gw - 1).reshape(gh, gw))
    out, band = [], np.zeros(len(q), bool)
    for a in np.linspace(0, 1, steps):
        src, arm, rq, hide = pose_map(P, a, q)
        out.append((*cell(src), arm.reshape(gh, gw), *cell(rq), (~hide).reshape(gh, gw)))
        vp, vnp = skeleton(P, a)
        band |= project(P, vp, vnp, q, inner="hw")[3] | hide
    ys, xs = np.nonzero(band.reshape(gh, gw))
    pad = 3
    box = ((xs.min() - pad) * S / TW, (ys.min() - pad) * S / TH, (xs.max() + 1 + pad) * S / TW, (ys.max() + 1 + pad) * S / TH)
    return out, box


def pose_support(sweep_out, sup, arm_too=True):
    """support grid -> support grown by every pose (the fanned rest; the moved arm if arm_too)"""
    grown = sup.copy()
    for sy, sx, arm, ry, rx, rest in sweep_out:
        grown |= rest & sup[ry, rx]
        if arm_too:
            grown |= arm & sup[sy, sx]
    return grown


def glsl(P):
    """armPose(q px, qr px, a, inout rot) for the shader: q = output point, qr = its fanned rest source;
    xy = arm source px, z = arm, w = rest hidden; rot.xy = cos/sin of the turn from the posed frame
    back to the rest frame"""
    n = P["nseg"]
    f = lambda x: f"{x:.6f}"
    v2 = lambda p: f"vec2({f(p[0])}, {f(p[1])})"
    a_s, a_d, hw = P["ang_src"], P["ang_dst"], P["hw"]
    hi = P.get("hw_in", hw)
    vr, vnr = skeleton(P, 0.0)
    L = []
    L.append("vec4 armPose(vec2 q, vec2 qr, float a, inout vec4 rot)\n{")
    for i in range(n):
        L.append(f"\tfloat th{i} = {f(a_s[i])} + a * {f(a_d[i] - a_s[i])};")
    hp = f(math.pi / 2)
    L.append(f"\tvec2 N0 = vec2(cos(th0 + {hp}), sin(th0 + {hp}));")
    for i in range(1, n):
        L.append(f"\tvec2 N{i} = vec2(cos(0.5 * (th{i - 1} + th{i}) + {hp}), sin(0.5 * (th{i - 1} + th{i}) + {hp}));")
    L.append(f"\tvec2 N{n} = vec2(cos(th{n - 1} + {hp}), sin(th{n - 1} + {hp}));")
    bs, bd = P["base_src"], P["base_dst"]
    L.append(f"\tvec2 A = {v2(bs)} + a * {v2([bd[0] - bs[0], bd[1] - bs[1]])};")
    L.append("\tvec2 D = vec2(0.0, 0.0);\n\tvec3 r = vec3(0.0, 0.0, 0.0);\n\tfloat bestN = 1e9;\n\tfloat arm = 0.0;"
             "\n\tvec2 src = vec2(0.0, 0.0);\n\tfloat turn = 0.0;\n\tfloat vs = 0.0;\n\tfloat vp = 0.0;")
    for i in range(n):
        vni = f"0.5 * (th{i - 1} + th{i}) + {hp}" if i > 0 else f"th0 + {hp}"
        vnj = f"0.5 * (th{i} + th{i + 1}) + {hp}" if i < n - 1 else f"th{n - 1} + {hp}"
        RA, RD = vr[i], vr[i + 1] - vr[i]
        L.append(f"\tD = {f(P['seglen'])} * vec2(cos(th{i}), sin(th{i}));")
        L.append(f"\tr = segCoord(q, A, D, N{i}, N{i + 1}, vec4({f(hw[i])}, {f(hw[i + 1])}, {f(hw[i])}, {f(hw[i + 1])})).xyz;")
        L.append(f"\tif (r.z > 0.5 && abs(r.y) < abs(bestN))\n\t{{\n\t\tbestN = r.y;\n\t\tarm = 1.0;"
                 f"\n\t\tvs = {f(vnr[i])} + r.x * {f(vnr[i + 1] - vnr[i])};"
                 f"\n\t\tvp = ({vni}) + r.x * (({vnj}) - ({vni}));"
                 f"\n\t\tsrc = {v2(RA)} + r.x * {v2(RD)} + r.y * vec2(cos(vs), sin(vs));"
                 f"\n\t\tturn = vs - vp;\n\t}}")
        L.append("\tA += D;")
    L.append("\tif (arm > 0.5 && !armRegion(src))\n\t{\n\t\tarm = 0.0;\n\t}")
    L.append("\trot = vec4(cos(turn), sin(turn), 0.0, 0.0);\n\treturn vec4(src, arm, 0.0);\n}")
    # the rest arm's material: is texture point x (px) the arm (in its band, head side narrowed)?
    # Called on the points the chain really samples (after the rigs: lean, sway), so the old place
    # is hidden and the moved arm drawn exactly where arm texture is read.
    L.append("\n// x = h: arm material (rest band, head side narrowed); y: the head-side fade past it\n"
             "vec2 armRestBand(vec2 x)\n{\n\tfloat hard = 0.0;\n\tfloat soft = 0.0;\n\tvec4 h = vec4(0.0, 0.0, 0.0, 0.0);"
             "\n\tif (armRegion(x))\n\t{")
    for i in range(n):
        RA, RD = vr[i], vr[i + 1] - vr[i]
        NA = [math.cos(vnr[i]), math.sin(vnr[i])]; NB = [math.cos(vnr[i + 1]), math.sin(vnr[i + 1])]
        L.append(f"\t\th = segCoord(x, {v2(RA)}, {v2(RD)}, {v2(NA)}, {v2(NB)}, vec4({f(hw[i])}, {f(hw[i + 1])}, {f(hi[i])}, {f(hi[i + 1])}));")
        L.append("\t\thard = max(hard, h.z);\n\t\tsoft = max(soft, h.w);")
    L.append("\t}\n\treturn vec2(hard, soft);\n}")
    return "\n".join(L)


def consts(P):
    """#defines for armSink / armFan (all layouts)"""
    J = P["base_src"]
    return (f"\n#define ARM_J vec2({J[0]:.6f}, {J[1]:.6f})"
            f"\n#define ARM_TURN {P['ang_dst'][0] - P['ang_src'][0]:.6f}"
            f"\n#define ARM_COIL vec2({-math.cos(P['ang_src'][0]):.6f}, {-math.sin(P['ang_src'][0]):.6f})"
            f"\n#define ARM_FAN_R1 {P['fan_r1']:.6f}\n#define ARM_FAN_R2 {P['fan_r2']:.6f}"
            f"\n#define ARM_SINK {P['sink']:.6f}"
            f"\n#define ARM_SINK_X vec2({P['sink_x'][0]:.6f}, {P['sink_x'][1]:.6f})"
            f"\n#define ARM_LINE_P vec2({line_normal(P)[0][0]:.6f}, {line_normal(P)[0][1]:.6f})"
            f"\n#define ARM_LINE_N vec2({line_normal(P)[1][0]:.6f}, {line_normal(P)[1][1]:.6f})"
            f"\n#define ARM_FADE {P['fade']:.6f}"
            f"\n#define ARM_FEATHER_IN {P.get('feather_in', FEATHER_IN):.6f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--margin", type=float, default=70)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    P = build(args.margin)
    P["hw_in"] = head_side_limits(P)
    P["feather_in"] = FEATHER_IN
    JSON.write_text(json.dumps(P, indent=1), encoding="utf-8")
    print(f"{P['nseg']} segments of {P['seglen']:.1f} px; hinge {math.degrees(HINGE):.0f} deg, fan {FAN_R1:.0f}..{FAN_R2:.0f} px; "
          f"band half-width {min(P['hw']):.0f}..{max(P['hw']):.0f} px")
    # preview: K + W composited at a = 0, 0.5, 1 with the reference map (third res)
    from PIL import Image, ImageOps
    k = np.asarray(Image.open(HERE / "recovered_original" / "Sem título-1_Prancheta 1.png").convert("RGBA")).astype(np.float32)
    w = np.asarray(Image.open(HERE / "recovered_original" / "sprite bgpng_Prancheta 1.png").convert("RGBA")).astype(np.float32)
    S = 3
    x0, y0 = 2100, 300
    gy, gx = np.mgrid[y0 // S:TH // S, x0 // S:TW // S]
    q = np.c_[(gx.ravel() + 0.5) * S, (gy.ravel() + 0.5) * S]

    def sample(img, p):
        xi = np.clip(p[:, 0].astype(int), 0, TW - 1); yi = np.clip(p[:, 1].astype(int), 0, TH - 1)
        out = img[yi, xi].copy()
        out[(p[:, 0] < 0) | (p[:, 0] >= TW) | (p[:, 1] < 0) | (p[:, 1] >= TH)] = 0
        return out

    tiles = []
    for a in (0.0, 0.5, 1.0):
        src, arm, rq, hide = pose_map(P, a, q)
        hw_ = hide_weight(P, a, q)
        col = np.full((len(q), 3), 222.0)
        for img in (w, k):
            rest = sample(img, rq); rest[:, 3] *= 1 - hw_
            armc = sample(img, src); armc[~arm] = 0
            for c in (rest, armc):
                al = c[:, 3:4] / 255
                col = col * (1 - al) + c[:, :3] * al
        tiles.append(ImageOps.mirror(Image.fromarray(col.reshape(gy.shape[0], gy.shape[1], 3).astype(np.uint8))))
    tw, th_ = tiles[0].size
    sheet = Image.new("RGB", (tw * 3 + 20, th_), (40, 40, 40))
    for j, t_ in enumerate(tiles):
        sheet.paste(t_, (j * (tw + 10), 0))
    sheet.save(OUT / "arm_pose_preview.png")
    print("preview: rig/v7/arm_pose_preview.png (pose 0, 0.5, 1)")


if __name__ == "__main__":
    main()
