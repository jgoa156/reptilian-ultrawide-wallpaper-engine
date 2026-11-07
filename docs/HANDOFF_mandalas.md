# Handoff: Choronzon mandalas → Reptilian wallpaper

Status as of 2026-11-07. **Stopped before touching the live scene.** Nothing in the
Wallpaper Engine project folder has been modified yet.

## Goal (user's request)
- Turn each Choronzon ink layer (cyan, magenta, black) into an 8-sided mandala:
  mirror the figure and join the copies at the centre.
- Black mandala: pulses on a regular rhythm and is more visible than the others
  ("like mandalas on walls during acid trips").
- All of them spin like the existing kaleidoscope (layer `BG`).
- Audio reactive, the same way the reptilian layers are.

## Locations
- Working folder: `C:\Users\rockb\OneDrive\Área de Trabalho\Reptilian Ultrawide 4K`
- Live WE project: `D:\steam\steamapps\common\wallpaper_engine\projects\myprojects\reptilian_ultrawide_5120`
  (`scene.json` has 6 objects, in draw order: BG, W, C, M, C2, K.
  It already includes the wavy-hair edits.)
- Backup of live scene + project taken just now: `backups/2026-11-07_before_mandalas/`

## Done
1. **Line extraction**: `bw_threshold.py` turns `Choronzon.webp` (703×797) into
   `Choronzon_{black,cyan,magenta}.png`. Each is a 2812×3188 single-colour ink layer
   with anti-aliased alpha, matching the style of the reptilian layers.
   Defaults: `--scale 4 --sigma 8 --bias 18 --soft 4 --smooth 2.5`.
2. **Mandalas**: `scripts/mandala.py` produces `Choronzon_mandala_{black,cyan,magenta}.png`
   (4096×4096 RGBA).
   - The figure is cropped to its bounding box, then polar-warped into 45° wedges.
   - Alternate wedges are mirrored.
   - Heads point outward and the feet meet at a small solid hub (`--core 0.025`).
   - Checked by eye at 1600px. The 4096 outputs were generated but not viewed.
3. **Layout script**: `scripts/reptilian_layout.js` has been edited locally only.
   - `BACKGROUND` is now a list: `['BG','MandalaC','MandalaM','MandalaK']`.
   - Each of those layers is centred and scaled with screen height, and keeps its
     authored offset from the canvas centre (2560,1080).
   - The live copy embedded in layer K's `visible.script` is still the old version.
4. **Installer, written but NOT run**: `scripts/add_mandalas.py`.
   - Writes `materials/Choronzon_mandala_*.tex`, `.tex-json`, a material json and a
     `models/*.json` for each colour.
   - Inserts `MandalaC`, `MandalaM`, `MandalaK` right after BG, i.e. behind the
     creature, since W is the creature's light-grey fill.
   - Re-running it replaces existing `Mandala*` layers instead of duplicating them.
   - Each mandala is 3000px across (same as BG), centred, with a copy of BG's spin
     effect (speed 0.01).
   - **MandalaC** (alpha 0.36): copy of C's audio pulse `(C) Música`
     (AUDIOPROCESSING 1, PULSEALPHA). It is invisible when there's no music, same as C.
   - **MandalaM** (alpha 0.66): offset (-15,-2) and scale ×1.007 for a chromatic
     misregistration, like M. Gets a copy of M's audio pulse, including the
     `colorhigh`/`colorlow` user bindings.
   - **MandalaK**: has no pulse effect. Its `alpha` is bound to a SceneScript.
     - Regular cosine breathing, 4s period, depth 0.6, peak 0.8.
     - Plus a bass boost from `engine.registerAudioBuffers(engine.AUDIO_RESOLUTION_16)`,
       averaging bands 0–2, with fast attack and slow release.
     - It's a script and not the pulse effect because a PULSEALPHA audio pulse goes
       to zero alpha in silence, which would defeat "always visible + pulsing".
   - Refreshes K's embedded layout script from `scripts/reptilian_layout.js`.
   - All new ids start at the current max + 1 (current max is 939).

## Not verified / risks
- **.tex format**: `write_tex` embeds the PNG using FreeImage format 13: 1 image,
  1 mip, uncompressed header, with TEXI = fmt 0, flags 2, w,h,w,h, 0xFFFFFFFF.
  - This is modelled on how `materials/C.tex` stores its PNG. That file has 5 mips;
    ours has 1.
  - Not yet loaded in WE. Check it first by round-tripping through `untex.py`
    (from an earlier session's tools), then by opening the project in the WE editor.
  - Fallback: import the PNGs through the WE editor, which compiles its own .tex.
- **SceneScript API**: `engine.registerAudioBuffers`, `audio.average`,
  `engine.runtime` and the `scriptproperties` on an alpha binding are written from
  memory of the WE API. They have not been tested in the engine.
- **Spin**: 0.01 matches BG exactly. That's slow, about 10 minutes per turn.
- **Visual balance**: opacity and layer order are educated guesses, based on a rough
  Python composite. Nothing has been checked in the actual wallpaper.

## Next steps
1. Run the installer: `python scripts/add_mandalas.py` (from the working folder).
2. Open the project in the Wallpaper Engine editor.
   - Confirm the 3 textures load and the layers spin.
   - Confirm MandalaK breathes, and that C/M react to music.
   - Check the editor log for script errors.
3. Tune in the editor: opacities, the MandalaK script properties (base, depth, period,
   bass boost), and spin speed. Consider opposite spin directions per layer for more
   motion.
4. Roll back if needed: copy `backups/2026-11-07_before_mandalas/scene.json` over the
   live one, then delete `materials/Choronzon_mandala_*` and
   `models/Choronzon_mandala_*.json` in the live project.

## Leftover files you can delete
`figure.jpg`, `figure_bw.png`, `figure_lines.png`, `1_bw.png` (early threshold tests).

---

## Amendment (2026-11-07, from the animation session)

This plan now runs together with the animation plan in **`HANDOFF_animation.md`**. Read
that first: it has the live scene's layer and effect state, the strain rules for any
motion, and the tools. Neither plan has been started. Use one combined order so the two
don't collide in `scene.json`.

### Risks above: updates
- **.tex check:** `untex.py` is now in `tools/untex.py` in this folder. Run
  `python -I tools/untex.py <live project>/materials <out_dir>` after the installer and
  confirm each `Choronzon_mandala_*.tex` decodes to 4096×4096. The editor test is still
  needed.
- **SceneScript API: confirmed against WE's own definitions.**
  - File: `D:\Steam\steamapps\common\wallpaper_engine\ui\dist\monaco\autocomplete\lib.sceneScript.d.ts`.
  - `engine.AUDIO_RESOLUTION_16` exists, and the buffers expose `left`, `right` and
    `average`.
  - Lifecycle events: `init`, `update`, `resizeScreen`, `applyUserProperties`.
  - Note: `resizeScreen` is not called on first load, so run layout from `init` too.
    The layout script already does this.
- **Installer and the layout script:**
  - `add_mandalas.py` replaces only K's `visible.script` text. It keeps the existing
    `scriptproperties` (`heightPercent: 90`) and computes new ids from the live max.
  - Whatever is in `scripts/reptilian_layout.js` when it runs is what goes live. Make
    any `GROUP` edits there first (see step 3 below).

### Combined order of work
1. **Mandalas** (this file, "Next steps" 1–4).
   - Take a fresh backup first: the `before_mandalas` backup equals the live scene now,
     but won't after other edits.
   - Mandala layers go right after BG, behind the creature. They aren't art layers, so
     they get no motion-rig effects.
2. **Test in the WE editor**, then tune opacities, MandalaK breathing and spin.
   - Wallpaper Engine runs elevated on this PC, so Claude can't drive the editor. The
     user checks it and records a clip if something looks off.
3. **More blue on the chest and tail** (`HANDOFF_animation.md` §4A). New full-frame cyan
   crop layers go above M.
   - Add their names to `GROUP` in `scripts/reptilian_layout.js`, then re-embed the
     script into K's `visible.script`. Re-running `add_mandalas.py` would also do it.
   - Their names must not start with `Mandala`: the installer replaces `Mandala*` layers.
4. **Animate every inch** (`HANDOFF_animation.md` §4B):
   - The face first.
   - Then the chest toward the lower-right corner.
   - Strain ≤ 0.3 combined, and prefer extending the 3 existing rig passes over adding
     effects.

### Performance note
- The scene is at **83 shader passes**. The three mandalas add about 6–9 (spin + pulse
  each).
- Each new art-layer effect costs about 4–5 more (one per art layer).
- If the editor stutters, the first levers are:
  1. Fewer detail effects on C2 (it's only the bass fringe).
  2. Giving the new chest/tail crop layers only the effects that touch their region.
