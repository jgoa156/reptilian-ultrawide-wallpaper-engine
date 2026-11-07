import fs from 'fs';
class Vec3 { constructor(x, y, z) { this.x = x; this.y = y ?? x; this.z = z ?? x; } copy() { return new Vec3(this.x, this.y, this.z); } }
globalThis.Vec3 = Vec3;
const props = {};
globalThis.createScriptProperties = () => { const b = { addCombo(o) { props[o.name] = o.value ?? o.options[0].value; return b; }, addSlider(o) { props[o.name] = o.value; return b; }, finish() { return props; } }; return b; };
const scene = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const layers = {};
for (const o of scene.objects) { const v = (s, d) => s ? s.split(' ').map(Number) : d; const [x, y, z] = v(o.origin); const [sx, sy, sz] = v(o.scale, [1, 1, 1]); layers[o.name] = { name: o.name, origin: new Vec3(x, y, z), scale: new Vec3(sx, sy, sz) }; }
const fresh = () => Object.fromEntries(Object.entries(layers).map(([k, l]) => [k, { name: k, origin: l.origin.copy(), scale: l.scale.copy() }]));
globalThis.engine = { canvasSize: { x: 5120, y: 2160 }, screenResolution: { x: 0, y: 0 } };
let current; globalThis.thisScene = { getLayer: n => current[n] };
const mod = await import('./layout.mjs');
const ART = { left: 3728, right: 5120, bottom: 2, top: 2082 };   // K-layer art bounds in authored coords
const res = [[1920,1080],[2560,1440],[3840,2160],[2560,1080],[3440,1440],[5120,2160],[3840,1080],[5120,1440],[1280,1024],[1024,768],[1080,1920],[1440,3200],[7680,2160]];
const out = [];
for (const side of ['right', 'left']) for (const [w, h] of res) {
  current = fresh(); engine.screenResolution = { x: w, y: h };
  mod.init(true); mod.applyUserProperties({ side });
  // also exercise a resize from a different screen back to this one
  mod.resizeScreen({ x: 1000, y: 1000 }); mod.resizeScreen({ x: w, y: h });
  const K = current.K, b = layers.K, rx = K.scale.x / b.scale.x, ry = K.scale.y / b.scale.y;
  const map = (px, py) => [K.origin.x + (px - b.origin.x) * rx, K.origin.y + (py - b.origin.y) * ry];
  const [ax0, ay0] = map(ART.left, ART.bottom), [ax1, ay1] = map(ART.right, ART.top);
  // visible canvas region under centred fill
  const cw = 5120, ch = 2160, a = w / h; let v;
  if (a < cw / ch) { const vw = ch * a; v = { x: (cw - vw) / 2, y: 0, w: vw, h: ch }; } else { const vh = cw / a; v = { x: 0, y: (ch - vh) / 2, w: cw, h: vh }; }
  const k = w / v.w, sx = X => (X - v.x) * k, sy = Y => (Y - v.y) * k;
  const xs = [sx(ax0), sx(ax1)].sort((p, q) => p - q), bottom = Math.min(sy(ay0), sy(ay1)), top = Math.max(sy(ay0), sy(ay1));
  const r = { side, res: `${w}x${h}`, heightPct: +(100 * (top - bottom) / h).toFixed(3), bottomPx: +bottom.toFixed(2), leftPx: +xs[0].toFixed(1), rightPx: +xs[1].toFixed(1), widthPct: +(100 * (xs[1] - xs[0]) / w).toFixed(1),
    bgCenter: [+sx(current.BG.origin.x).toFixed(1), +sy(current.BG.origin.y).toFixed(1)], layers: Object.fromEntries(Object.entries(current).map(([n, l]) => [n, [l.origin.x, l.origin.y, l.scale.x, l.scale.y]])) };
  r.ok = Math.abs(r.heightPct - 90) < 0.01 && Math.abs(r.bottomPx) < 0.01 && (side === 'right' ? Math.abs(r.rightPx - w) < 0.01 : Math.abs(r.leftPx) < 0.01);
  out.push(r);
}
fs.writeFileSync(process.argv[3], JSON.stringify(out));
for (const r of out) console.log(`${r.ok ? 'OK  ' : 'FAIL'} ${r.side.padEnd(5)} ${r.res.padEnd(10)} height ${r.heightPct}%  bottom ${r.bottomPx}px  x ${r.leftPx}..${r.rightPx} (${r.widthPct}% wide)  bg@${r.bgCenter}`);
