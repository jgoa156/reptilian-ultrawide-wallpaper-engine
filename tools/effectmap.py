import json, sys, math, os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
scene_path, maskdir, art_path, out = sys.argv[1:5]
W, H = 5040, 2160; ASP = W / H
X0, X1 = 3500, 5040            # crop of the art region
scene = json.load(open(scene_path, encoding='utf-8'))
K = next(o for o in scene['objects'] if o['name'] == 'K')
art = Image.open(art_path).convert('RGBA')
base = Image.new('RGBA', art.size, (255, 255, 255, 255)); base.alpha_composite(art)
base = Image.blend(base.convert('RGB'), Image.new('RGB', art.size, 'white'), 0.55).convert('RGBA')
palette = [(230,25,75),(60,180,75),(0,130,200),(245,130,48),(145,30,180),(70,240,240),(240,50,230),(128,128,0),(0,0,128),(170,110,40),(0,128,128),(128,0,0),(255,180,0),(90,90,90),(0,200,120),(200,0,90),(60,60,255),(150,200,0),(255,100,100),(0,90,60),(120,60,200),(200,120,0)]
lab = ImageDraw.Draw(base)
try: font = ImageFont.truetype('arial.ttf', 26)
except Exception: font = ImageFont.load_default()
legend = []
def P(u, v): return (u * W, v * H)
for i, e in enumerate(K['effects']):
    col = palette[i % len(palette)]
    kind = e['file'].split('/')[-2]
    name = e.get('name') or ''
    p = e['passes'][0]; c = p.get('constantshadervalues', {})
    tag = f'{i:02d}'
    legend.append((tag, kind, name, col))
    texs = p.get('textures') or []
    masks = [t for t in texs if t]
    for t in masks:
        m = Image.open(os.path.join(maskdir, t.split('/')[-1] + '.png'))
        if m.mode == 'RGB':   # shake flow map: show magnitude of deviation from neutral
            a = np.array(m).astype(np.float32)[..., :2] - 127
            mag = np.clip(np.hypot(a[..., 0], a[..., 1]) * 2, 0, 255).astype(np.uint8)
            m = Image.fromarray(mag)
        m = m.convert('L').resize((W, H))
        a = (np.array(m).astype(np.float32) * 0.45).astype(np.uint8)
        layer = Image.new('RGBA', (W, H), col + (0,)); layer.putalpha(Image.fromarray(a))
        base.alpha_composite(layer)
        ys, xs = np.nonzero(np.array(m) > 30)
        if len(xs): lab.text((int(np.median(xs)), int(np.median(ys))), tag, fill=col + (255,), font=font, stroke_width=3, stroke_fill='white')
    if kind in ('spin', 'twirl') or 'lens' in kind:
        cu, cv = map(float, c.get('center', '0.5 0.5').split()); r = float(c.get('size', 0.1)) * H
        ratio = float(c.get('ratio', 1)); ang = float(c.get('angle', 0))
        cx, cy = P(cu, cv)
        pts = []
        for k in range(73):
            t = k / 72 * 2 * math.pi
            x, y = r / ratio * math.cos(t), r * math.sin(t)
            x, y = x * math.cos(-ang) - y * math.sin(-ang), x * math.sin(-ang) + y * math.cos(-ang)
            pts.append((cx + x, cy + y))
        lab.line(pts, fill=col + (255,), width=4)
        lab.text((cx + r / ratio + 6, cy - 14), tag, fill=col + (255,), font=font, stroke_width=3, stroke_fill='white')
    if kind == 'swing':
        p0 = [float(x) for x in c['point0'].split()]; p1 = [float(x) for x in c['point1'].split()]
        a0, a1 = P(*p0), P(*p1)
        ax = np.array([(p1[0]-p0[0]) * ASP, p1[1]-p0[1]]); ax /= np.linalg.norm(ax); orth = np.array([-ax[1], ax[0]])
        s = float(c['size']) * H
        q0 = (a0[0] + orth[0]*s, a0[1] + orth[1]*s); q1 = (a1[0] + orth[0]*s, a1[1] + orth[1]*s)
        lab.line([a0, a1], fill=col + (255,), width=6); lab.line([a0, q0, q1, a1], fill=col + (255,), width=3)
        lab.text((a0[0] + 8, a0[1] - 34), tag, fill=col + (255,), font=font, stroke_width=3, stroke_fill='white')
img = base.crop((X0, 0, X1, H))
sheet = Image.new('RGB', (img.width + 560, H), 'white'); sheet.paste(img.convert('RGB'), (0, 0))
d = ImageDraw.Draw(sheet)
for j, (tag, kind, name, col) in enumerate(legend):
    d.text((img.width + 20, 20 + j * 38), f'{tag} {kind} {name}'[:34], fill=col, font=font)
sheet.save(out); print('saved', out, sheet.size)
