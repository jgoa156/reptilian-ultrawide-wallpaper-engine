"""Still mock of black edge smoke over the real desktop capture (2560x1080, WE flip on: creature left).
Puffs = WE's smoke2 alpha sprite sheet (8x8 frames), normal blending, black. Smoke sits behind the
creature, the taskbar and the desktop icons."""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

CAP = r"C:\Users\rockb\AppData\Local\Temp\claude\d64e448faefced48\693b7150-23ed-4ab5-9231-0fb0cc03f6c4\scratchpad\final_live.png"
cap = np.asarray(Image.open(CAP).convert("RGB")).astype(np.float32) / 255
H, W = cap.shape[:2]
TASKBAR = 30
lum = cap.mean(2) * 255
sat = (cap.max(2) - cap.min(2)) * 255

# creature silhouette (left), filled
ink = ((lum < 150) | (lum > 238) | (sat > 35))
ink[:, 800:] = False
ink[:TASKBAR] = False
sil = ndi.binary_closing(ink, np.ones((15, 15)), border_value=0)
sil = ndi.binary_fill_holes(sil)
lab, n = ndi.label(sil)
sizes = ndi.sum(sil, lab, range(1, n + 1))
sil = lab == (1 + int(np.argmax(sizes)))
sil = ndi.binary_dilation(sil, iterations=2)
# desktop icons (right strip)
icons = (lum < 170) & (np.arange(W)[None, :] > 2400)
icons[:TASKBAR] = False
icons = ndi.binary_dilation(icons, iterations=4)
keep = sil | icons
keep[:TASKBAR] = True
keep_soft = ndi.gaussian_filter(keep.astype(np.float32), 1.0)

def cut(name, ch):
    sh = np.load(name)[..., ch].astype(np.float32) / 255
    fr = sh.shape[0] // 8
    return [sh[r*fr:(r+1)*fr, c*fr:(c+1)*fr] for r in range(8) for c in range(8)]
puffs = cut("smoke2.npy", 1)
wisps = [f / max(f.max(), 1e-3) for f in cut("fog2.npy", 1) if f.max() > 0.2]

WISP = 0.4
def puff_layer(rng, n, side, opacity, reach=0.12, top=0.62, xpow=1.6):
    acc = np.ones((H, W), np.float32)          # product of (1 - a)
    for _ in range(n):
        life = rng.random()                         # steady-state snapshot
        x0 = rng.random() ** xpow * reach * W        # distance from the edge at birth
        drift = rng.normal(0.25, 0.25) * reach * W  # leans inward as it rises
        rise = life * top * H * rng.uniform(0.85, 1.15)
        dx = x0 + drift * life
        y = H + 60 - rise                           # births just below the bottom edge
        x = dx if side == "L" else W - dx
        size = (150 + 420 * life) * rng.uniform(0.8, 1.25)
        a = opacity * min(life / 0.15, 1) * (1 - life) ** 1.3
        a *= max(0.0, 1 - dx / (reach * W * 1.6))   # thinner away from the edge
        if a <= 0.003:
            continue
        wisp = rng.random() < WISP
        f = wisps[rng.integers(len(wisps))] if wisp else puffs[rng.integers(64)]
        if wisp: size *= 1.3
        im = Image.fromarray((f * 255).astype(np.uint8)).rotate(rng.uniform(0, 360), Image.BILINEAR)
        s = int(size); im = im.resize((s, s), Image.BILINEAR)
        if rng.random() < 0.5: im = im.transpose(Image.FLIP_LEFT_RIGHT)
        p = np.asarray(im, np.float32) / 255 * a
        x1, y1 = int(x - s / 2), int(y - s / 2)
        xa, ya, xb, yb = max(x1, 0), max(y1, 0), min(x1 + s, W), min(y1 + s, H)
        if xa >= xb or ya >= yb: continue
        acc[ya:yb, xa:xb] *= 1 - p[ya-y1:yb-y1, xa-x1:xb-x1]
    return 1 - acc

def render(seed, n, opacity, out):
    rng = np.random.default_rng(seed)
    a = 1 - (1 - puff_layer(rng, n, "L", opacity, reach=0.36, xpow=0.7)) * (1 - puff_layer(rng, n, "R", opacity, reach=0.10))
    a *= 1 - keep_soft
    col = np.array([0.03, 0.03, 0.035], np.float32)
    o = cap * (1 - a[..., None]) + col * a[..., None]
    Image.fromarray((np.clip(o, 0, 1) * 255 + 0.5).astype(np.uint8)).save(out)
    print(out, "max alpha", round(float(a.max()), 3), "mean alpha in edge strips",
          round(float(a[:, :300].mean()), 3), round(float(a[:, -300:].mean()), 3))

render(7, 110, 0.10, "smoke_mock_soft.png")
render(7, 150, 0.17, "smoke_mock_heavy.png")
Image.fromarray(sil.astype(np.uint8) * 255).save("smoke_keep_mask.png")
