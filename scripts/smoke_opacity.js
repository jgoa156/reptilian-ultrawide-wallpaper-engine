'use strict';

// Edge smoke opacity. Bound to the "Smoke" particle layer's instance-override alpha (installed by
// scripts/add_edge_smoke.py). User property `smokeopacity` (0..200 %) multiplies the particles'
// own alpha; 100 % is the approved "light" look.

let a = 1;

export function applyUserProperties(changed) {
	if (changed.hasOwnProperty('smokeopacity')) {
		a = Math.max(0, Number(changed.smokeopacity)) / 100;
	}
}

export function update(value) {
	return a;
}
