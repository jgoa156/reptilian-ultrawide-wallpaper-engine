import sys, json, math, numpy as np, cv2
from PIL import Image
S, R, NOISE = sys.argv[1:4]
FOL = sys.argv[4] if len(sys.argv) > 4 else 'v2/fix_foliagesway_mask_135029a1.png'
FSTR = float(sys.argv[5]) if len(sys.argv) > 5 else 0.21
TW, TH = 5040, 2160; MW, MH = 1720, 720; SX, SY = TW / MW, TH / MH
noise = np.array(Image.open(NOISE).convert('RGB')).astype(np.float32) / 255; nh, nw = noise.shape[:2]
gy, gx = np.mgrid[0:MH, 0:MW].astype(np.float32)
u, v = (gx + 0.5) / MW, (gy + 0.5) / MH
rep = json.load(open(f'{S}/rig2_report.json'))
def flow(png, strength):
    fl = (np.array(Image.open(png)).astype(np.float32)[..., :2] / 255 - 0.498) * 2
    return fl[..., 0] * strength**2 * TW, fl[..., 1] * strength**2 * TH
def tmap(png): return np.array(Image.open(png)).astype(np.float32) / 255 * 2 * math.pi
bal = flow(f'{R}/v2/fix_shake_mask_647b9b30.png', rep['author']['Balance (General)']['strength'])
app = flow(f'{R}/v2/rig2_appendages_flow.png', rep['rig']['appendages']['strength']); app_t = tmap(f'{R}/v2/rig2_appendages_time.png')
body = flow(f'{R}/v2/rig2_body_flow.png', rep['rig']['body']['strength']); body_t = tmap(f'{R}/v2/rig2_body_time.png')
fm = np.array(Image.open(f'{R}/{FOL}')).astype(np.float32) / 255
def rot(x, y, a): return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
def foliage(t, mask, strength=FSTR, ratio=2.25, scale=0.22, direction=2.8540409, speed=5, phase=0.5, power=1.37):
    asp = TW / TH * ratio
    nzx, nzy = rot(1 / asp, asp, direction)
    px, py = rot(u, v, direction)
    ng = noise[..., 1]
    ns = cv2.remap(ng, (u * scale * nw - 0.5).astype(np.float32), (v * scale * nh - 0.5).astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
    ph = (ns * 2 * math.pi + px * 10 + py * 5) * phase
    a = strength**2 * 0.005 * mask
    k1 = [1, -0.16161616, 0.0083333, -0.00019841]; k2 = [-0.5, 0.041666666, -0.0013888889, 0.000024801587]
    sp = lambda x: np.sign(np.sin(x)) * np.abs(np.sin(x)) ** power
    sx = sum(sp(ph + speed * t * k) for k in k1); sy = sum(sp(0.4 + ph + speed * t * k) for k in k2)
    return nzx * sx * a * TW, nzy * sy * a * TH
def shake(f, tm, speed, t, left=False):
    off = np.sin(np.mod((speed * t + tm) / (2 * math.pi), 1) * 2 * math.pi) * 0.498 + 0.5
    off = off if left else off * 2 - 1
    return f[0] * off, f[1] * off
def strain(dx, dy):
    g = lambda a, ax, s: np.gradient(a, axis=ax) / s
    return np.sqrt(g(dx, 1, SX)**2 + g(dx, 0, SY)**2 + g(dy, 1, SX)**2 + g(dy, 0, SY)**2)
worst = {k: np.zeros((MH, MW), np.float32) for k in ['foliage', 'balance', 'appendages', 'body', 'total']}
for t in np.linspace(0, 20, 120):
    parts = {'foliage': foliage(t, fm), 'balance': shake(bal, 0, 3.18, t, left=True),
             'appendages': shake(app, app_t, 1.3, t), 'body': shake(body, body_t, 0.9, t)}
    tx = sum(p[0] for p in parts.values()); ty = sum(p[1] for p in parts.values())
    for k, p in parts.items(): worst[k] = np.maximum(worst[k], strain(*p))
    worst['total'] = np.maximum(worst['total'], strain(tx, ty))
hair = (v < 0.3) & (u > 0.80)
for k, w in worst.items():
    ys, xs = np.unravel_index(np.argmax(np.where(hair, w, 0)), w.shape)
    print(f'{k:10s} worst strain in hair {np.where(hair, w, 0).max():.2f} at tex ({int(xs*SX)},{int(ys*SY)})')
np.save(f'{S}/hair_worst.npy', worst['total'])
