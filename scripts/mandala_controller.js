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
//  * Spin: this script integrates the angle (`spinphase`) so the speed can change without a jump.
//    It is 1 / `spinperiod` turns per second, or, with `mandalabpmspin` on and a tempo detected,
//    one piece every `mandalabeatsperpiece` beats (13 pieces per turn). The speed glides
//    (~1.5 s); after 6 s without a beat it glides back to `spinperiod`.
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

let fx = null, mLayer = null, tried = 0;
let presence = 0, fast = 0, slow = 0, favg = 0.02, hold = 0.05;
let tickAcc = 0, mosh = 0, moshSeed = 0, moshErrors = 0;
let efast = 0, eslow = 0, eavg = 0.02, epulse = 0, glitchUntil = 0, glitchCool = 0, glitchOn = false;
let glitchLv = 0, glitchSlices = 0;
const GLITCH_SCALE = 0.1;           // user: "WAY WAY more subtle" -> a tenth of Leonard's shove
const MOSH_MAX = 0.3;               // datamosh opacity cap (was 1)

// user properties (project.json): beat glitch and datamosh noise, each on/off + strength in %;
// spin period, and the spin following the song's tempo (beats per piece, 13 pieces per turn)
let uGlitchOn = true, uGlitchAmt = 1, uMoshOn = true, uMoshAmt = 1;
let uPeriod = 39, uBpmSpin = false, uBeatsPerPiece = 4;
// the centre eye (`mandalaeye`); the shader's `eye` is set from here. Shelved 2026-11-10 until its
// design is done: EYE_ENABLED false keeps it off whatever the user property says (the property is
// removed from project.json too, see scripts/add_living_creature.py)
const EYE_ENABLED = false;
let uEye = EYE_ENABLED;

export function applyUserProperties(changed) {
	if (changed.mandalaglitch !== undefined) uGlitchOn = !!changed.mandalaglitch;
	if (changed.mandalaglitchstrength !== undefined) uGlitchAmt = changed.mandalaglitchstrength / 100;
	if (changed.mandaladatamosh !== undefined) uMoshOn = !!changed.mandaladatamosh;
	if (changed.mandaladatamoshstrength !== undefined) uMoshAmt = changed.mandaladatamoshstrength / 100;
	if (changed.spinperiod !== undefined) uPeriod = Math.max(changed.spinperiod, 0.1);
	if (changed.mandalabpmspin !== undefined) uBpmSpin = !!changed.mandalabpmspin;
	if (changed.mandalabeatsperpiece !== undefined) uBeatsPerPiece = Math.max(changed.mandalabeatsperpiece, 1);
	if (changed.mandalaeye !== undefined) {
		const on = EYE_ENABLED && !!changed.mandalaeye;
		if (!on && uEye) eyeReset();
		uEye = on;
	}
}

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }

// ---- tempo (BPM) detection
// Onset envelope: positive spectral flux of the log spectrum (bass bands weighted double), sampled
// at a fixed 60 Hz whatever the frame rate. Every 0.5 s the last 8 s are autocorrelated over the
// lags of 70..180 BPM, each lag scored with its 2x and 3x multiples (a beat repeats), weighted
// toward ~120 BPM (the usual half/double-time ambiguity), refined to a fractional lag by a parabola.
// The reading only replaces the held tempo when it is confident; octave jumps (x2, x0.5) of the
// held tempo are ignored, a real tempo change has to win 4 checks in a row.
const BPM_HOP = 1 / 60, BPM_WIN = 480, BPM_MIN = 70, BPM_MAX = 160;
const BPM_LMIN = Math.ceil(60 / (BPM_MAX * BPM_HOP)), BPM_LMAX = Math.ceil(60 / (BPM_MIN * BPM_HOP));
const bpmEnv = new Float32Array(BPM_WIN), bpmWork = new Float32Array(BPM_WIN);
const bpmPrev = new Float32Array(16);
let bpmPos = 0, bpmCount = 0, bpmAcc = 0, bpmHold = 0, bpmCheck = 0;
let bpm = 0, bpmConf = 0, bpmCand = 0, bpmCandN = 0, bpmLost = 0;

function near(a, b, tol) { return Math.abs(a / b - 1) < tol; }

let bpmFlux = 0;

function bpmFeed(spec, dt) {
	// the audio buffers can refresh slower than the frame rate: a frame with the same spectrum
	// keeps the last flux (zero-order hold), and every 60 Hz sample a frame spans gets its value,
	// so no artificial zeros comb the envelope at any frame rate
	let flux = 0, changed = false;
	for (let i = 0; i < 16; i++) {
		const v = Math.log(1 + 100 * spec[i]);
		const d = v - bpmPrev[i];
		if (d !== 0) changed = true;
		if (d > 0) flux += i < 6 ? 2 * d : d;
		bpmPrev[i] = v;
	}
	if (changed) bpmFlux = flux;
	bpmHold = Math.max(bpmHold, bpmFlux);
	bpmAcc += dt;
	let pushed = false;
	for (let n = 0; bpmAcc >= BPM_HOP && n < 30; n++) {
		bpmAcc -= BPM_HOP;
		bpmEnv[bpmPos] = bpmHold;
		bpmPos = (bpmPos + 1) % BPM_WIN;
		if (bpmCount < BPM_WIN) bpmCount++;
		pushed = true;
	}
	if (pushed) bpmHold = 0;
	if (bpmAcc > BPM_HOP) bpmAcc = 0;                    // long stall: drop the backlog
}

// one tempo reading from the envelope: [bpm, confidence 0..1]
function bpmRead() {
	const N = bpmCount, start = (bpmPos - N + BPM_WIN) % BPM_WIN;
	for (let i = 0; i < N; i++) bpmWork[i] = bpmEnv[(start + i) % BPM_WIN];
	// remove the local mean (0.25 s) and keep the rises: an onset train, not the loudness
	const H = 7, pre = new Float32Array(N + 1), tmp = new Float32Array(N);
	for (let i = 0; i < N; i++) pre[i + 1] = pre[i] + bpmWork[i];
	for (let c = 0; c < N; c++) {
		const lo = Math.max(0, c - H), hi = Math.min(N, c + H + 1);
		tmp[c] = Math.max(0, bpmWork[c] - (pre[hi] - pre[lo]) / (hi - lo));
	}
	let r0 = 0;
	for (let i = 0; i < N; i++) r0 += tmp[i] * tmp[i];
	if (r0 <= 1e-9) return [0, 0];
	const acf = (L) => {
		let s = 0;
		for (let i = L; i < N; i++) s += tmp[i] * tmp[i - L];
		return s / (N - L);
	};
	const r = new Float32Array(3 * BPM_LMAX + 1);
	for (let L = BPM_LMIN - 1; L <= Math.min(3 * BPM_LMAX, N - 1); L++) r[L] = acf(L);
	let best = BPM_LMIN, bestS = -1e9;
	for (let L = BPM_LMIN; L <= BPM_LMAX; L++) {
		const oct = Math.log2(60 / (L * BPM_HOP) / 120) / 0.9;
		const s = (r[L] + 0.5 * r[2 * L] + 0.33 * r[3 * L]) * Math.exp(-0.5 * oct * oct);
		if (s > bestS) { bestS = s; best = L; }
	}
	// fractional lag from the raw autocorrelation around the peak
	const a = r[best - 1], b0 = r[best], c = r[best + 1];
	const den = a - 2 * b0 + c;
	const off = den < 0 ? clamp(0.5 * (a - c) / den, -0.5, 0.5) : 0;
	return [60 / ((best + off) * BPM_HOP), clamp(b0 * N / r0, 0, 1)];
}

function bpmUpdate(dt, playing) {
	bpmCheck += dt;
	if (bpmCheck < 0.5) return;
	bpmCheck = 0;
	const [cand, conf] = bpmCount >= 240 && playing ? bpmRead() : [0, 0];
	bpmConf = conf;
	if (!(cand > 0) || conf < 0.12) {
		bpmLost += 0.5;
		if (bpmLost > 6) bpm = 0;                             // 6 s with no beat: let the spin go back
		return;
	}
	bpmLost = 0;
	const agree = bpmCandN > 0 && near(cand, bpmCand, 0.04);
	if (!(bpm > 0)) {                                     // first lock: two confident readings that agree
		if (conf < 0.3) { bpmCandN = 0; return; }
		if (agree) { bpm = (cand + bpmCand) / 2; bpmCandN = 0; } else { bpmCand = cand; bpmCandN = 1; }
		return;
	}
	if (near(cand, bpm, 0.04)) { bpm += (cand - bpm) * 0.25; bpmCandN = 0; return; }
	for (const k of RELATED) {                            // the same beat felt at another level: keep
		if (near(cand, bpm * k, 0.04)) return;
	}
	if (agree) bpmCandN++;
	else { bpmCand = cand; bpmCandN = 1; }
	if (bpmCandN >= 4) { bpm = cand; bpmCandN = 0; }
}
const RELATED = [2, 1 / 2, 3 / 2, 2 / 3, 4 / 3, 3 / 4, 3, 1 / 3];

// ---- spin: the script integrates the angle so a change of speed never jumps the wheel
let spinPhase = -1, spinSpeed = 0;

function spinUpdate(dt) {
	const target = uBpmSpin && bpm > 0 ? bpm / 60 / (13 * uBeatsPerPiece) : 1 / uPeriod;   // turns per second
	if (spinPhase < 0) {                                  // take over from the shader's g_Time spin
		spinPhase = (engine.runtime / uPeriod) % 1;
		spinSpeed = 1 / uPeriod;
	}
	spinSpeed += (target - spinSpeed) * (1 - Math.exp(-dt / 1.5));
	spinPhase = (spinPhase + spinSpeed * dt) % 1;
	set('spinphase', spinPhase);
	set('spinscripted', 1);
}

const eyeX = { x: 0, v: 0 }, eyeY = { x: 0, v: 0 };
let eyeBlinkAt = 5, eyeBlinkT = -1;
function eyeSpring(s, goal, dt) {                     // omega 7, zeta 0.85: a calm, slightly lazy gaze
	while (dt > 0) {
		const h = Math.min(dt, 1 / 120);
		s.v += (49 * (goal - s.x) - 2 * 0.85 * 7 * s.v) * h;
		s.x += s.v * h;
		dt -= h;
	}
}

// the centre eye: iris toward the cursor (spring), a blink every 4..9 s
function eyeUpdate(dt) {
	if (mLayer) {
		const cw = engine.canvasSize.x;
		const cur = input.cursorWorldPosition;
		let gx = 0, gy = 0;
		if (cw > 0) {
			gx = (cur.x - mLayer.origin.x) / (0.35 * cw);
			gy = -(cur.y - mLayer.origin.y) / (0.35 * cw);         // the shader's y runs down
			const L = Math.hypot(gx, gy);
			if (L > 1) { gx /= L; gy /= L; }
		}
		eyeSpring(eyeX, gx, dt);
		eyeSpring(eyeY, gy, dt);
		set('eyelookx', clamp(eyeX.x, -1, 1));
		set('eyelooky', clamp(eyeY.x, -1, 1));
	}
	if (eyeBlinkT < 0 && engine.runtime >= eyeBlinkAt) eyeBlinkT = 0;
	let eb = 0;
	if (eyeBlinkT >= 0) {
		eyeBlinkT += dt;
		const t = eyeBlinkT;
		eb = t < 0.09 ? t / 0.09 : t < 0.14 ? 1 : t < 0.3 ? 1 - (t - 0.14) / 0.16 : 0;
		if (t >= 0.3) { eyeBlinkT = -1; eyeBlinkAt = engine.runtime + 4 + Math.random() * 5; }
	}
	set('eyeblink', eb);
}

// switched off: park it centred and open, so it doesn't come back mid-blink or glancing away
function eyeReset() {
	eyeX.x = eyeX.v = eyeY.x = eyeY.v = 0;
	eyeBlinkT = -1;
	eyeBlinkAt = engine.runtime + 4 + Math.random() * 5;
	if (fx) { set('eyelookx', 0); set('eyelooky', 0); set('eyeblink', 0); }
}

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
		mLayer = layer;
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

	// ---- tempo + spin
	bpmFeed(audio.average, dt);
	bpmUpdate(dt, presence > 0.5);
	spinUpdate(dt);

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

	// ---- the centre eye (user property `mandalaeye`): off = the shader skips it entirely and none of
	// this runs; it comes back centred and open
	set('eye', uEye ? 1 : 0);
	if (uEye) eyeUpdate(dt);

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
