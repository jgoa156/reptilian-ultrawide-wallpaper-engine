'use strict';

// Arm follows the mouse. Bound to the "Rig: Tail" follow values on every creature layer: AXIS 0
// drives "follow" (lean, from the cursor's horizontal distance to the tip), AXIS 1 drives
// "followdown" (the arm lowers while the cursor is below the tip, so it can point at the
// mandala's centre like a record needle). optimize_creature.py installs both copies. Every copy
// runs the same math on the same input, so all layers stay in register.
//
// The tip's position is read from layer K's live position, so it follows the layout script and
// WE's flip. REACH of the canvas width either side gives full lean; REACH_Y of the canvas height
// below the tip gives full drop. An under-damped spring makes it snappy with a small overshoot;
// the output is clamped (lean -1..1, drop 0..1), which keeps the shader's strain guarantee.
// User property `tailfollow` (0..100 %) scales both; 0 turns it off.

const AXIS = 0;            // 0: lean (follow), 1: drop (followdown)
const TAIL_TX = 3680;      // tail tip, px in the full 5040x2160 layer
const TAIL_TY = 382;
const TEX_CX = 2520;       // full-layer px at layer K's origin (the crop centre; set by optimize_creature.py)
const TEX_CY = 1080;
const REACH = 0.3;         // fraction of the canvas width for full lean
const REACH_Y = 0.25;      // fraction of the canvas height below the tip for full drop
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

function findK() {
	if (!kLayer && engine.runtime > tried) {
		tried = engine.runtime + 1;
		try { kLayer = thisScene.getLayer('K'); } catch (e) { kLayer = null; }
	}
	return kLayer;
}

function target(w, h) {
	const k = findK();
	if (AXIS === 0) {
		const tipX = k ? k.origin.x + (TAIL_TX - TEX_CX) * k.scale.x : w * 0.72;
		return clamp((input.cursorWorldPosition.x - tipX) / (REACH * w), -1, 1) * amount;
	}
	// scene coordinates are Y up, the texture's rows go down
	const tipY = k ? k.origin.y - (TAIL_TY - TEX_CY) * k.scale.y : h * 0.74;
	return clamp((tipY - input.cursorWorldPosition.y) / (REACH_Y * h), 0, 1) * amount;
}

export function update(value) {
	const w = engine.canvasSize.x, h = engine.canvasSize.y;
	if (!(w > 0) || !(h > 0)) {
		return value;
	}
	const goal = target(w, h);
	let dt = Math.min(engine.frametime, 0.05);
	while (dt > 0) {                                   // sub-step for a stable spring
		const s = Math.min(dt, 1 / 120);
		const acc = OMEGA * OMEGA * (goal - pos) - 2 * ZETA * OMEGA * vel;
		vel += acc * s;
		pos += vel * s;
		dt -= s;
	}
	return AXIS === 0 ? clamp(pos, -1, 1) : clamp(pos, 0, 1);
}
