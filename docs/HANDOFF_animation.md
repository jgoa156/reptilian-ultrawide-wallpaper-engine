# Handoff: Reptilian animation rig (and what's next)

Status as of 2026-11-07. **2026-11-09: §19 (arm reach + fixes) and §20 (living creature, mandala eye with an on/off switch) are verified in WE, committed and pushed. Nothing is in progress; read §20 first for the current state.**

The tasks in "Next" are written down only. None have been started. The live scene is
in a state the user approved ("looks right"), with a wavier hair update applied on top.
A separate, also-paused workstream exists for mandalas: see `HANDOFF_mandalas.md`.

---

## 1. Where everything is

| What | Path |
|---|---|
| Live WE project | `D:\Steam\steamapps\common\wallpaper_engine\projects\myprojects\reptilian_ultrawide_5120` |
| Working folder (this one) | `C:\Users\rockb\OneDrive\Área de Trabalho\Reptilian Ultrawide 4K` |
| Published original (source of truth for the restore) | `D:\Steam\steamapps\workshop\content\431960\3349566695\scene.pkg` |
| Decoded original layers + masks (lossless PNG) | `recovered_original/`, `recovered_original/masks/` |
| Original scene, 5040-wide | `recovered_original/scene_original_5040.json` |
| Motion maps as PNG (editable/viewable) | `rig/` (v1), `rig/v2/` (current masks + tail/body), `rig/v3/` (current hair) |
| Tools (Python 3.13 + numpy/scipy/OpenCV/Pillow; Node for the harness) | `tools/` (see section 6) |
| Calibration reports | `reports/` |
| Layout script (source) | `scripts/reptilian_layout.js` |
| Full project copy of the faithful restore | `myprojects/reptilian_ultrawide_5120_backup_2026-11-07` |

Backups of `scene.json`, oldest first. Each is a known-good state you can roll back to:

| Folder | State |
|---|---|
| `backups/2026-11-07_before_animation_overhaul/` | Faithful restore, 5120 layout |
| `backups/2026-11-07_rig_v1/` | First rig. It tore at peaks; this is the one in the user's recording |
| `backups/2026-11-07_rig_v2/` | Strain-limited rig + cleaned masks |
| `backups/2026-11-07_before_wavy_hair/` | v2 + foliage calibration + C2 bass layer |
| `backups/2026-11-07_before_mandalas/` | Identical to the current live scene, taken by the mandala session |

---

## 2. Current live scene

Canvas: 5120×2160.

Draw order, back to front: **BG → W → C → M → C2 → K**.

- **Art layers:** W, C, M, C2 and K all use 5040×2160 textures with the creature in the
  right part, at texture x 3648–5040, y 80–2160. They therefore share one UV space,
  and every mask or flow map works on all of them.
- **Layout:** handled by a SceneScript on K's `visible` property.
  - The art group sits at 90% of screen height, pinned bottom-right; WE's flip option
    mirrors it.
  - BG stays centred.
  - The live embedded copy is the old version without the mandala list. The newer
    `scripts/reptilian_layout.js` (with mandalas) has not been pushed into the scene yet.

| Layer | What it is | Opacity | Notes |
|---|---|---|---|
| BG | Kaleidoscope, 1500², scale 2 | 0.1 | Slow spin + audio pulses (unchanged from original) |
| W | Light-grey silhouette fill | 1 | Gets only the big rig motions + lens |
| C | Cyan ink copy, scale 1.003 | 0.36 | `(C) Música` pulse, left channel, bands 0–10. This is the face blue: it only shows where it isn't covered by M, which is near the face |
| M | Magenta ink copy, offset −15px, scale 1.01 | 0.66 | `(M) Música` pulse bound to user colors + motion blur |
| C2 | Cyan ink copy, offset (−5, +4)px from K, scale 1 | 0.45 | `(C2) Bass` pulse: AUDIOPROCESSING 3, bands 0–2, bounds 0.25–1.2, exponent 0.35, amount 2. Cyan fringe on every stroke on bass hits |
| K | Black line art | 1 | Full detail stack + edge detection + gill radial blur |

### Effect stack

K, C, M and C2 all run the same stack, so the colors stay in register. The order
matters, because masks are in UV space and must see the undeformed art:

1. **Each layer's own color/audio effects:** C's pulse, M's pulse + motion blur, C2's bass pulse.
2. **Detail effects:**
   - Spins: Olhar #1, Olho #2, Mini Eye #1, Mini Eye #2.
   - Iris: Olho menor #1, Little Eyes.
   - Foliage: Guelras, Strings Hair, Strings Back.
   - Twirls: Nose twirl, Honeycomb.
   - Tail edge shimmer (waterwaves).
   - Balance (General) (shake).
   - K only: Ink edges (edge detection) and Guelras (2) (radial blur).
3. **Rig, 3 shake passes:**

   | Pass | Speed | Strength | Peak movement |
   |---|---|---|---|
   | Rig: Hair & Tendrils (`rig3_appendages`) | 1.3 | 0.098 | Hair tips ~48px, tendrils ~11px |
   | Rig: Tail (`rig2_tail`) | 1.04 | 0.074 | ~27px at the tip |
   | Rig: Head & Body (`rig2_body`) | 0.9 | 0.082 | Head nod ~10px at the face, abdomen breathing ~6px, guts slither ~4px around the coils, ribbed-tube contraction wave ~4px |

4. **Lens distortion** (static, original values).

Total: **83 shader passes.** Every effect added to the art stack costs about 4–5 passes,
one per art layer.

### Calibrated values that differ from the author's original

| Effect | Original | Now | Why |
|---|---|---|---|
| Guelras (foliage) | strength 0.31 | 0.171 | Was close to folding over itself (strain 0.98) |
| Strings Hair (foliage) | 0.21 | 0.153 | Caused the "fourth hair" glitch |
| Strings Back (foliage) | 0.35 | 0.278 | Over the strain limit |
| Balance (General) | 0.04 | 0.036 | Map smoothed |
| Guelras (2) blur centre | (0.5, 0.5) | (0.9331, 0.41629) | The default smeared toward the texture middle |
| Twirls | feather 0.002 | 0.9 × size | Hard edge made a tearing ring |
| Mini Eye #1 / #2 spin centres | | Moved 11 / 14px onto their pupils | Were spinning blank ink |

- **Removed as no-ops:** an empty shake, and a pulse with both tints white.
- **Replaced by the rig:** the author's three swings and the old tail shake.
- **Masks:** all of the author's masks are feathered copies, named `masks/fix_*`. The
  originals are still in `materials/masks`.

---

## 3. Hard-won rules (read before touching motion)

1. **Strain limit.** No displacement map may change by more than **~0.3 px of
   displacement per px of distance**, at the worst moment of the cycle, with
   time-offset gradients included.
   - Above ~0.3 the art visibly stretches.
   - At ≥1 it folds over itself. That was the hair/tail "glitch" (v1 had 5–6).
   - Check with `tools/hairsim*.py` (simulates effects over time against WE's real
     `assets/materials/util/noise.png`).
   - Several effects that each pass 0.3 can still add up to more. Simulate the whole
     stack for a region, not one effect.
2. **Tips must carry their surroundings.** A moving spike or tail tip needs the
   transparent space around it to move too. Otherwise the tip tears off.
3. **Move pieces coherently.** Don't key motion to per-piece path length when pieces
   sit next to each other. Neighbours then disagree, and you have to blur the field
   to stop tearing, which kills the amplitude. That's why the hair v3 uses smooth
   height above the scalp instead.
4. **Masks need feathered edges.** A mask edge needs a feather at least as wide as
   (peak displacement / 0.3).
5. **Foliage-sway peaks are ~4×** strength² × 0.005 (four summed sines can line up),
   not 2.5×. Its noise ripple also shears inside the mask, so cap strength by
   simulating, not by the mask edge alone.
6. **Shake time-offset maps can't wrap.** They're 8-bit, 0..1 → 0..2π, and a 255→0 wrap
   becomes a glitch line under bilinear filtering. So at most one wave per piece.
   `M_PI_2` in WE shaders is 2π, so the shake is a clean sine.
7. **Effect order:** detail (masked) effects first, then big rig motions, then the lens.
8. **One UV space:** new art layers should stay full-frame 5040×2160 with the same
   placement, so every existing mask and flow map works on them as-is.
9. **Texture format WE accepts for masks:** `TEXV0005/TEXI0001/TEXB0003`.
   - Flow maps: fmt 8 (RG88). Opacity/time maps: fmt 9 (R8). Both 1720×720,
     LZ4 literal-only block, neutral bytes `7f7f00ff` (flow) or `000000ff`.
   - Writer: `write_tex` in `tools/rig2.py`. Reader: `tools/untex.py`.
   - Proven by loading in WE.
10. **Wallpaper Engine runs elevated (as admin)** on this PC, so Claude can't drive the
    editor or send it `-control` commands. The user tests in the editor and records a
    clip; analyse it with optical flow (motion map + direction reversals per second).
    That's how the tearing was found.

---

## 4. Next: what the user asked for (not started)

### A. More blue on the chest (bass), and the tail too

Today the bass cyan comes from C2 at 0.45 opacity sitting over M. On the chest it reads
as a thin fringe, and on the tail it blends into a lavender. The user's plan, which is
sound:

- **Crop the belly/chest area of the cyan ink** into its own PNG and put it **above the
  magenta layer**, so it's definitely visible.
- **Do the same for the tail.**

How to do it without breaking the rig:

1. **Source:** `recovered_original/C.png`, the full-frame 5040×2160 cyan ink.
   - Keep the PNG **full-frame 5040×2160**, transparent outside the cut, with a soft
     (~20–40px) alpha edge. Don't crop the canvas: that keeps the UV space, so every
     mask and flow map applies unchanged.
2. **Regions** (texture px; u = x/5040, v = y/2160):
   - Belly/abdomen: roughly x 4350–4800, y 1150–1950.
   - Chest corner + guts: x 4750–5040, y 1150–2160. Coils centred ~(4935, 1480); ribbed
     tube ~x 4880–5040, y 1660–2160.
   - Tail: the tail silhouette, x < 3950, plus the bottom sweep y > 1870, x < 4560. Use
     the tail region from `tools/rig2.py` (`tail_region`) to cut it exactly.
3. **New layers** (e.g. `CB_Chest`, `CB_Tail`) go between M and C2/K.
   - Placement like C2: origin = K's origin + (−5, +4), scale 1.
   - Pulse: a copy of `(C2) Bass` (AUDIOPROCESSING 3, bands 0–2). Higher opacity
     (0.7–1.0) so it reads clearly.
4. **Give them the same motion stack as C2**, minus C2's pulse: detail effects + the 3
   rig passes + lens. Otherwise the blue drifts off the moving art. That's about +18
   passes per layer, so consider giving these layers only the effects that touch their
   region:
   - Chest: Rig: Head & Body, Guelras, Strings Back, Balance, lens.
   - Tail: Rig: Tail, Tail edge shimmer, lens.
5. **Add the layer names to `GROUP`** in `scripts/reptilian_layout.js`, then re-embed the
   script into K's `visible.script`. Otherwise the new layers won't follow the
   90%-height layout.
6. **Coordinate with the mandala installer** (`scripts/add_mandalas.py`). It also edits
   `scene.json` and re-embeds the layout script. Run one change at a time, take a fresh
   backup first, and recompute the max effect id at that moment.

### B. Animate every inch of the beast

The user wants the whole creature alive. Priorities, in their words: the **face needs a
lot of animation**, then the **chest, especially the area toward the corner** (the
lower-right of the creature, toward the frame edge).

What already moves:

| Region | Current motion |
|---|---|
| Hair crest + back mane | Rig + Strings Hair / Strings Back + Balance |
| Tail + barbs | Rig + edge shimmer |
| Tendrils | Rig |
| Gills | Foliage + radial blur |
| Eyes | 4 spins + 2 iris |
| Nose | Twirl |
| Honeycomb | Twirl |
| Whole head | Nod |
| Belly | Breathing |
| Coils | Slither |
| Ribbed tube | Contraction wave |

Gaps to fill. Coordinates are texture px; all these sections were already segmented in
`tools/rig*.py`.

- **Face** (x ~3990–4450, y ~450–1300):
  - Forehead dot column at x≈4187, y 665/690/715/742: blink or pulse them in sequence.
  - Ring eye at (4149, 822).
  - Brow ridge (x 4100–4300, y 450–620).
  - Cheek/face plates and the white highlight streaks.
  - Jaw/mouth (x 4060–4330, y 1180–1440): a slow open/close via a shake flow map
    rotating about the jaw hinge.
  - Ideas: subtle muscle twitches (small shake flow maps per plate, staggered
    time-offsets); highlight shimmer (waterwaves at very low strength in the white
    streaks).
- **Chest toward the corner** (x 4750–5040, y 600–2160):
  - Shoulder/back stripes (x 4700–5040, y 600–1300).
  - The coils.
  - The ribbed tube.
  - The lower-right corner down to the frame edge.
  - Today they only get ~4–6px from the body pass, plus Strings Back.
  - Ideas: stronger peristalsis in the tube; ribs that pulse with bass (a masked pulse
    on the new blue chest layer); a slow "muscle flex" shake over the shoulder stripes.
  - The body continues off-frame at the right edge, so fade any horizontal motion to 0
    over the last ~90–220px. Otherwise the clamped edge smears.

Constraints for all of it:
- Strain ≤ 0.3 combined (rule 1).
- Keep speeds in the existing family (0.5–3.2) so it reads as one creature.
- Watch the pass budget: prefer adding new regions to the existing three rig passes'
  flow/time maps (they're combined per pass in `tools/rig2.py` / `rig3_hair.py`)
  over adding new effects.

### C. Saved idea, not for now: cel-shading texture from the user's drawings

The user has other drawings in the same hatching style. The idea is to analyse all of
them and build a game-ready **tonal art map**:
- 6–8 tileable hatch textures, light → dark, cut from real stroke patches.
- Darker levels contain the lighter levels' strokes.
- An RGBA atlas plus a sample cel/hatch shader for their engine.

A proposal card for this was created in the original session. It's a separate project,
in its own folder; ask the user where the drawings are and which engine they target.

---

## 5. How to test a change

1. Back up `scene.json` (and `project.json`) into `backups/<date>_<label>/` first.
2. Validate:
   - JSON parses.
   - Every `file`/`image` and every `masks/*` reference exists.
   - No duplicate ids.
   - New `.tex` files round-trip through `tools/untex.py`.
3. Simulate motion with the tools in section 6. Compare rest vs both peak extremes at
   full resolution on tips and edges.
4. Ask the user to open the project in the WE editor and, if anything looks off, record
   a clip. Then analyse it with OpenCV optical flow:
   - High direction reversals per second plus jerk ≈ speed means tearing or flicker,
     not sway.

---

## 6. Tools (in `tools/`)

Arguments are positional. Each script's header explains it.

| Script | Purpose |
|---|---|
| `unpkg.py` | Unpack a WE `scene.pkg` |
| `untex.py` | Decode `.tex` → PNG (RGBA8888, R8, RG88, embedded PNG, LZ4) |
| `effectmap.py` | Draw every K-layer effect region/mask over the art |
| `rig.py` | v1 rig (kept for reference; tears) |
| `rig2.py` | v2: cleaned author masks + strain-limited tail/body fields + texture writer |
| `rig3_hair.py` | v3 coherent wavy hair + tendrils. Args: tip px, lag along, lag across. Used: `44 0.5 0.3` |
| `build_anim.py`, `build_anim2.py` | Scripts that rewrote the scene's effect stacks (v1, v2) |
| `hairsim.py`, `hairsim3m.py` | Time simulation of all hair effects with worst-case strain per effect and combined |
| `layout_harness.mjs` | Runs the layout script under Node with mocked WE objects across 13 resolutions |

`reports/` holds the numbers behind every calibrated value above.

---

## 7. Done (2026-11-07, later session): mandalas + §4A + §4B installed, NOT yet seen in WE

Draw order now: **BG → MandalaC → MandalaM → MandalaK → W → C → M → CB_Chest → CB_Tail → C2 → K**.
Total **108 shader passes** (was 83).

### Mandalas (`scripts/mandala.py`, `scripts/add_mandalas.py`)
- Rebuilt per user: **13 arms, no distortion.** Each arm is the Choronzon PNG itself, rigidly
  rotated, every other copy mirrored, feet glued at the exact centre (`--hub 0`), overlaps
  merged by max alpha. (21 arms was tried first; the user switched to 13.)
- `.tex` now carries a 5-level mip chain like WE's own `C.tex` (was 1 mip → shimmer when scaled).
- Installed via `add_mandalas.py`; all three decode to 4096².

### §4A Bass blue (`scripts/add_bass_blue.py`, re-runnable)
- `CB_Chest`, `CB_Tail`: full-frame crops of `recovered_original/C.png`, ~30px soft edge,
  saved in `bass_blue/`. Placed like C2, alpha 0.9, copy of `(C2) Bass` pulse.
- **Strokes grown 6px (`--grow`)**: the cyan ink has the same shape as K's lines, and K is
  on top, so without growth the blue could only ever be the thin fringe the user disliked.
- Each layer only gets the effects that move pixels inside its crop (measured from masks/
  flow maps): 5 passes each. **Re-run the script after any rig change.**

### §4B Rig v4 (`tools/rig4_face_chest.py` → `rig/v4/`, `reports/rig4_report.json`; `scripts/apply_rig4.py`)
- **`Rig: Head & Body`** now uses `rig4_body_*` (rig2 body + shoulder-stripe flex rippling
  to the corner, tube peristalsis +4px, coil slither +50%, lower-right corner heave; right-edge
  and bottom-edge fades). New parts were auto-scaled to 0.75 to keep the pass ≤ 0.3.
- **New `Rig: Face`** shake (speed 1.6, strength 0.051) on W/C/M/C2/K, map at 2520×1080:
  jaw rotation about (4340,1150) ~6px, brow lift 5px, 4 plate twitches ~3px (staggered),
  ring-eye dilation, dot ripple.
- **K only: `Blink: dot 1-4`, `Blink: ring eye`** — masked alpha pulses (speed 1.6, bounds
  0–0.15, phases 0.9 rad apart) at the top of K's stack; the dots blink in sequence and
  show the cyan/magenta copies beneath.
- Combined strain over time (`tools/rigcheck.py`): face 0.286, chest corner 0.288.
  Hair 0.455 and tail 0.349 are **unchanged from the approved scene** (same in baseline).
- Previews: `rig/v4/preview_face.gif`, `rig/v4/preview_chest.gif` (`tools/rigpreview.py`).

### Backups taken (newest last)
`backups/2026-11-07_before_mandalas_21fold/` (= pre-mandala live), `…_before_bass_blue/`,
`…_before_rig4/`.

### Not done / open
- Nothing has been opened in the WE editor yet: textures, blinks, MandalaK script all untested in-engine.
- Face highlight shimmer (white streaks) skipped: it would need a waterwaves pass on every art layer.
- Mandala spin speed, opacities and MandalaK breathing still at the handoff's guesses.

### Update: bass blue split into 5 pieces (user's cut map)
- `CB_Tail` is retired (its files are deleted). Now: **CB_Chest, CB_Tail4 (base + sweep), CB_Tail3, CB_Tail2, CB_Tail1 (tip)**.
- Regions come from the user's hand-drawn map `bass_blue/ref/user_cut_map.webp` (yellow = cuts,
  green = one stroke per tail portion, red = no blue at all). It was registered to the texture by
  template matching (`bass_blue/ref/registration.json`, s = 0.475, mirrored); the code is in
  `scripts/bass_regions.py`. The tail portions tile the tail with a soft partition. The red
  area is excluded from every piece and extended to the frame edges.
- One bass band each: Chest 0, Tail4 1, Tail3 2, Tail2 3, Tail1 4 (a kick rises up the tail).
  Bounds/exponent/amount copied from `(C2) Bass`.
- Look matched to the face blue: no stroke growth, 1.2px soft edge, alpha 0.38 (~85% of C2's 0.45).
  The earlier 6px-grown, 0.9-alpha version was rejected as too strong.
- 4–5 passes per piece; scene total **120 passes**. Backup before this: `backups/2026-11-07_before_bass_pieces/`.

### Update 2 (user feedback from the editor)
**Mandala** (`scripts/add_mandalas.py` + new `scripts/mandala_controller.js`, re-runnable):
- MandalaC / MandalaM have **no audio pulse** any more. They are now Master Leonard's audio
  ghosts, ported from `C:\Users\rockb\goat-mimic\src\leonard.c`:
  - cyan = left channel, magenta = right channel
  - louder = brighter and further out; silence = invisible
  - onset/auto-gain logic as in `audio_poll`, ~30 fps rates converted per frame
  - on each hit the ghosts jump to a random offset, and one of 4 hidden `Glitch slices N`
    shake effects (3/4/5/7 horizontal slices, `materials/masks/mandala_glitch_*`) is shown
    on all three mandalas for 90–300 ms. Constant shove = speed 0, bounds `0 0.5`, DIRECTION 1.
- The controller is bound to **MandalaK's alpha**, with tunable script properties. MandalaK
  breathing is now slower (period 4 → 6 s) and 25% dimmer: peak 0.8 → 0.6, low 0.32 → 0.24,
  bass boost 0.35 → 0.26.
- Untested in WE: whether `setMaterialProperty('strength', …)` and `effect.visible` toggling
  behave as documented in `lib.sceneScript.d.ts`. Simulated under Node with mocks only.

**Blue slices** (`scripts/bass_regions.py`, `scripts/add_bass_blue.py`):
- The bass-only bands didn't work. Now spread across the song: Chest 0–1, Tail4 2–4,
  Tail3 5–7, Tail2 8–10, Tail1 11–15, with lower audio bounds for the higher bands.
- Heavy blur (σ 6 px) and alpha 0.14, so the magenta reads through.
- Each slice fades out over 140 px toward every cut (`FADE`); the outer outline is not faded.

Scene: **130 passes, 118 active at rest** (the 12 glitch passes only run during a hit).
Backup before this round: `backups/2026-11-07_before_mandala_glitch/`.

### Update 3: spectrum mandala (13 pieces) + reptile drop shadow
User asked for these changes:
- spin 1 s faster, pulse 1 s slower, overall opacity 50% lower
- the mandala split into 13 pieces with fading sides, each pulsing black with its part of the spectrum (sound replaces the breathing; the spin stays)
- distortion borrowed from Rainbow Rings and Customizable Module Visualizer
- an Arrival-style ink splash
- keep the Leonard glitch, on the black layer only, without changing darkness
- an outer drop shadow on the reptile

**Mandala:** one layer, `MandalaK`, with one custom effect, "Spectrum mandala" (effect source in `scripts/shader/`; installed by `scripts/add_mandalas.py` into `effects/mandala_spectrum/`, `materials/effects/`, `shaders/effects/`).
- **Layer image:** `materials/mandala_canvas.tex` is transparent and canvas-sized (5120×2160, scale 1). It only sets the render size, so the splash can spread to the screen edges.
- **Mandala texture:** `Choronzon_mandala_black` is sampled through the effect's 3rd texture slot (`textures: [null, "util/noise", "Choronzon_mandala_black"]`).
- **Pieces:** one per Choronzon figure. Copy 0 points up and arms run clockwise. Side fade is `feather` 0.35 of the half-wedge.
- **Spectrum mapping (stereo-mirrored):**
  - The top arm takes bands 0-2 from both channels.
  - The right half takes the right channel and the left half the left channel, both rising in pitch toward the bottom.
  - There are 7 band groups. The controller script computes the levels (fast attack, slower release) and sends them as `arm0`..`arm12` and `bass`. Bounds run from 0.2..1.1 for the bass pieces to 0.04..0.45 for the treble pieces.
  - **Shader-compile lesson:** the first install rendered the whole screen red, which is WE's broken-shader fallback. WE's log (`wallpaper_engine/log.txt`) showed two errors. Reading `g_AudioSpectrum16Right[...]` into locals in the vertex shader failed (X3011 "initial value must be a literal expression"), and custom varyings (`v_Lv0`..) were not passed to the fragment shader. Fix: a plain pass-through vertex shader, with the levels sent as script uniforms. Check `log.txt` after every shader change.
- **Darkness:** a piece's alpha is `floor + (1-floor)*level`. The controller sets `floor`: in silence it breathes (period 7 s, was 6); with music it hands over to `musicFloor` 0.15, so only the sounding pieces get blacker.
- **Opacity:** the layer alpha is `peak` 0.3. Before, the breathing ran 0.24-0.6 plus a bass boost; it now runs 0.12-0.3.
- **Spin:** `armperiod` 47.3 s per arm. The old spin was 0.01 rad/s, about 48.3 s per arm, so this is literally "1 s faster", which you can barely see. It is a plain effect property in seconds, so it is easy to tune.
- **Rainbow Rings:** each piece scales outward with its level (`bulge` 0.1), and the whole mandala swells with the bass (`bassscale` 0.04).
- **Module Visualizer datamosh:** while bass is above `moshLevel` (0.7) of its recent peak, each ~33 ms tick has probability 0.5 of a fresh corruption. The corruption works like JPEG byte errors in 32 px blocks:
  - every block after an error, in scan order, shifts sideways and changes density
  - a few garbage blocks sit at each error
  - the result is overlaid at opacity `mosh`.
- **Leonard glitch:** whole-song onsets, ported from leonard.c, shear 3-7 slices sideways for 90-300 ms. The shift is 30 px·(1+2.5 lv) on an 800 px panel the diameter wide. It only moves pixels.
- **Ink splash:** on a strong bass onset, a blotchy smoky ring (about 9 blots, crisp leading edge) and an echo of the arms spread out over 2.6 s to about 1.7 radii, then fade. This is our own procedural ink; nothing is taken from the film.
- **Controller:** `scripts/mandala_controller.js` sets it all via `setMaterialProperty`. Sliders: peak, period, depth, musicFloor, moshChance, moshLevel, glitch, splash.
- **Fallback:** if the script fails, the mandala still spins at floor 0.6, but the pieces don't react to the music.
- **Retired** (copies in the backup): the MandalaC/MandalaM layers and files, and `masks/mandala_glitch_1..4`.

**Shadow:** `scripts/add_shadow.py` → layer `Shadow`, right under W.
- **Shape:** the silhouette is W ∪ K with holes filled. The shadow combines a contact shadow (σ7, offset ×0.45) and a soft one (σ34), cast toward the open side (−22, +18 texture px). It is clipped to the outside of the silhouette, with alpha 0.7 and a peak around 0.55.
- **Motion:** it copies W's motion effects (4 rig shakes + lens). The rig flow maps reach 40-60 px past the outline at full strength (measured), so the shadow follows the rig. `Shadow` is in the layout GROUP.

**Preview / validation:**
- **Preview:** `tools/mandala_preview.py` is a CPU port of the shader. It wrote `reports/mandala_spectrum_preview.png`: silence, music, beat (slices + mosh), splash at 0.6 s and 1.4 s, and a shadow close-up.
- **Validation:** ids unique, every reference resolves, the .tex files round-trip identical, both embedded scripts parse, and the controller was simulated in Node with a mocked engine and beat track.
- **Not seen in WE yet.** The custom shader compiles only inside WE. If the layer shows nothing, check WE's shader error log first.

**Draw order:** BG, MandalaK, Shadow, W, C, M, CB_Chest, CB_Tail4..1, C2, K. 121 active passes (was 118).

**Backup:** `backups/2026-11-07_before_mandala_pieces/` holds scene.json, project.json and the retired files.

**Update 3b (user: glitch needs more fps and to be "WAY WAY more subtle"):**
- **Leonard slices:** the shove is ×0.1 (`GLITCH_SCALE`, now about 12-39 px; it was up to ~395). Slices are thinner (2-18 of 480 panel px, was 4-48). While active, the seed and shift re-roll every frame, so it flickers instead of holding one jump. It triggers on smaller onsets (0.3, was 0.45) with a 60 ms cooldown (was 140).
- **Datamosh:** opacity is capped at 0.3 (`MOSH_MAX`), with block shifts of ±2 (was ±4). Density gain is 0.9-1.2 and garbage blocks have alpha 0.3. It re-rolls up to 60 times a second (was 30).
- **Preview:** `reports/mandala_glitch_subtle.png`.

**Update 3c (user, from the editor screenshot):**
- **Overall opacity:** `peak` 0.3 → 0.15, which halves both the minimum and the maximum.
- **Spin:** `armperiod` 47.3 → 45.8 s per arm (1.5 s faster).
- **Ink splash (smoke ring):** thickness ×0.25 (th = 0.0125 + 0.0625e, edges scaled with it) and opacity ×0.5 (ring 0.425, echo 0.3).
- **Artifact fixed:** a grey shadow smear sat at the art quad's top-left corner, which is top-right on screen with WE's flip. The Shadow texture's blur reached its top and right borders, and the lens distortion samples past the quad edge and smeared that border shadow into the corner. W does the same, but white on the light background is invisible. Shadow.png now fades to 0 within 90 px of the top and left borders and 160 px of the right border (`add_shadow.py`).

---

## 8. Handoff: current state of the mandala and shadow (2026-11-07, end of session). This section replaces Update 3, 3b and 3c where they differ.

### What the user asked for last (all done; the user hasn't checked it in WE yet)
- Mandala still far too dark → fixed. **Root cause:** `MandalaK`'s layer alpha was never applied. WE applies a layer's alpha when it draws the layer's own image, and the Spectrum mandala effect replaces that image entirely, so the alpha script's return value did nothing. The user's screenshot showed the ink at ~100% (luminance 0-42 on a 222 background). Opacity is now applied **inside the shader** (`opacity` uniform = the controller's `peak`, 0.15).
- Remove the smoke ring → the ink splash is deleted from the shader, controller and installer, and the noise texture slot is gone.
- Idle = the full mandala, not sliced → new `slice` uniform (0 = full, 1 = 13 pieces). The controller sets it to the smoothed music presence: silence shows the full breathing mandala, music shows the pieces with side fades.
- The audio-reactive version must keep spinning → the spin is g_Time-based and independent of audio, in both states. `armperiod` is 45.8 s per arm (slow by design: the user asked for "1 s faster", then "1.5 s faster").
- Remove the top-right artifact → fixed for real this time; see below. The Update 3c border-fade theory was wrong.

### Top-right corner artifact: real cause and fix
- **Cause:**
  - Every creature layer ends with the workshop "Lens distortion" (center 0.883 0.552, size 0.415, Distorsion 1 = 0.5). It is a strong barrel: `uv' = c + (uv-c)*(1 - 0.5*len2)` with `len2 = |(uv-c)/(0.7117, 1.6607)|^2`.
  - Past len2 = 2/3 the mapping folds back, so the art quad's far corners show squashed copies of whatever lies near the lens centre.
  - The art (W/K/C/M) has nothing there. The new Shadow halo does, and it showed as a grey smear at the quad's top-left corner (top-right on screen with WE's flip): texture x 0-44, y 0-168.
- **Fix:**
  - A new custom effect, **"Lens fold clip"** (`scripts/shader/lens_fold_clip.*` → `effects/lens_fold_clip/`), is appended after the lens on the Shadow layer only. It multiplies alpha by `1 - smoothstep(0.55, 0.62, len2)`.
  - Measured result: the corner smear goes from 0.356 to 0, and 100% of the real shadow is kept (all of it lies inside len2 < 0.55).
  - Installed by `scripts/add_shadow.py`. The border fade from 3c is still there and harmless.

### MandalaK now (one layer, one effect "Spectrum mandala")
- **Layer:**
  - image `models/mandala_canvas.json`: transparent 5120×2160, scale 1, centred
  - the mandala texture comes in through texture slot 2 (`[null, null, "Choronzon_mandala_black"]`)
- **Shader:** `scripts/shader/mandala_spectrum.frag` plus a pass-through `.vert.in`, installed by `scripts/add_mandalas.py`.
  - **Spin:** `armperiod` seconds per arm.
  - **Pieces:** 13, one per figure (copy 0 points up, numbered clockwise). They fade toward both sides by `feather` × `slice`.
  - **Darkness:** `floor + (1-floor)*level`.
  - **Bulge:** `bulge` × level per piece, plus a `bassscale` swell.
  - **Leonard slices:** `glitchslices`, `glitchseed`, `glitchshift`.
  - **Datamosh:** `mosh`, `moshseed`, `mosherrors`, `moshgrid` "160 68".
  - **Final alpha:** × `opacity`.
- **WE shader rules learned this session:**
  - No reading `g_AudioSpectrum16*` into locals in the vertex shader (X3011).
  - No custom varyings beyond `v_TexCoord` (they arrive undeclared in the fragment shader).
  - Use `texSample2DLod` inside branches.
  - Check `wallpaper_engine/log.txt` after every shader change. A broken shader renders the layer solid red.
- **Controller:** `scripts/mandala_controller.js`, bound to MandalaK alpha. Every frame it sets:
  - `arm0..arm12` and `bass`: the 13 levels, stereo-mirrored. The top piece takes bands 0-2 from both channels; the right half takes the right channel and the left half the left channel, both rising in pitch toward the bottom (7 groups; bounds 0.2..1.1 for bass, 0.04..0.45 for treble; fast attack, slower release).
  - `floor`: breathing in silence (period 7 s, depth 0.6), `musicFloor` 0.15 with music.
  - `slice`: the presence level.
  - `opacity` = `peak`.
  - **Leonard slices:** onsets of the whole song with a 60 ms cooldown. While active, the seed and shift re-roll every frame. Shift is ×0.1 of Leonard's (`GLITCH_SCALE`), about 12-39 px. Slices are 2-18 of 480 panel px.
  - **Datamosh:** bass above `moshLevel` 0.7 of its recent peak, re-rolled up to 60 times a second with probability 0.5. Opacity is capped at `MOSH_MAX` 0.3.
- **Script sliders:** peak 0.15, period 7, depth 0.6, musicFloor 0.15, moshChance 1, moshLevel 0.7, glitch 1.
- **Retired:** MandalaC/MandalaM (ghosts), the shake-based glitch maps, and the ink splash.

### Shadow layer (`scripts/add_shadow.py`)
- **Shape:** the silhouette is W ∪ K, filled. It combines a contact shadow (σ7) and a soft one (σ34), cast at (−22, +18) texture px and clipped to the outside of the silhouette. Alpha is 0.7 (peak about 0.55), and it fades at the texture borders.
- **Placement:** right under W, with W's motion effects (4 rig shakes + lens) plus the Lens fold clip. It is in the layout's GROUP.

### Draw order and files
- **Draw order:** BG, MandalaK, Shadow, W, C, M, CB_Chest, CB_Tail4..1, C2, K.
- **Re-run order after edits:** `python scripts/add_mandalas.py`, then `python scripts/add_shadow.py`. `add_bass_blue.py` is only needed after rig changes.
- **Preview:** `tools/mandala_preview.py` is a CPU port of the shader. It is now **stale**: it still has the splash and has no slice/opacity, so update it before relying on it.
- **Backups:**
  - `backups/2026-11-07_before_mandala_pieces/` holds the scene before this whole mandala-pieces/shadow round, plus the retired files.
  - There are no per-step backups inside the round; the scripts are re-runnable.

### Open / next
- **Unverified:** nothing from this last round has been confirmed in WE: the darkness fix, full-when-idle, the spin and the corner clip. Ask the user for a screenshot with music and one in silence.
- **Log spam that isn't ours:**
  - `Uncaught SyntaxError: Unexpected identifier 'cursor'`: the half-written `visible` script on every layer's lens_distortion effect (`CursorEvent cursor = new`). Shadow copied it from W. The value stays `true`, so it is harmless spam, but it can be removed.
  - `setTimeout is not defined`: from some other script in the scene.
- **Possible tuning:** if the mandala is now too light, raise `peak` (the script slider); if the spin feels static, lower `armperiod` (the effect property).

---

## 9. Update (2026-11-07, later): spin, ink color pickers, tail follows mouse

None of this is live until the wallpaper is reloaded in WE. `-control openWallpaper` on the already
active wallpaper does NOT reload it; the user has to re-select it.

### Mandala spin: one full turn = 13 s exactly
- `armperiod` 45.8 -> **1.0** s per arm. Full turn = 13 x armperiod (WE's `M_PI_2` is 2pi). The spin
  is g_Time-based, so it is the same idle and with music. At 45.8 it was ~0.6 deg/s, which read as
  "not spinning" under the music pieces.
- Set in `add_mandalas.py` (EFFECT_VALUES), the .frag default (range now 0.1..300) and the preview.

### Ink colors: user hex pickers "Magenta" and "Cyan" (`scripts/add_ink_colors.py`)
- Textures C, M, CB_* are now **white** (alpha kept); the color comes only from the pulse tints.
  Rebuilt from `backups/2026-11-07_before_colors_spin_tail/materials/*.tex`, so re-runs are safe.
- Each of those pulses: BLENDMODE 0 (Normal: mix(low, high, pulse)), tintlow = tinthigh =
  `{"user": key}` -> the on-screen color is exactly the picked color; audio still drives alpha.
- `magentacolor` (M) default #FF124F, `cyancolor` (C, C2, CB_*) default #30F6FF: what those
  layers showed at pulse 0.75 with the old Add-blend tints. The old reddish `colorhigh`/`colorlow`
  and M's broken glow script are gone, which also ends the `setTimeout is not defined` spam.
- Trade-off: the old Add blend also brightened the color a little on loud beats; now the color is
  constant and only the opacity pulses.

### Tail follows the mouse (`scripts/add_tail_follow.py`)
- "Rig: Tail" on all 10 layers (Shadow, W, C, M, CB_Tail1-4, C2, K) now uses the custom effect
  `tail_follow` (`scripts/shader/tail_follow.*`): an exact copy of the shake's sway for the old
  settings + a follow term along the same flow map, mixed as `sway*(1-|f|) + f`, so |total| <= 1 =
  the rig's peak. The flow map's strain at that peak is 0.284 px/px (limit ~0.3): following can't
  tear more than the idle sway.
- `follow` is set per layer by `scripts/tail_follow.js` (identical copies): cursor X over the canvas
  -> -1..1, 0.45 s exponential lag, DIR = -1 (mouse right -> tip right/up). Uses
  `input.cursorWorldPosition` so it should stay correct with WE's flip option (unverified).
- User property `tailfollow` (slider 0-100 %, default 100); 0 = plain idle sway.
- Reach is ~27 px at the tip (that flow map's limit). For a bigger swing, build a new field
  (e.g. near-rigid rotation about the tail root) and check it with tools/hairsim*.py.
- `reports/tail_follow_preview.png`: full left / rest / full right.
- **Re-run order now:** add_mandalas.py -> add_shadow.py -> add_ink_colors.py -> add_tail_follow.py
  (add_shadow copies W's stack; add_bass_blue/rig scripts rebuild the shake).

### Preview tool
- `tools/mandala_preview.py` is current again (splash removed, slice + opacity added).
  Latest sheet: `reports/mandala_preview_2026-11-07b.png`.

### Open
- **Top-right corner marks (cyan / black / magenta slivers):** the user still sees them after the
  Shadow clip. Measured: C, M, K, W and CB_* put **zero** ink into the lens fold zone, and none of
  them has stray pixels at the texture's top-left. Leading guess: they are the tips of a real hair
  spike (texture ~x4615, y82) showing as three misregistered copies (C scale 1.003, M offset -15 px).
  Needs a full-screen screenshot after the reload to pin down.
- Verify in WE after the reload: spin (13 s/turn in both modes), pickers, tail follow direction
  (also with flip), and the log for shader errors.

### 9b. Spin is now a user property (supersedes the "armperiod 1.0" note above)
- Shader uniform `g_ArmPeriod`/`armperiod` (s per arm) is replaced by **`g_TurnPeriod`/`turnperiod`
  (s per full turn)**: `angle = g_Time * 2pi / turnperiod`.
- Bound to the user property **`spinperiod`** ("Mandala spin (seconds per turn)", slider 1-600,
  default **39**). `add_mandalas.py` writes both the binding and the project.json property, so
  re-runs keep it. Moving the slider makes the mandala jump to the new angle once (angle is
  computed from g_Time, not integrated); harmless.

---

## 10. Update (2026-11-07, round 3): corner artifact, outline, tail reach, still areas

User verdict on round 2: "everything else is perfect". Backup before this round:
`backups/2026-11-07_before_outline_clip_tail2/` (scene.json, project.json, reptilian_layout.js).

### Top-right corner marks: real cause and fix
- The lens fold samples, for the quad's far corner, a band whose edge sits **5-7 px from the tail**
  at texture (3670, 983) (the gap between tail and head). At rest it is empty (so every rest-pose
  check said 0), but the tail sway / mouse follow push ink in, and the corner shows one sliver
  per ink layer: cyan, black, magenta.
- Fix: `scripts/add_fold_clip.py` appends "Lens fold clip" after the lens on **every** lensed layer
  (W, C, M, CB_*, C2, Outline, K; Shadow already had it). Measured: no layer has ink in the source
  ring the clip removes, so real art is untouched.

### Outline (`scripts/add_outline.py`)
- Layer "Outline" between C2 and K: 12 px stroke OUTSIDE the W+K silhouette (+2 px inward overlap),
  colour = K's ink #242423. 12 px = hair stroke (K hair lines: median 10, p75 15; K's own edge line 12).
- Same motion stack as C2 minus its bass pulse; added to the layout GROUP in reptilian_layout.js.
- M's magenta fringe still peeks out on one side (M is offset 15 px > 12 px stroke). By design.

### Tail follow, round 2
- New follow field `masks/tail_follow_flow` from `tools/tail_follow_field.py`: a sideways bend that
  starts at y 1150 (above the barbs, which sit ~100 px from the head) and grows to the tip;
  **52 px at the tip** (was 27), strain 0.25, zero motion on the head/body. Strength 0.108.
- Shader takes it as g_Texture3 / `followstrength`; mix = sway*(1-|f|) - f*follow (f > 0 = art +x).
- `tail_follow.js`: target = cursor X minus the tail's live world X (from layer K), full deflection
  at 30% of the canvas width; under-damped spring (omega 14, zeta 0.55): 85% in 0.17 s, small
  overshoot, output clamped to +-1.
- Preview: `reports/outline_tail_follow_preview.png`.

### Still areas -> Rig: Belly
- `tools/motion_coverage.py` maps peak displacement over all of K's effects. Before: **12.3% of the
  silhouette never moved** (lower body / chest, x 4270-5040, y 1040-2160). After: 0%.
  Maps: `reports/motion_coverage.png` (before), `reports/motion_coverage_after.png`.
- `tools/belly_field.py` -> `masks/rig5_belly_flow` + `rig5_belly_time`: radial breathing from the
  chest (4700, 1620), linear inside 450 px, ripple along the coil, mask = still zone dilated 60 px +
  blur 70 px; **9.3 px peak at strain 0.15**. Strength 0.067, speed 0.75 (~8.4 s per breath).
- `scripts/add_belly_rig.py` adds it after "Rig: Head & Body" on every layer that has that rig.

### Cost
- 163 effect passes (was ~121): Outline ~20, Belly 12.

### Full re-run order now
add_mandalas.py -> add_shadow.py -> add_ink_colors.py -> add_outline.py -> add_tail_follow.py ->
add_belly_rig.py -> add_fold_clip.py (fields first: tools/tail_follow_field.py, tools/belly_field.py).

### Not verified in WE yet
Everything in this round. `-control openWallpaper ... -playInWindow` did not open a test window this
time (it only brought up the WE UI), so nothing was screenshotted; the user reloads and reports.

---

## 11. Update (2026-11-07, round 4): outline removed, mandala opacity/blur selectors, GIF plan

### Outline removed (user: "remove the thick border")
- Layer, materials/Outline.*, models/Outline.json deleted; 'Outline' taken out of the layout GROUP.
  `scripts/add_outline.py` is kept but must NOT be in the re-run order. Backup:
  `backups/2026-11-07_before_outline_removal/`. Passes: 143.
- Everything else from round 3 stays (fold clip on all layers, tail follow v2, Rig: Belly).

### Mandala selectors (user properties, bound straight to the shader)
- `mandalaminopacity` "Mandala min opacity (%)" 0-100, default 0 -> `minopacity`
- `mandalamaxopacity` "Mandala max opacity (%)" 0-100, default 15 -> `maxopacity`
- `mandalablur` "Mandala blur (px)" 0-60, default 0 -> `blur` (canvas px)
- Shader: a piece at level L gets `mix(min, max, L)`; defaults reproduce the old `0.15 * L`.
  Blur = 12-tap golden-angle disc on the ink from the matching mip (`inkBlur`). Datamosh garbage
  scales with max opacity. `g_Opacity` is gone; the controller no longer has the `peak` slider and
  no longer sets `opacity` (it returns layer alpha 1, which is invisible anyway).
- All written by `add_mandalas.py` (binding + project.json properties). Preview tool updated
  (min/max; blur not modelled). **Shader not compiled by WE yet** - check log.txt after the reload.

### Workshop GIF (capture notes; result in §12)
- WE docs: preview GIF max **256x256 px, max 1 MB** (recommend < 500 KB; the app only requests
  128x128). So the target is a square 256x256 under 1 MB; trade frame rate / length for size.
- Capturing: `-playInWindow` no longer opens a window (it once reloaded the desktop, once did
  nothing); PrintWindow on WE's WPEDesktopDX11Window returns black. Working route: CopyFromScreen of
  the main monitor (2560x1080 at 0,0) while the desktop is clear (Win+D), wallpaper is mirrored
  there (WE flip) -> flip frames back. Square crop on the creature (right-aligned 1080x1080 in the
  unflipped frame), optional cursor sweep to show the tail follow. Build with ffmpeg
  (palettegen/paletteuse), tune fps/length to land under 1 MB.
- Scripts in the session scratchpad: we_record.ps1, desk_grab.ps1 (not part of the project).

## 12. Workshop preview GIF (2026-11-07, done)
- Installed: project `preview.gif` = 256x256, 45 frames @ 15 fps (3.0 s loop), 255 colours,
  988,971 bytes (under WE's 1 MB limit). Old one backed up to
  `backups/2026-11-07_before_gif_preview/preview.gif`. Copies: `reports/workshop_preview_256.gif`
  and a 516 KB variant `reports/workshop_preview_256_small.gif` (thresh 14, closer to WE's 500 KB tip).
- Capture: scratchpad `gif_capture.ps1` (MinimizeAll, cursor swept x 80->1450->80 over the 10 s
  capture to show the tail follow, CopyFromScreen of the left 1080x1080 of the main monitor, 512 px
  frames, windows restored after). Music was playing, so the mandala is in sliced mode.
- Encoder: `tools/make_preview_gif.py frames out.gif --start 3.5 --dur 3.0 --thresh 4 --xfade 8`.
  Shared palette + sub-threshold pixels written transparent (disposal 1). With music nothing
  repeats, so the loop is a crossfade of the last 8 frames into the frames before the start:
  seam diff 1.87 against a median frame step of 2.72 (the raw seam was 12.4). Cost: a brief ghosted
  double image of the hair/tail around frames 38-42.
- For a cleaner loop: re-capture with music paused (the idle 13-fold mandala repeats every 3.0 s at
  39 s per turn) and a cursor sweep period of exactly 3.0 s; then --xfade 0.

### 2026-11-10: preview GIF v2 (installed)
- `preview.gif` = `reports/workshop_preview_256_v2.gif`: 256x256, 30 frames @ 10 fps (3.0 s loop),
  989,129 bytes. Old one in `backups/2026-11-10_before_gif_preview_v2/`.
- With the living-creature motion nearly every pixel changes, so 15 fps stayed >= 1.3 MB; 10 fps,
  thresh 20 fits. Capture with music on and the cursor sweep period exactly 3 s (capture script
  `-Period 3`), so the arm pose matches at the seam; `--start 3.53 --dur 3.0 --fps 10 --thresh 20
  --xfade 3`. A 10 s sweep with --xfade 8 ghosted a double arm at the seam.

## 13. Performance pass (2026-11-07, done): `scripts/optimize_creature.py`

Goal (user): "consumes as few computing resources as possible while keeping the best quality".

### Result
| | Before | After |
|---|---|---|
| Effect passes, creature layers | 142 | 21 (Shadow 1, W 1, C/M/C2 2, CB_* 2 each, K 3) |
| GPU 3D load, wallpaper visible (2560x1080, 3080 Ti) | ~34 % | ~4 % idle, 18-25 % with music (sliced mandala) |
| VRAM (WE process) | 1196 MB | 633 MB (720 MB before the mandala step below) |
| Project size | 73 MB | 19 MB |

### How (details in the header of `scripts/shader/creature_warp.frag.in`)
- **One "Creature warp" pass per layer** (`effects/creature_warp`, generated from
  `scripts/shader/creature_warp.{frag,vert}.in`). A chain of WE warp passes is a composition of
  coordinate maps, so the shader walks it backwards with WE's own math for every effect (spin,
  twirl, iris, foliage sway, water waves, shake, the 5 rigs, tail follow, lens + chromatic
  aberration, fold clip, radial blur, blinks) and reads the texture once. No intermediate render
  targets, and no repeated bilinear resampling (edges are ~1 texel crisper than before).
- **Per-frame values in the vertex shader** (spin angles, iris offsets, twirl angles, Balance
  phase, blink pulses), passed as varyings.
- **Masks packed** 20 → 7 RGBA textures (`materials/masks/cw_*`, bit-exact copies).
- **Layers cropped** to the area the creature can reach: alpha dilated by the largest continuous
  warp (345 px) + the chromatic aberration reach (88 px), clipped to the lens output area. Layer
  origins move so nothing shifts; `uvrect` maps the cropped layer back to full-layer UV.
- **Support skip**: pixels whose lens sample point is outside the dilated alpha are written
  transparent without running the chain (`cw_support_{a,b,c}`).
- **Colour layers keep WE's own audio pulse** as their first pass (so audio response and the ink
  colour pickers are untouched). M's motion blur (rate 1, a no-op except for its 8-bit buffer
  capping alpha at 1) is dropped; `alphamax` 1.0 on M reproduces the cap.
- **K**: KPRE (blinks, spins, iris, guelras, radial blur) → WE's Ink edges (kept) → KPOST.
- **MandalaK**: the mandala texture only carries alpha (RGB all 0), so it is now R8
  (`masks/mandala_alpha`, 4096² + the original 4 mips copied bit-exact, shader reads `.r`):
  85 → 21 MB VRAM. The empty 5120x2160 canvas texture is replaced by WE's texture-less solid
  layer (`models/util/solidlayer.json`, same size): -44 MB VRAM.
- `tools/tex_io.py` reads/writes .tex (FreeImage PNG, RGBA8/RG8/R8, LZ4, mips). Real LZ4 when the
  `lz4` package is installed (it is now), a run coder otherwise.

### Re-running
`python scripts/optimize_creature.py` always starts from
`backups/2026-11-07_before_optimize/project` (the pre-optimisation scene, textures and masks)
and rewrites the live project. **Any effect change made in the WE editor must go into that copy
first**, or the next run loses it. Order if something upstream changes: the old `scripts/add_*.py`
/ `apply_rig4.py` against the backup copy, then `optimize_creature.py`.

### Verification done
- `tools/make_verify_project.py` builds a temporary A/B project (old chain beside new, same
  g_Time and audio); `--grid --suffix=_N` isolates the colour layers at half scale.
- B/W layers: pixel-equivalent apart from the crisper edges (blurring the new render by σ 0.5
  halves the difference; no offset).
- Colour layers (10 frames, music playing): total ink new/old within ±0.3 % for C, M, CB, C2
  on every frame.
- WE compile rules found on the way: only `g_Texture0..9` exist; functions other than `main`
  cannot read varyings (X3004, pass them as arguments); `main` cannot `return` early (X3080).

- Mandala after the R8 / solid-layer step: seen live, line art crisp at full resolution.
- The temporary verify projects were deleted. WE keeps folder handles on projects it has scanned,
  so a new verify project needs a fresh `--suffix`, or must be deleted after switching away from it.

### 13b. Texture compression (WE's "compress these textures" tips, all cleared)
- Every creature layer texture is one flat colour + alpha, so `write_layer_texture` stores it as
  **DXT5** (`tools/tex_io.py`: own encoder; colour block exact, alpha per 4x4 block with the better
  of BC3's two modes + a local endpoint search; ~98 % of pixels exact, the rest anti-aliased edge
  pixels within ~12/255 at p99.9). 3 mip levels; crop edges now snap to 16 px so mips stay
  block-aligned. Textures: ~149 MB -> 37 MB VRAM.
- **Face pack** cropped to the face box (`BOX_FACE_RECT`, shader samples through it): 2520x1080 ->
  372x544, lossless (it is only read inside BOX_FACE).
- **BG kaleidoscope**: general DXT5 (per-block principal-axis colour fit), padded 1500 -> 1504,
  4 levels. Drawn at <= 6.6 % opacity, so on-screen error <= 1.4 levels.
- TinyPNG-style PNG shrinking would not help: WE decodes PNG to RGBA8 in VRAM.
- VRAM now ~570 MB with music (was 1196 MB before all of §13).

## 14. Arm follows the mouse, v2 (2026-11-07): `tools/arm_follow_field.py`
- User: the "arm" (the spike next to the head) should reach much further, rigging the entire arm
  including the coil it grows from; ~3x the old reach.
- Bend weight = t^1.4, t = geodesic distance along the arm (spike + coil, rig2's tail region) from
  where the coil joins the body (0) to the tip (1). Carried to the surrounding empty space by
  nearest arm pixel + 40 px blur; a territory weight takes it to 0 across the gap to the head
  (20 px margins around both). Displacement is horizontal only.
- **150 px at the tip** (was 52), ink strain 0.164 (limit 0.25), max |d(dx)/dx| 0.566 in the
  transparent gap (fold at 1), head/body exactly still. Up to ~220 px would still be clean.
- Stored as **16 bits** over pack B's b/a (hi/lo; zero = 127/128, decode `(q - 32640) / 32640`):
  8 bits would step 1.2 px. Linear filtering commutes with the decode. `followstrength` 0.175.
- The tool writes `masks/arm_follow_flow16` and the new followstrength into the optimiser's source
  copy (`backups/2026-11-07_before_optimize/project`), then run `optimize_creature.py`. The old
  `tools/tail_follow_field.py` / `scripts/add_tail_follow.py` (8-bit) are superseded.
- Preview: `rig/v6/arm_follow_preview.png` (still / full lean each way); max warp is now 438 px,
  so the layer crops grew a little.

### Repo
Public: https://github.com/jgoa156/reptilian-ultrawide-wallpaper-engine, local clone
`E:\Dev\reptilian-ultrawide-wallpaper-engine`. `python tools/export_repo.py` refreshes it (wallpaper/,
scripts/, tools/, docs/, plus README/.gitignore/.gitattributes from `repo/`). Then commit and push there.
The repo is self-contained: it also holds the optimiser's source project, `recovered_original/`, the
mandala sources and the rig PNGs, and `scripts/we_paths.py` finds the WE project in any Steam library
(else the repo's `wallpaper/`). A fresh clone rebuilt every texture, shader and mask byte-identically
(README, "Set up on a new machine"). `scene.pkg` (WE's publish package) is kept by the optimiser's
cleanup but not exported.

## 15. Glitch / datamosh user properties (2026-11-07)
`scripts/add_mandala_properties.py` (was add_glitch_properties.py) adds four properties to project.json (idempotent, keeps current values):
`mandalaglitch` (bool) + `mandalaglitchstrength` (0-300 %, shown only when on), `mandaladatamosh` (bool)
+ `mandaladatamoshstrength` (0-300 %). `scripts/mandala_controller.js` reads them in
`applyUserProperties`: glitch strength multiplies the slice shove (`glitchshift`, on top of
GLITCH_SCALE 0.1); datamosh strength multiplies the mosh opacity cap (MOSH_MAX 0.3, capped at 1, so
333 % would be full). Off = no new triggers. The optimiser now injects `mandala_controller.js` into the
MandalaK alpha script, so that file is the one to edit (the source project's copy is overwritten).

## 16. Mandala spin follows the BPM (2026-11-07, verified in WE)
`scripts/mandala_controller.js` detects the tempo live and drives the spin angle itself:
- Onset envelope: positive flux of the log 16-band spectrum (bands 0-5 x2), sampled at a fixed 60 Hz
  with a zero-order hold (a frame whose spectrum did not change keeps the last flux), so no
  artificial zeros comb the envelope at 30 fps or when the audio refreshes slower than the frames.
- Every 0.5 s: last 8 s, local-mean removed, autocorrelation over 70..160 BPM, each lag scored with its
  2x/3x multiples and a log-Gaussian prior around 120 BPM, parabola for the fractional lag.
- Hold logic: first lock needs two agreeing readings with confidence >= 0.3; readings related to the held
  tempo by 2, 3/2, 4/3, 3 (and inverses) are ignored; a different tempo must win 4 checks in a row;
  6 s with no confident beat (or no music) drops the tempo.
- Spin: the script integrates `spinphase` (turns) and sets `spinscripted` 1; the shader falls back to
  g_Time / turnperiod when the script never ran. Target speed = bpm / 60 / (13 x beats per piece), or
  1 / spinperiod; it glides with a 1.5 s time constant, so nothing jumps.
- Properties (`scripts/add_mandala_properties.py`): `mandalabpmspin` (bool, default off),
  `mandalabeatsperpiece` (1-16, default 4). The script also reads `spinperiod` in applyUserProperties.
- Offline test: `tools/bpm_test/` (spectra.py makes WE-like frames from a song with ffmpeg, run.mjs runs
  the real controller in Node and fails if the spin jumps). On 6 songs it held within ~2% of the
  whole-song reference after the first 15-30 s, at 60 fps, 30 fps and 30 Hz audio at 60/144 fps.

## 17. Arm drops toward the cursor (2026-11-07, verified in WE) — REVERTED 2026-11-08, see §19
The user rejected the global drop ("the abdomen shouldn't really stretch down"). The drop and the
needle-on-mandala trigger are gone from the working copy (not yet committed); §19 replaces them.
User: the arm should also move down while following, so the tail can point at the mandala's centre
(a record needle).
- No new texture (slots 0-9 are full): the drop reuses §14's bend shape along y. In `opTail`,
  `p -= fx * vec2(f * TAIL_FOLLOW_AMP2, fd * TAIL_DROP_AMP2)`, with
  `TAIL_DROP_AMP2 = followstrength^2 * followdrop * TW / TH`. The idle sway fades with `max(|f|, fd)`.
- `followdrop` 0.8 = 120 px drop / 150 px lean at the tip; `tools/arm_follow_field.py --drop 120`
  checks lean -1/0/+1 combined with full drop (worst ink strain 0.210, min Jacobian det 0.337, 0.898
  on ink; MIN_DET 0.2 matches GAP_COMPRESS 0.8) and writes `followdrop` into the source's "Rig: Tail".
- `scripts/tail_follow.js` has `AXIS`: 0 drives `follow` (lean), 1 drives `followdown` (the optimiser
  installs a second copy). Drop target = clamp((tipY - cursorY) / (0.25 x canvas height), 0, 1), with
  the tip read from layer K (Y up in the scene). Same spring; shares the `tailfollow` property.
- `max_warp_px` counts the follow term x (1 + followdrop): max warp 438 -> 558 px, crops a bit larger.
- Preview: `rig/v6/arm_follow_preview.png` (still, lean +1, lean -1, drop only, lean -1 + drop).

## 18. Smoke behind the creature (2026-11-08, verified in WE)
User picked the "light" still mock (`mock/smoke_mock_compare.png`, made by `mock/smoke_mock.py` on a
desktop capture), creature side only. The mock's "tail stretch" was its own cut-out mask (a
straight-edged block beside the tail); the real smoke is a layer behind the creature, so it has none.
- `scripts/add_edge_smoke.py` (idempotent) writes `particles/edge_smoke.json` + `materials/edge_smoke.json`
  (genericparticle, translucent, WE asset `particle/smoke/smoke2`, rg88 8x8 sheet, `animationmode`
  randomframe) into the source and live projects, inserts layer "Smoke" right above MandalaK in the
  source scene, refreshes K's layout script and adds `edgesmoke` (bool, binds `visible`) and
  `smokeopacity` (0-200 %, `scripts/smoke_opacity.js` on the instance-override alpha) to project.json.
- Authored in creature space (bottom-right pin): boxrandom +-990 x +-40 at (4130, -180), rate 8,
  life 11-16 s, velocity x -75..5 / y 85..125, size 900-1300 x sizechange 0.33 -> 1, alpha 0.06-0.11,
  colour ~black, slow rotation, light turbulence, starttime 16 (pre-simulated, full on load).
- `scripts/reptilian_layout.js`: 'Smoke' is in GROUP, so it moves and scales with the creature (and
  WE's flip mirrors it). `optimize_creature.py` cleanup keeps particle layers' system + material.
- Mirror (2026-11-08, verified in WE): layer "SmokeFar" (`particles/edge_smoke_far.json`, velocity x
  -5..75, i.e. inward from the opposite edge) at authored (990, -180), right after "Smoke". The layout
  script's FAR list pins it bottom-left of the visible rect with the creature's scale s. Same material,
  same `edgesmoke` / `smokeopacity` bindings as "Smoke".

## 19. Arm reach: hinge + joint fan + pre-arm sink (2026-11-08, verified in WE, pushed 2026-11-09)
Committed and pushed on 2026-11-09 together with §20 and the §17 revert (the commit after `cf64404`).

### What the user asked for (in order, all still in force)
1. The arm follows **only horizontal** mouse movement. Moving far right (toward the mandala) makes it
   reach. No arm stretching/sliding (rejected), no needle-on-mandala trigger (rejected).
2. Shape "B: hinge" (`mock/arm_junction_mock.png`): the arm swings from its junction, keeping its length.
3. The junction "opens like an actual arm junction": the abdomen next to it fans out, it does NOT
   stretch down (global drop rejected, §17 reverted).
4. The pre-arm arc points DOWN, option "sink under edge" (`mock/arm_prearm_dip.png`).
5. "A full calibration to make sure it does not distort the arm too much and the rigging is well
   applied on those junctions" -> `tools/arm_calibrate.py`.
6. Last message (screenshot with a red line from the body's lower corner up across the U toward the
   arm): "its unecessary to stretch anything above that red line, focus on the arm movement".
   Nothing above that line may move. That line is `LINE` in `tools/arm_pose.py` (texture px).

### How it works (`tools/arm_pose.py` is the reference; docstring has the full description)
- Arm = 32-segment skeleton (seglen 64.17) from the joint J = (4373, 2088) to the spike tip. Pose a
  (0..1) turns segment i by `a*HINGE*(1-TAPER*i/31)*(BASE_FRAC+(1-BASE_FRAC)*smooth(i/RAMP))` around
  the base: the bend is spread over the arm's root, the tip lags. Pixel -> (segment, t, n) on the posed
  skeleton -> same (s, n) on the rest skeleton.
- Joint fan: the rest of the layer rotates around J by `-turn*s(psi)*fr(r)*w`; psi = angle from the
  coil direction, s = smoothstep(psi/lim) with lim = +-90deg + turn (s^1, not s^3: s^3 spiked stretch to
  4.24), fr fades out between FAN_R1 200 and FAN_R2 560 px.
- Sink: `q - (0, a*SINK*w*g)`, base_dst = base_src + (0, SINK). g fades horizontally (full up to
  SINK_X1 4420, none past SINK_X2 4900); w = line mask = smoothstep(signed distance below LINE / FADE).
- Rest source of an output q: w = below(q); undo sink(q, w); undo fan(., w). Both use w at the OUTPUT q.
  Rest pixels inside the rest arm band ∩ armRegion (at that source) are hidden.
- Current constants: HINGE -42deg, TAPER 0.6, BASE_FRAC 0.55, RAMP 5, FAN 200/560, SINK 70,
  SINK_X 4420/4900, LINE (5035,2107)-(3990,1553), FADE 140.
- Trigger, `scripts/tail_follow.js`: tip x from layer K, dir toward MandalaK; `d = (cursorX-tipX)*dir/w`,
  reach goal = clamp((d - P_START 0.08)/(P_FULL 0.32 - 0.08), 0, 1) * amount, spring-damped; OUT 1
  returns smoothstep(pose) into the `armpose` user value; the lean is multiplied by (1 - pose).
- `scripts/optimize_creature.py`: `armpose` combo value on every layout except KPRE (CB_Chest too),
  supports grown over a pose sweep (`arm_pose.pose_support`), defines from `arm_pose.consts(P)`.

### Calibration (latest, Python reference with the line mask)
`python -I tools/arm_calibrate.py` -> `rig/v7/arm_calibration.png` (mirrored like WE; seams red,
stretch > 1.25 yellow, > 1.5 orange; overview on top, junction close-up at full res below).
- All poses: seams 0; above the line: rest moves 0.0000 px.
- Pose 1: arm p50 1.066 / p99 1.127 / max 1.29; rest p99 1.383 / max 1.44. Pose 0.75: arm max 1.22,
  rest max 1.36.

### State: reference and live are OUT OF SYNC
- **Live WE (built 2026-11-08 22:02)** has the PREVIOUS version: hinge + fan + Y-ramp sink
  (ARM_SINK 110, ARM_SINK_X (4523, 5040), ARM_SINK_Y (1250, 1950)), no line mask. The user has seen
  this one; it moves things above the red line.
- **`tools/arm_pose.py`** has the line-mask version (above). `consts()` already emits ARM_SINK,
  ARM_LINE_P, ARM_LINE_N, ARM_FADE but NOT the sink x range yet.
- **`scripts/shader/creature_warp.frag.in`** still has the old armSink (ARM_SINK_X / ARM_SINK_Y) and an
  armFan without w. Building now would fail (ARM_SINK_X/Y undefined).

### 2026-11-09: steps 1-4 DONE, live rebuilt with the line-mask version
- `consts()` emits ARM_SINK_X; shader has `armBelow`, `armSink(q, a, w)`, `armFan(q, a, w)`.
- Calibration unchanged from the numbers above (seams 0, above the line 0.0000 px).
- `optimize_creature.py` rebuilt live (2026-11-09).
- WebGL parity vs `pose_map` (64x64 grid, poses 0.25..1): rest <= 0.004 px, arm <= 0.141 px, 1-3 of
  4096 arm/hide flags flip at region edges. Full-shader WebGL compile: error set identical to the
  previous WE-verified shader (WebGL-only strictness: int*float, undefined R_* combos), so nothing new.
  Harness generator: session scratchpad `mkharness.py` (gone next session; rebuild from this note).
- Seen in WE (2026-11-09): log clean; user: "the animation looks good for now".
- **Fix: whiter gap by the jaw.** The hidden rest-arm band (ink + 70 px both sides) erased the head's own
  drop shadow in the head-arm gap, up to a straight cut at region()'s x = 3950. The arm casts its shadow
  AWAY from the head (n < 0), so the head side (n > 0) now uses `hw_in` = measured K|W ink + MARGIN_IN 30
  (> the ~27 px tail sway, so no old-arm slivers), then the hide fades out over FEATHER_IN 30 px (ramped
  in over pose 0..0.2, no pop). Joint vertices < 6 keep the full band (ramp to 9). Applies to both the
  hide and the posed arm's band (else the moved arm would carry a strip of head shadow).
  `arm_pose.head_side_limits`, `hide_weight`; shader `segCoord(..., vec4 h)` returns (t, n, ok, soft),
  `rest.a *= 1 - pz.w`. Calibration unchanged; old-arm K ink left visible 0 px at poses 0.4 / 1;
  gap row profile now 201 209 215 220 222 (was 209 -> 222 cut). WebGL parity: same numbers, hide weight
  4-7/4096 points > 0.05 off at band edges; no new compile errors. Live rebuilt.
- **Fix 2 (user recording 2026-11-09 03:16): ghost of the spike tip** at its rest spot when the arm
  leaves/returns. The band tests ran on pre-rig points, but the chain draws after the rigs (mouse lean up
  to ~150 px x (1 - pose), sway ~27 px), so mid-reach the leaned rest tip left the narrow head-side band.
  Now the tests run on what the chain really reads: `hide` = `armRestBand(walkRigs(rG))` (hard + fade),
  moved arm drawn only if `armRestBand(walkRigs(src)).x` (material); the moved arm is FOUND through the
  full band (hw both sides). `armRestBand` is generated by `arm_pose.glsl`; reference `pose_map` arm =
  wide posed band & narrow material band at src (rigs still). optimize_creature is now ~12 min.
  WebGL caught a 5-component `vec4(src, arm, 0, 0)` before WE did: always run the compile diff.
- **Fix 3: thin straight light line through the lower body (45 deg, texture (4770,1987)-(4872,2095)),
  present at rest too, older than §19.** `Rig: Belly` time map wrapped (`np.mod((X-Y)/1400, 1)`, step
  190/255 at x - y = 2800; rule 6). `tools/belly_field.py` now ramps once across the moving zone
  (`time_span`); the source project's `masks/rig5_belly_time.tex` was rewritten from the existing flow
  map's footprint only (scratch fix_belly_time.py; flow/amplitude/strength unchanged; backup in
  `backups/2026-11-09_before_belly_time_fix/`). Max step now 1/255; the ripple is ~half as fast across
  the body (wave ~2700 px). NOTE: belly_field.py itself writes to the LIVE project and reads the live
  scene for its still zone: do not re-run it against the optimised live scene.
- **Fix 4: teeth gaps read as bright white slots.** They are the creature's only 8 enclosed holes
  (x 4139-4271, y 1066-1285; background shows through) and `add_shadow.py` filled holes, so no shadow
  fell in them. Now holes stay open (edge pixels still forced solid as before): only the mouth changes
  (30 px elsewhere, max 27/255). Written to the source project's `materials/Shadow.tex` only (scratch
  shadow_teeth.py); backup `backups/2026-11-09_before_teeth_shadow/`. Live rebuilt.
- **Torso motion today** (source scene, peak per rig): torso x >= 4300, y 800-2160: median 6 px, p90 10 px
  (Head & Body 2-7, Belly 4-9); hair/head median 12, p90 35. Belly runs at strain 0.15 of 0.3.
  motion_coverage.py needs `load_mask` -> tex_io.read_tex and PROJ -> the source project now.
- **Waiting on:** user re-selects the wallpaper (tip ghost, body line, jaw gap, teeth), picks torso/next
  effects, then step 6.
- FPS: WE's own cap is `"fps": 30` in wallpaper_engine/config.json (GPU ~4 % idle at 30); not a GPU limit.

### Next steps (original list)
1. `consts()`: add `#define ARM_SINK_X vec2(sink_x[0], sink_x[1])`.
2. Shader:
   ```glsl
   float armBelow(vec2 q) { return smoothstep(0.0, 1.0, dot(q - ARM_LINE_P, ARM_LINE_N) / ARM_FADE); }
   vec2 armSink(vec2 q, float a, float w) {
       float g = 1.0 - smoothstep(ARM_SINK_X.x, ARM_SINK_X.y, q.x);
       return q - vec2(0.0, a * ARM_SINK * w * g);
   }
   ```
   armFan gets a `float w` parameter and `th = -turn * s * fr * w`. In main:
   `vec2 q = uvG * ARM_PX; float w = armBelow(q); rG = armFan(armSink(q, a, w), a, w) / ARM_PX;`
   (rR/rB stay rG + (uvR - uvG) etc.; the posed block's `armPose(uvG*ARM_PX, rG*ARM_PX, ...)` is unchanged).
3. `python -I tools/arm_pose.py`, `python -I tools/arm_calibrate.py`, `python -I scripts/optimize_creature.py`
   (rebuilds live, ~2 min).
4. GPU checks (scratchpad harness `glsltest/`: index.html, frag.txt, ref.json; WebGL2, RGBA32F target,
   64x64 grid over box [3300, 1300, 4950, 2160]): compile test, then parity vs a ref.json regenerated
   from the current `pose_map`. Last passing parity (previous version): rest <= 0.007 px, arm <= 0.13 px.
   The scratchpad is session-only; rebuild the harness if it's gone.
5. User re-selects the wallpaper in WE. Then check `D:\steam\steamapps\common\wallpaper_engine\log.txt`
   (`grep -a`) for shader errors: WebGL does NOT catch HLSL-only errors.
6. After "looks right, push it": README (arm reach: horizontal trigger, hinge, joint fan, sink, line
   limit; drop and needle gone), this handoff, `python -I tools/export_repo.py` (include
   `mock/arm_slide_stroke.npz`, which arm_pose.py reads; consider adding .npz to the export mock
   filter), commit (includes the §17 revert) and push.

### Gotchas learned this round
- WE compiles GLSL to HLSL ps_5_0: no 2-argument `atan` (it gave the red "error loading texture"
  block). Use `acos(dot)` plus a cross-product sign; ARM_COIL is a vec2.
- Tuning history: root-chain Hermite folded (dropped); global drop stretched the body (rejected);
  sink Y-ramp stretched the abdomen wall to 4.2; the line-mask fade band alone gave 3.16, fixed by the
  sink's horizontal fade + spreading the bend over the root (BASE_FRAC, RAMP).
- Bash heredoc patch scripts turn `\n` into real newlines; edit f-strings with `\n` by hand.

## 20. Living creature (2026-11-09, verified in WE, pushed)
Seen in WE 2026-11-09: log clean, user: "Looks right, push it". The mandala eye's on/off switch was
added on the same day (below).
User: "all ideas are good ... proceed with everything you suggested and yes double the breathing"; the
mandala-centre eye last (own procedural eye, not the Tool venue). Step 6 of §19 (push) waits for
"looks right, push it" and now covers this too.

All per-frame values come from ONE script, `scripts/creature_driver.js`, bound to "bass" of
K's "Creature warp (KPOST)"; it sets the others on every creature pass with
`getEffect('Creature warp (LAYOUT)').setMaterialProperty` (like the mandala controller).
New float uniforms: bass, loud, beat, jaw, blink, lookx, looky; per-layer constant `split`
(layer offset xy + scale-1 from K, full uv; from the source scene in `uber()`).
Tuning constants are `#define`s at the top of `creature_warp.frag.in` (after @@CONSTANTS@@).

| Effect | Where | Notes |
|---|---|---|
| Breathing x2 | opBelly, BREATH_GAIN 2 | rigcheck combined 0.302 -> 0.319 (chest corner, HB-driven) |
| Bass heave | opBelly, + HEAVE_GAIN 0.3 x bass, no wave | peak 2.3x belly: ~0.34 briefly |
| Muscle ripple | opBelly, RIP_* | `tools/torso_ripple.py`: stripe orientation from K's structure tensor, cubic fit (20 consts), slide T*g (stripe tensor x fixed down-right dir, no sign ambiguity); 3 px (x1.5 loud), 420 px wavelength; strain 0.13 max |
| Weight shift | opLean in walkRigs | 0.016 rad about (5040,2160), 20 s; x fades at right edge, y at bottom (320 px); 25 px at head, strain 0.145 |
| Jaw snap | opJaw in walkRigs (R_FACE) | hinge (4400,1065), mouth line + below-snout band + neck/top/radius limits, 80 px feathers; 0.05 rad; ink strain 0.56 at the 1.15 overshoot (15 px feathers tore the tendril roots) |
| Eyes look | eyeMod in spinStep (S1-S4) + iris offsets I1/I2 | 6 / 3 / 4 px, profile (1-r2)^2 |
| Big-eye blink | eyeMod (S1, S2) | vertical squash to 1/5; 2.5-7 s, 20 % double |
| Gill flare | walkMid E_F1 | radial about BLUR_CENTER, 6 % x loud x guelras mask |
| Hair bristle | opHair | +20 % x loud |
| Colour split | main(), uv -= beat*1.5*(off + ds*(uv-0.5)) | M grows ~22 px + scale on hits |
| Mouth smoke | layer MouthSmoke (after K) | `scripts/add_living_creature.py` + `scripts/mouth_smoke.js` (instance rate, reads `shared.creaturePuff`); in the layout GROUP |
| Mandala eye | `mandala_spectrum.frag` eye() | almond window + halo, double lid + 13 spikes, ringed iris turning with the spin, slit pupil widening with bass, blink; look/blink from `mandala_controller.js` |

User properties (add_living_creature.py): `creaturemusic`, `mandalaeye`, `mandalaeyeopacity` (35).
**2026-11-10: the mandala eye is SHELVED** (user: "completely disable the eye in the mandala for now,
we're not done with the design yet"). `EYE_ENABLED = false` in mandala_controller.js, the scene's
`eye` constant is 0, and add_living_creature.py removes `mandalaeye`/`mandalaeyeopacity` from
project.json (their definitions are kept there as a comment). The shader code and eyeUpdate() stay.
To bring it back: restore the two PROPS, set EYE_ENABLED true, `eye` 1.0 and re-bind `eyeopacity`
in optimize_creature.py, and put it back in the README. Verified in WE and pushed 2026-11-10.
**2026-11-10: mouth smoke thinned** (user: "too dense"): rate 36 -> 16, alpha 0.22-0.38 -> 0.06-0.13,
size 70-140 -> 50-110, maxcount 48 -> 24, grows 0.5 -> 2.0 (was 0.4 -> 1.6). It is the jaw-snap puff
on hard bass hits only, not continuous breath. Backup `backups/2026-11-10_before_smoke_eye_off/`.
(Before shelving:) `mandalaeye` is the eye's master switch. It is read by mandala_controller.js's applyUserProperties, which sets the shader's `eye` constant (left unbound in the scene). When it is off, the shader skips eye() and the script skips eyeUpdate(). Turning it off parks the eye centred and open.
`max_warp_px` adds the new motions (crop/support margins), reading the template's #defines.
Checks: WebGL strict compile of all 7 layouts OK (scratch mkfrag.py makes a strict variant: defined()
for feature macros, int literals -> float); arm parity unchanged. Numpy mirror: scratch living_check.py.
Backups: `backups/2026-11-09_before_living_creature/` (source scene.json, live project.json).
Re-run order now: ... add_edge_smoke.py -> add_living_creature.py -> optimize_creature.py.
