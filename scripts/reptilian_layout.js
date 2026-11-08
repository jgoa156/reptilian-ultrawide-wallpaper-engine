'use strict';

// Layout controller for the Reptilian wallpaper.
// Bound to the "visible" property of layer K; it positions every art layer as one rigid group so
// the effects and painted masks (which live in each layer's UV space) stay aligned on any resolution.
//
// Rules:
//  - the creature is 90% of the visible screen height, width follows its aspect ratio
//  - it is pinned to the bottom-right corner (the artwork is cropped at its bottom and right edge,
//    so those edges must touch the screen); Wallpaper Engine's own flip option mirrors it to the left
//  - the kaleidoscope background stays centred and scales with the screen height
// Scene coordinates are bottom-left origin, Y up.

export var scriptProperties = createScriptProperties()
	.addSlider({ name: 'heightPercent', label: 'Height (% of screen)', value: 90, min: 10, max: 100, integer: false })
	.finish();

// Creature bounds in the authored scene coordinates (measured from layer K's alpha).
const ART = { right: 5120, bottom: 2, top: 2082 };
const AUTHORED_CANVAS = { x: 5120, y: 2160 };
// Shadow: outer drop shadow under W (same UV space, same motion).
// CB_*: full-frame cyan crops (bass blue, one bass band each) above M; same UV space as the rest.
// Smoke: the edge smoke particle system behind the creature (scripts/add_edge_smoke.py); it moves
// and scales with the creature, so it keeps rising from behind it.
const GROUP = ['Smoke', 'Shadow', 'W', 'C', 'M', 'CB_Chest', 'CB_Tail4', 'CB_Tail3', 'CB_Tail2', 'CB_Tail1', 'C2', 'K'];
// Centred layers: kaleidoscope + the spectrum mandala (one black layer; its effect draws the
// pieces, glitch, datamosh and splash). Any authored offset from the canvas centre is kept, scaled.
const BACKGROUND = ['BG', 'MandalaK'];

let base = null;

function capture() {
	base = {};
	for (const name of GROUP.concat(BACKGROUND)) {
		const layer = thisScene.getLayer(name);
		if (layer) {
			base[name] = { layer: layer, origin: layer.origin.copy(), scale: layer.scale.copy() };
		}
	}
}

// Wallpaper Engine fills the screen with the scene canvas (centred, cropping the overflow),
// so work out which part of the canvas is actually visible.
function visibleRect(screen) {
	let cw = engine.canvasSize.x;
	let ch = engine.canvasSize.y;
	if (!(cw > 0 && ch > 0)) {
		cw = AUTHORED_CANVAS.x;
		ch = AUTHORED_CANVAS.y;
	}
	const res = screen || engine.screenResolution;
	const aspect = res && res.x > 0 && res.y > 0 ? res.x / res.y : cw / ch;
	if (aspect < cw / ch) {
		const w = ch * aspect;
		return { x: (cw - w) / 2, y: 0, w: w, h: ch };
	}
	const h = cw / aspect;
	return { x: 0, y: (ch - h) / 2, w: cw, h: h };
}

function layout(screen) {
	if (!base) {
		return;
	}
	const view = visibleRect(screen);
	const s = (scriptProperties.heightPercent / 100) * view.h / (ART.top - ART.bottom);

	for (const name of GROUP) {
		const b = base[name];
		if (!b) {
			continue;
		}
		b.layer.origin = new Vec3(view.x + view.w + (b.origin.x - ART.right) * s, view.y + (b.origin.y - ART.bottom) * s, b.origin.z);
		b.layer.scale = new Vec3(b.scale.x * s, b.scale.y * s, b.scale.z);
	}

	const k = view.h / AUTHORED_CANVAS.y;
	for (const name of BACKGROUND) {
		const bg = base[name];
		if (!bg) {
			continue;
		}
		const ox = (bg.origin.x - AUTHORED_CANVAS.x / 2) * k;
		const oy = (bg.origin.y - AUTHORED_CANVAS.y / 2) * k;
		bg.layer.origin = new Vec3(view.x + view.w / 2 + ox, view.y + view.h / 2 + oy, bg.origin.z);
		bg.layer.scale = new Vec3(bg.scale.x * k, bg.scale.y * k, bg.scale.z);
	}
}

export function init(value) {
	capture();
	layout();
	return value;
}

export function resizeScreen(size) {
	layout(size);
}
