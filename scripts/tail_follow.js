'use strict';

// Tail follows the mouse (horizontal axis). Bound to the "follow" value of the "Rig: Tail"
// effect on every creature layer (installed by scripts/add_tail_follow.py). Every copy runs the
// same math on the same input, so all layers stay in register.
//
// The target is the cursor's horizontal distance from the tail itself (read from layer K's live
// position, so it follows the layout script and WE's flip): REACH of the canvas width either side
// gives full deflection. An under-damped spring makes it snappy with a small overshoot; the output
// is clamped to -1..1, which keeps the shader's strain guarantee.
// User property `tailfollow` (0..100 %) scales it; 0 turns it off.

const TAIL_TX = 3680;      // tail tip, px in the full 5040-wide layer
const TEX_CX = 2520;       // full-layer px at layer K's origin (the crop centre; set by optimize_creature.py)
const REACH = 0.3;         // fraction of the canvas width for full deflection
const OMEGA = 14;          // spring stiffness (rad/s)
const ZETA = 0.55;         // damping ratio (< 1: slight overshoot)

let amount = 1;
let pos = 0, vel = 0;
let kLayer = null, tried = -1;

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

export function applyUserProperties(changed) {
	if (changed.hasOwnProperty('tailfollow')) {
		amount = clamp(Number(changed.tailfollow) / 100, 0, 1);
	}
}

function tailWorldX(w) {
	if (!kLayer && engine.runtime > tried) {
		tried = engine.runtime + 1;
		try { kLayer = thisScene.getLayer('K'); } catch (e) { kLayer = null; }
	}
	if (kLayer) {
		return kLayer.origin.x + (TAIL_TX - TEX_CX) * kLayer.scale.x;
	}
	return w * 0.72;
}

export function update(value) {
	const w = engine.canvasSize.x;
	if (!(w > 0)) {
		return value;
	}
	const target = clamp((input.cursorWorldPosition.x - tailWorldX(w)) / (REACH * w), -1, 1) * amount;
	let dt = Math.min(engine.frametime, 0.05);
	while (dt > 0) {                                   // sub-step for a stable spring
		const h = Math.min(dt, 1 / 120);
		const acc = OMEGA * OMEGA * (target - pos) - 2 * ZETA * OMEGA * vel;
		vel += acc * h;
		pos += vel * h;
		dt -= h;
	}
	return clamp(pos, -1, 1);
}
