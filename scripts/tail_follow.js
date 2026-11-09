'use strict';

// Arm follows the mouse. Bound to the creature layers' "Creature warp" values; optimize_creature.py
// installs two copies: OUT 0 drives "follow" (the arm leans toward the cursor), OUT 1 drives
// "armpose" (the reach: when the cursor travels far sideways toward the mandala the whole arm glides
// down along the track from tools/arm_pose.py, the coil junction bending with it, and the lean fades
// out). Only the cursor's horizontal position counts. Every copy runs the same
// math on the same input, so all layers stay in register.
//
// Lean: the tip's position is read from layer K's live position (follows the layout script and WE's
// flip); REACH of the canvas width either side gives full lean, an under-damped spring makes it
// snappy. Reach: past P_START of the canvas width from the tip toward the mandala (layer MandalaK, so
// it follows WE's flip) the arm starts to reach, fully at P_FULL; a slower, nearly critically damped
// spring makes it glide.
// User property `tailfollow` (0..100 %) scales both; 0 turns them off.

const OUT = 0;             // 0: lean (follow), 1: needle pose (armpose)
const TAIL_TX = 3680;      // tail tip, px in the full 5040x2160 layer
const TEX_CX = 2520;       // full-layer px at layer K's origin (the crop centre; set by optimize_creature.py)
const REACH = 0.3;         // fraction of the canvas width for full lean
const OMEGA = 14;          // lean spring stiffness (rad/s)
const ZETA = 0.55;         // lean damping ratio (< 1: slight overshoot)
const P_START = 0.08;      // cursor this far past the tip toward the mandala (x canvas width): reach starts
const P_FULL = 0.32;       // ... this far: full reach
const P_OMEGA = 5;         // needle spring stiffness (rad/s)
const P_ZETA = 0.9;

let amount = 1;
let pos = 0, vel = 0, ppos = 0, pvel = 0;
let kLayer = null, mLayer = null, tried = -1;

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

export function applyUserProperties(changed) {
	if (changed.hasOwnProperty('tailfollow')) {
		amount = clamp(Number(changed.tailfollow) / 100, 0, 1);
	}
}

function findLayers() {
	if ((!kLayer || !mLayer) && engine.runtime > tried) {
		tried = engine.runtime + 1;
		try { kLayer = thisScene.getLayer('K'); } catch (e) { kLayer = null; }
		try { mLayer = thisScene.getLayer('MandalaK'); } catch (e) { mLayer = null; }
	}
}

function spring(x, v, goal, omega, zeta, dt) {
	while (dt > 0) {                                   // sub-step for a stable spring
		const s = Math.min(dt, 1 / 120);
		const acc = omega * omega * (goal - x) - 2 * zeta * omega * v;
		v += acc * s;
		x += v * s;
		dt -= s;
	}
	return [x, v];
}

export function update(value) {
	const w = engine.canvasSize.x, h = engine.canvasSize.y;
	if (!(w > 0) || !(h > 0)) {
		return value;
	}
	findLayers();
	const cur = input.cursorWorldPosition;
	const dt = Math.min(engine.frametime, 0.05);

	// reach (horizontal only)
	const tipX = kLayer ? kLayer.origin.x + (TAIL_TX - TEX_CX) * kLayer.scale.x : w * 0.72;
	const cx = mLayer ? mLayer.origin.x : w / 2;
	const dir = cx >= tipX ? 1 : -1;
	const d = (cur.x - tipX) * dir / w;
	const pgoal = clamp((d - P_START) / (P_FULL - P_START), 0, 1) * amount;
	[ppos, pvel] = spring(ppos, pvel, pgoal, P_OMEGA, P_ZETA, dt);
	const pose = clamp(ppos, 0, 1);
	if (OUT === 1) {
		return pose * pose * (3 - 2 * pose);
	}

	// lean
	const goal = clamp((cur.x - tipX) / (REACH * w), -1, 1) * amount * (1 - pose);
	[pos, vel] = spring(pos, vel, goal, OMEGA, ZETA, dt);
	return clamp(pos, -1, 1);
}
