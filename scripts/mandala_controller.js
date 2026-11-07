'use strict';

// Mandala controller, bound to MandalaK's alpha (installed by scripts/add_mandalas.py).
//
// The 13 pieces, their spin, their side fades and their bulge live in the "Spectrum mandala"
// shader effect. This script feeds it the 13 piece levels (arm0..arm12, bass) every frame and
// drives what needs memory over time:
//
//  * Silence: every piece breathes together (the old pulse, period `period`).
//    Music: the breathing hands over to the sound. The floor drops to `musicFloor`, so each
//    piece reads by its own band. The hand-over follows a smoothed "is music playing" level.
//  * Datamosh (Customizable Module Visualizer): while the bass is above `moshLevel` of its
//    recent peak, a fresh corrupted frame is rolled on each ~33 ms tick with probability
//    0.5 * moshChance. Louder bass means more errors and higher opacity. Otherwise the
//    corruption dies out within a few ticks.
//  * Leonard glitch (Master Leonard, src/leonard.c), black layer only: on every beat (an onset of
//    the whole song) 3..7 horizontal slices shear sideways for 90..300 ms. Harder hits tear more
//    slices and shove them further. It only moves pixels, so it keeps the pieces' darkness: in
//    a song, only the pieces whose band is sounding get blacker.
//
// Opacity: the shader's min/max opacity, bound straight to the user properties
// `mandalaminopacity` / `mandalamaxopacity` (blur: `mandalablur`). This script no longer touches
// them. The layer alpha it returns (1) does nothing visible: the effect replaces the layer image.
//
// Idle = the full mandala (`slice` 0); music = 13 pieces (`slice` follows the music presence).

export var scriptProperties = createScriptProperties()
	.addSlider({ name: 'period', label: 'Silent pulse period (s)', value: 7, min: 0.5, max: 30, integer: false })
	.addSlider({ name: 'depth', label: 'Silent pulse depth', value: 0.6, min: 0, max: 1, integer: false })
	.addSlider({ name: 'musicFloor', label: 'Piece level under music', value: 0.15, min: 0, max: 1, integer: false })
	.addSlider({ name: 'moshChance', label: 'Datamosh strength', value: 1, min: 0, max: 2, integer: false })
	.addSlider({ name: 'moshLevel', label: 'Datamosh bass level', value: 0.7, min: 0, max: 1, integer: false })
	.addSlider({ name: 'glitch', label: 'Glitch strength', value: 1, min: 0, max: 2, integer: false })
	.finish();

const audio = engine.registerAudioBuffers(engine.AUDIO_RESOLUTION_16);
const EFFECT = 'Spectrum mandala';

// 13 pieces, clockwise from the top: the top piece takes the lowest bands of both channels,
// the right half the right channel and the left half the left channel, both rising in pitch
// toward the bottom (7 band groups over WE's 16 bands). Higher bands carry less energy, so their
// bounds are lower (bass pieces 0.2..1.1, treble pieces 0.04..0.45).
const GROUPS = [[0, 2], [2, 4], [4, 6], [6, 9], [9, 11], [11, 13], [13, 15]];
const ARMS = [[0, 'both']];
for (let g = 1; g <= 6; g++) ARMS[g] = [g, 'right'];
for (let g = 6; g >= 1; g--) ARMS[13 - g] = [g, 'left'];
const BOUNDS_LOW = [0.2, 1.1], BOUNDS_HIGH = [0.04, 0.45];
const armLv = new Array(13).fill(0);
let bassLv = 0;

function smooth01(a, b, x) { const t = clamp((x - a) / (b - a), 0, 1); return t * t * (3 - 2 * t); }
function groupLevel(buf, g) {
	let v = 0;
	for (let i = GROUPS[g][0]; i <= GROUPS[g][1]; i++) v += buf[i];
	return v / (GROUPS[g][1] - GROUPS[g][0] + 1);
}

let fx = null, tried = 0;
let presence = 0, fast = 0, slow = 0, favg = 0.02, hold = 0.05;
let tickAcc = 0, mosh = 0, moshSeed = 0, moshErrors = 0;
let efast = 0, eslow = 0, eavg = 0.02, epulse = 0, glitchUntil = 0, glitchCool = 0, glitchOn = false;
let glitchLv = 0, glitchSlices = 0;
const GLITCH_SCALE = 0.1;           // user: "WAY WAY more subtle" -> a tenth of Leonard's shove
const MOSH_MAX = 0.3;               // datamosh opacity cap (was 1)

// user properties (project.json): beat glitch and datamosh noise, each on/off + strength in %
let uGlitchOn = true, uGlitchAmt = 1, uMoshOn = true, uMoshAmt = 1;

export function applyUserProperties(changed) {
	if (changed.mandalaglitch !== undefined) uGlitchOn = !!changed.mandalaglitch;
	if (changed.mandalaglitchstrength !== undefined) uGlitchAmt = changed.mandalaglitchstrength / 100;
	if (changed.mandaladatamosh !== undefined) uMoshOn = !!changed.mandaladatamosh;
	if (changed.mandaladatamoshstrength !== undefined) uMoshAmt = changed.mandaladatamoshstrength / 100;
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

function set(name, v) {
	try { fx.setMaterialProperty(name, v); } catch (e) { /* older WE: leave the shader defaults */ }
}

export function update(value) {
	const p = scriptProperties;
	const dt = engine.frametime;
	if (!(dt > 0)) {
		return 1;
	}
	if (!fx && engine.runtime > tried) {                  // retry once a second until the layer exists
		tried = engine.runtime + 1;
		const layer = thisScene.getLayer('MandalaK');
		try { fx = layer ? layer.getEffect(EFFECT) : null; } catch (e) { fx = null; }
	}
	if (!fx) {
		return 1;
	}
	const k30 = Math.min(dt * 30, 4);                     // ~30 fps ticks this frame
	const rate = (a) => 1 - Math.pow(1 - a, k30);

	// ---- levels
	let all = 0, bass = 0;
	for (let i = 0; i < 16; i++) all += audio.average[i];
	all /= 16;
	for (let i = 0; i < 4; i++) bass += audio.average[i];
	bass /= 4;

	// ---- Leonard glitch: onsets of the whole song (leonard.c audio_poll), black layer only
	let l = 0, r = 0;
	for (let i = 0; i < 16; i++) { l += audio.left[i]; r += audio.right[i]; }
	const e = Math.max(l, r) / 16;
	efast += (e - efast) * rate(0.55);
	eslow += (e - eslow) * rate(0.06);
	const eflux = Math.max(0, efast - eslow);
	const en = eflux / (eavg * 1.5 + 0.004);
	eavg += (eflux - eavg) * rate(0.02);
	epulse = Math.max(epulse * Math.pow(0.8, k30), clamp(en, 0, 1.5));
	const ms = engine.runtime * 1000;
	const gAmt = uGlitchOn ? p.glitch * uGlitchAmt : 0;
	if (gAmt > 0 && en > 0.3 && e > 0.01 && ms >= glitchCool) {
		const lv = Math.min(1, Math.max(e * 0.6 / 0.3, Math.min(epulse, 1)));   // how hard the hit was
		const slices = 3 + Math.floor(Math.random() * (1 + Math.round(lv * 4)));  // 3..7
		// Leonard shoves a slice by up to 30 px * (1 + 2.5 lv) on an 800 px panel the mandala's
		// diameter wide: 2 radii = 800 px
		glitchLv = lv;
		glitchSlices = slices;
		set('glitchslices', slices);
		glitchUntil = ms + 90 + Math.random() * 90 + lv * 120;
		glitchCool = ms + 60;
		glitchOn = true;
	}
	if (glitchOn && ms < glitchUntil) {
		// re-roll every frame while active: fast flicker, not one held jump
		set('glitchseed', Math.floor(Math.random() * 1000));
		set('glitchshift', 30 * (1 + 2.5 * glitchLv) / 400 * GLITCH_SCALE * gAmt * (0.5 + Math.random() * 0.5));
	} else if (glitchOn) {
		set('glitchslices', 0);
		glitchOn = false;
	}

	// ---- piece levels (the shader can't read audio itself in WE's translator)
	for (let k = 0; k < 13; k++) {
		const g = ARMS[k][0], side = ARMS[k][1];
		const raw = side === 'both' ? (groupLevel(audio.left, g) + groupLevel(audio.right, g)) * 0.5
			: groupLevel(side === 'left' ? audio.left : audio.right, g);
		const t = g / 6;
		const v = smooth01(BOUNDS_LOW[0] + (BOUNDS_HIGH[0] - BOUNDS_LOW[0]) * t,
			BOUNDS_LOW[1] + (BOUNDS_HIGH[1] - BOUNDS_LOW[1]) * t, raw);
		armLv[k] += (v - armLv[k]) * (v > armLv[k] ? rate(0.6) : rate(0.15));   // snap up, ease down
		set('arm' + k, armLv[k]);
	}
	const bv = smooth01(BOUNDS_LOW[0], BOUNDS_LOW[1], (audio.left[0] + audio.left[1] + audio.right[0] + audio.right[1]) * 0.25);
	bassLv += (bv - bassLv) * (bv > bassLv ? rate(0.6) : rate(0.15));
	set('bass', bassLv);

	// ---- silence <-> music hand-over
	const playing = all > 0.015 ? 1 : 0;
	presence += (playing - presence) * (playing > presence ? rate(0.08) : rate(0.02));
	const wave = 0.5 - 0.5 * Math.cos(2 * Math.PI * engine.runtime / p.period);
	const breath = 1 - p.depth + p.depth * wave;
	set('floor', breath + (p.musicFloor - breath) * presence);
	set('slice', presence);                              // idle: full mandala; music: 13 pieces

	// ---- bass onsets (fast envelope over slow one, normalised by how much the song usually moves)
	fast += (bass - fast) * rate(0.55);
	slow += (bass - slow) * rate(0.06);
	const flux = Math.max(0, fast - slow);
	const n = flux / (favg * 1.5 + 0.004);
	favg += (flux - favg) * rate(0.02);
	hold = Math.max(bass, hold * Math.pow(0.996, k30));
	if (hold < 0.05) hold = 0.05;
	const rel = clamp(bass / hold, 0, 1);                 // bass against its recent peak

	// ---- datamosh: re-rolled every frame (up to 60/s), like the visualizer's per-frame check
	tickAcc += dt;
	if (tickAcc >= 1 / 60) {
		tickAcc = 0;
		const mAmt = uMoshOn ? uMoshAmt : 0;
		if (mAmt > 0 && rel > p.moshLevel && bass > 0.05 && Math.random() < 0.5 * p.moshChance) {
			moshSeed = Math.floor(Math.random() * 1000);
			moshErrors = 1 + Math.floor(Math.random() * rel * 5.99);
			mosh = clamp((rel - p.moshLevel) / Math.max(1 - p.moshLevel, 0.05) * 0.8 + 0.2, 0, 1)
				* Math.min(p.moshChance, 1) * Math.min(MOSH_MAX * mAmt, 1);
		} else {
			mosh *= 0.5;
			if (mosh < 0.01) mosh = 0;
		}
	}
	set('mosh', mosh);
	if (mosh > 0) {
		set('moshseed', moshSeed);
		set('mosherrors', moshErrors);
	}

	return 1;
}
