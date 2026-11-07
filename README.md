# Psychedelic Reptilian (Animated) — Ultrawide 5120×2160

An audio-reactive [Wallpaper Engine](https://www.wallpaperengine.io/) scene for ultrawide screens.
It works at any resolution: the creature is laid out by script, so it stays 90 % of the screen
height, pinned to the bottom-right corner (WE's flip option mirrors it to the left).

![preview](wallpaper/preview.gif)

## What moves
- **The creature**: hair, tendrils, tail, head, body, belly and face are driven by painted motion
  rigs (flow + time maps). The eyes spin and wander, the gills sway, the eyelids blink, and a
  lens + chromatic aberration pass sits on top.
- **The tail follows the mouse** horizontally, on a slightly springy curve.
- **Music**: the magenta and cyan ink layers pulse with the audio. Five blue bands across the chest
  and tail light up one frequency band each, and an extra cyan layer reacts to the bass.
- **Spectrum mandala** (the 13-fold Choronzon mandala behind the creature) turns slowly and
  breathes when there is no sound. With music it splits into 13 pieces, one per frequency band,
  and adds a bass swell, datamosh frames and beat glitches.

## User properties
| Property | Default |
|---|---|
| Magenta / Cyan (ink colours) | `#FF124F` / `#30F6FF` |
| Tail follows mouse (%) | 100 |
| Mandala spin (seconds per turn) | 39 |
| Mandala min / max opacity (%) | 0 / 15 |
| Mandala blur (px) | 0 |

## Install
Copy `wallpaper/` into `steamapps/common/wallpaper_engine/projects/myprojects/<any name>/` and
pick it in Wallpaper Engine (or open its `project.json` from the editor).

## Performance
Each creature layer renders in one generated shader pass ("Creature warp") that reproduces the
whole chain of built-in effects it replaced. The chain is walked backwards as a composition of
coordinate maps, followed by a single texture read. The layers are also cropped to the area the
creature can reach.

| | Before | After |
|---|---|---|
| Effect passes (creature) | 142 | 21 |
| GPU 3D load, wallpaper visible (2560×1080, RTX 3080 Ti) | ~34 % | ~4 % silent, 18–25 % with music |
| VRAM (Wallpaper Engine process) | 1196 MB | 633 MB |
| Project size | 73 MB | 19 MB |

Details: [`docs/HANDOFF_animation.md`](docs/HANDOFF_animation.md) §13 and the header of
[`scripts/shader/creature_warp.frag.in`](scripts/shader/creature_warp.frag.in).

## Repository layout
| Folder | Contents |
|---|---|
| `wallpaper/` | The Wallpaper Engine project: scene, textures, masks, effects, generated shaders |
| `scripts/` | The pipeline that built the scene (`add_*.py`, `apply_rig4.py`, `optimize_creature.py`), the scene scripts (`*.js`) and the shader sources (`scripts/shader/`) |
| `tools/` | Rig generators, `.tex` reader/writer (`tex_io.py`), preview and verification helpers |
| `docs/` | Working notes: how the rig, the mandala and the optimization were built and verified |

The scripts are working tools, not a packaged build. They expect the author's local folders: the
WE project path in `scripts/add_mandalas.py`, plus the source art and the pre-optimization project
copy that `optimize_creature.py` reads, neither of which is in this repo. Python 3.13 with numpy,
scipy, Pillow, OpenCV and (optionally) `lz4`.

## Credits
- **Artwork**: the Reptilian illustration by [death.yon](https://www.instagram.com/death.yon).
- **Chromatic Aberration (+Audio Response)** by fug4life, Steam Workshop
  [2423877731](https://steamcommunity.com/sharedfiles/filedetails/?id=2423877731). The effect
  files in `wallpaper/effects/workshop/2423877731` and `wallpaper/shaders/workshop/2423877731`
  are the author's, bundled unmodified for the background layer.
- **Lens distortion** by Gariam, Steam Workshop
  [2811235087](https://steamcommunity.com/sharedfiles/filedetails/?id=2811235087). The lens and
  chromatic-aberration math in the Creature warp shader reimplements that effect.
- Built-in Wallpaper Engine effects (spin, twirl, iris, foliage sway, water waves, shake, pulse,
  radial blur, edge detection) are reproduced from WE's own shader math.
