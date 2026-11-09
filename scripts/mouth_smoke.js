'use strict';

// Mouth smoke puff. Bound to the "MouthSmoke" particle layer's instance-override rate (installed by
// scripts/add_mouth_smoke.py). scripts/creature_driver.js writes shared.creaturePuff (engine.runtime of
// a strong bass hit, the same hit that snaps the jaw open); for PUFF seconds after it the emitter runs
// at full rate, otherwise it is shut. `smokeopacity` does not apply here (the puff has its own alpha).

const PUFF = 0.22;         // s of emission per hit (~6-8 puffs)

export function update(value) {
	const t = shared.creaturePuff;
	return (typeof t === 'number' && engine.runtime - t >= 0 && engine.runtime - t < PUFF) ? 1 : 0;
}
