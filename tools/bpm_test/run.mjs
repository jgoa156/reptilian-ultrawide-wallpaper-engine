// node run.mjs <controller.js> <frames.f32> <fps>: run the real controller on the frames, print the
// held tempo every 5 s, and the spin speed
import fs from 'fs';
import path from 'path';
import { pathToFileURL } from 'url';

const [ctl, framesPath, fpsS] = process.argv.slice(2);
const rep = Number(process.argv[5] || 1);           // each audio frame shown rep times (audio slower than fps)
const fps = Number(fpsS) * rep;
const buf = fs.readFileSync(framesPath);
const S = new Float32Array(buf.buffer, buf.byteOffset, buf.length / 4);
const n = S.length / 16 * rep;

const average = new Float32Array(16), left = new Float32Array(16), right = new Float32Array(16);
const props = {};
globalThis.engine = {
	frametime: 1 / fps, runtime: 0,
	AUDIO_RESOLUTION_16: 16,
	registerAudioBuffers: () => ({ average, left, right }),
};
globalThis.createScriptProperties = () => {
	const b = { addSlider: (o) => { props[o.name] = o.value; return b; }, finish: () => props };
	return b;
};
const mat = {};
globalThis.thisScene = { getLayer: () => ({ getEffect: () => ({ setMaterialProperty: (k, v) => { mat[k] = v; } }) }) };

const tmp = path.join(path.dirname(framesPath), 'ctl_' + process.pid + '.mjs');
fs.writeFileSync(tmp, fs.readFileSync(ctl, 'utf8') + '\nexport function __bpm() { return [bpm, bpmConf]; }\n');
const m = await import(pathToFileURL(tmp).href);
fs.unlinkSync(tmp);
m.applyUserProperties({ spinperiod: 39, mandalabpmspin: true, mandalabeatsperpiece: 4 });

const line = [];
let lastPhase = null;
for (let k = 0; k < n; k++) {
	const a = Math.floor(k / rep);
	for (let i = 0; i < 16; i++) { average[i] = left[i] = right[i] = S[a * 16 + i]; }
	engine.runtime = k / fps;
	m.update(1);
	if (k % Math.round(15 * fps) === 0 && k > 0) {
		const [b, c] = m.__bpm();
		line.push(`${(k / fps).toFixed(0)}s:${b ? b.toFixed(1) : '-'}(${c.toFixed(2)})`);
	}
	if (lastPhase !== null && Math.abs(mat.spinphase - lastPhase) > 0.02 && Math.abs(mat.spinphase - lastPhase) < 0.98) {
		throw new Error('spin jumped at frame ' + k);
	}
	lastPhase = mat.spinphase;
}
console.log(line.join(' '));
