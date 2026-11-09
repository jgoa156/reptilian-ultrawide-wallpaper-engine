'use strict';

// Creature driver: the music and cursor values of the "living creature" effects, worked out ONCE per
// frame and handed to every creature layer's "Creature warp" pass. optimize_creature.py binds this
// script to the "bass" value of K's second pass (Creature warp (KPOST)); it returns that layer's bass
// and sets the rest with setMaterialProperty on every pass (as the mandala controller does), so all
// layers read the same numbers in the same frame.
//
//  bass   0..1  low bands, snaps up and eases down (belly heave)
//  loud   0..1  whole-spectrum level, slow (hair bristle, gill flare, ripple strength)
//  beat   0..1  bass onset pulse, decays in ~0.25 s (colour split)
//  jaw    0..1  snaps open on strong bass hits and springs shut with a small bounce
//  blink  0..1  the big eyes blink every 2.5..7 s (sometimes twice)
//  lookx/looky  -1..1 the eyes look toward the cursor (layer uv axes: follows WE's flip)
// Strong hits also set shared.creaturePuff (engine.runtime of the hit) for the mouth smoke's rate
// script (scripts/mouth_smoke.js).
// User property `creaturemusic` (on/off) silences the music-driven parts; `tailfollow` (0..100 %)
// also scales how far the eyes follow the cursor.

const TEX_CX = 2520;       // full-layer px at layer K's origin (the crop centre; set by optimize_creature.py)
const TEX_CY = 1080;
const EYE_TX = 4230, EYE_TY = 790;   // between the big eyes, full-layer px
const LOOK_REACH = 0.35;   // cursor this far (x canvas width) from the eyes: full look
const LAYERS = [['Shadow', 'RIG'], ['W', 'RIG'], ['C', 'CSTACK'], ['M', 'CSTACK'], ['C2', 'CSTACK'],
	['CB_Chest', 'CBCHEST'], ['CB_Tail4', 'CBTAIL'], ['CB_Tail3', 'CBTAIL'], ['CB_Tail2', 'CBTAIL2'],
	['CB_Tail1', 'CBTAIL'], ['K', 'KPRE'], ['K', 'KPOST']];
const SELF = 'KPOST';      // the pass this script is bound to (its "bass" comes from the return value)

const audio = engine.registerAudioBuffers(engine.AUDIO_RESOLUTION_16);

let musicOn = true, lookAmt = 1;
export function applyUserProperties(changed) {
	if (changed.creaturemusic !== undefined) musicOn = !!changed.creaturemusic;
	if (changed.tailfollow !== undefined) lookAmt = Math.max(0, Math.min(1, Number(changed.tailfollow) / 100));
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function smooth01(a, b, x) { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }

let fxs = null, kLayer = null, tried = -1;
function findEffects() {
	if (fxs && kLayer) return;
	if (engine.runtime <= tried) return;
	tried = engine.runtime + 1;                       // retry once a second until every layer exists
	const found = [];
	let k = null;
	for (const [name, layout] of LAYERS) {
		let layer = null, fx = null;
		try { layer = thisScene.getLayer(name); } catch (e) { layer = null; }
		if (!layer) return;
		try { fx = layer.getEffect('Creature warp (' + layout + ')'); } catch (e) { fx = null; }
		if (!fx) return;
		if (name === 'K') k = layer;
		found.push([fx, layout === SELF]);
	}
	fxs = found;
	kLayer = k;
}

function spring(s, goal, omega, zeta, dt) {
	while (dt > 0) {
		const h = Math.min(dt, 1 / 120);
		s.v += (omega * omega * (goal - s.x) - 2 * zeta * omega * s.v) * h;
		s.x += s.v * h;
		dt -= h;
	}
}

let bassLv = 0, loud = 0, fast = 0, slow = 0, favg = 0.02, beat = 0, beatCool = 0, jawCool = 0, jawHold = 0;
const jaw = { x: 0, v: 0 }, lx = { x: 0, v: 0 }, ly = { x: 0, v: 0 };
let blinkAt = 3, blinkT = -1, blinkTwice = false;

function blinkCurve(t) {                              // 0 open .. 1 shut; close 70 ms, hold 40, open 120
	if (t < 0) return 0;
	if (t < 0.07) return t / 0.07;
	if (t < 0.11) return 1;
	if (t < 0.23) return 1 - (t - 0.11) / 0.12;
	return 0;
}

export function update(value) {
	const dt = Math.min(engine.frametime, 0.05);
	if (!(dt > 0)) return value;
	findEffects();
	const now = engine.runtime;
	const k30 = Math.min(dt * 30, 4);
	const rate = (a) => 1 - Math.pow(1 - a, k30);

	// ---- music
	let all = 0;
	for (let i = 0; i < 16; i++) all += audio.average[i];
	all /= 16;
	const braw = (audio.left[0] + audio.left[1] + audio.right[0] + audio.right[1]) * 0.25;
	const bv = musicOn ? smooth01(0.2, 1.1, braw) : 0;
	bassLv += (bv - bassLv) * (bv > bassLv ? rate(0.6) : rate(0.15));
	const lv = musicOn ? smooth01(0.03, 0.22, all) : 0;
	loud += (lv - loud) * (lv > loud ? rate(0.08) : rate(0.03));
	// bass onsets: fast envelope over a slow one, normalised by how much this song usually moves
	let bass4 = 0;
	for (let i = 0; i < 4; i++) bass4 += audio.average[i];
	bass4 /= 4;
	fast += (bass4 - fast) * rate(0.55);
	slow += (bass4 - slow) * rate(0.06);
	const flux = Math.max(0, fast - slow);
	const en = flux / (favg * 1.5 + 0.004);
	favg += (flux - favg) * rate(0.02);
	beat *= Math.pow(0.82, k30);
	if (musicOn && en > 1 && bass4 > 0.05 && now >= beatCool) {
		beat = Math.max(beat, Math.min(1, 0.35 + 0.35 * en));
		beatCool = now + 0.18;
	}
	if (musicOn && en > 1.6 && bassLv > 0.45 && now >= jawCool) {
		jawHold = now + 0.07;                         // pull open for 70 ms, then the spring shuts it
		jawCool = now + 0.35;
		if (en > 2.2 && bassLv > 0.6) shared.creaturePuff = now;
	}
	spring(jaw, now < jawHold ? 1 : 0, 26, 0.45, dt);
	const jawV = clamp(jaw.x, 0, 1.15);

	// ---- blink
	if (blinkT < 0 && now >= blinkAt) { blinkT = 0; blinkTwice = Math.random() < 0.2; }
	let blink = 0;
	if (blinkT >= 0) {
		blinkT += dt;
		blink = blinkCurve(blinkT) + (blinkTwice ? blinkCurve(blinkT - 0.3) : 0);
		if (blinkT > (blinkTwice ? 0.55 : 0.25)) { blinkT = -1; blinkAt = now + 2.5 + Math.random() * 4.5; }
	}

	// ---- look (world -> layer uv axes: K's scale carries WE's flip)
	const w = engine.canvasSize.x;
	const cur = input.cursorWorldPosition;
	let gx = 0, gy = 0;
	if (kLayer && w > 0) {
		const ex = kLayer.origin.x + (EYE_TX - TEX_CX) * kLayer.scale.x;
		const ey = kLayer.origin.y + (TEX_CY - EYE_TY) * Math.abs(kLayer.scale.y);
		gx = (cur.x - ex) / (LOOK_REACH * w) * Math.sign(kLayer.scale.x || 1);
		gy = -(cur.y - ey) / (LOOK_REACH * w);
		const L = Math.hypot(gx, gy);
		if (L > 1) { gx /= L; gy /= L; }
		gx *= lookAmt; gy *= lookAmt;
	}
	spring(lx, gx, 9, 0.8, dt);
	spring(ly, gy, 9, 0.8, dt);

	if (fxs) {
		const vals = [['loud', loud], ['beat', beat], ['jaw', jawV], ['blink', clamp(blink, 0, 1)],
			['lookx', clamp(lx.x, -1, 1)], ['looky', clamp(ly.x, -1, 1)]];
		for (const [fx, self] of fxs) {
			try {
				if (!self) fx.setMaterialProperty('bass', bassLv);
				for (const [n, v] of vals) fx.setMaterialProperty(n, v);
			} catch (e) { /* older WE: shader defaults */ }
		}
	}
	return bassLv;
}
