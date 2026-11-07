"""Workshop preview GIF: 256x256 (WE's maximum), under 1 MB (WE's limit), seamless loop.

Input: frames captured from the desktop (mirrored by WE's flip option, so they are flipped back),
512x512 crops of the left 1080x1080 of the main monitor, top TOPCUT px = taskbar strip.

Why a custom encoder: the mandala spins over the whole background, so nearly every pixel shifts
slightly between frames and ffmpeg's GIFs came out at 1.05-6.5 MB. Here every frame is mapped
to ONE shared palette and any pixel whose colour moved less than --thresh (RGB distance) keeps the
previously shown value and is written as transparent; LZW packs those runs almost for free.
Real motion still updates; only sub-threshold jitter is dropped. Every --keyframe frames the
whole frame is refreshed so drift can't build up.

Loop: with music on, the pulses and mandala pieces never repeat (best frame-pair seam in a 10 s
capture was ~6x a normal frame step), so --xfade N blends the clip's last N frames into the frames
just before its start. The window is centred on the cursor sweep's turn so the tail lines up.
Usage: python tools/make_preview_gif.py <frames_dir> <out.gif> [--start 3.5] [--dur 3.0]
       [--fps 15] [--thresh 14] [--keyframe 0] [--colors 255] [--xfade 8]
"""
import argparse
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

SRC_FPS = 15
TOPCUT = 15          # taskbar strip at 512 px scale


def load(frames_dir, start, dur, fps, xfade=0):
    files = sorted(Path(frames_dir).glob("f*.png"))
    n_out = int(round(dur * fps)) + xfade
    out = []
    for k in range(n_out):
        t = start + k / fps
        i = min(int(round(t * SRC_FPS)), len(files) - 1)
        im = Image.open(files[i]).convert("RGB")
        w, h = im.size
        side = h - TOPCUT
        im = im.crop((0, TOPCUT, side, h))          # creature hugs the left edge (mirrored)
        im = ImageOps.mirror(im)                     # back to WE's default orientation
        out.append(im.resize((256, 256), Image.LANCZOS))
    if not xfade:
        return out
    # crossfade loop: play F[c..c+L), and blend the last c frames toward F[0..c), so the clip's
    # end runs straight into its start (with music nothing repeats exactly, so no frame pair matches)
    c, L = xfade, len(out) - xfade
    res = []
    for k in range(L):
        f = out[k + c]
        if k >= L - c:
            w = (k - (L - c) + 1) / (c + 1)
            f = Image.blend(f, out[k - (L - c)], w)
        res.append(f)
    return res


def encode(frames, out, fps, thresh, keyframe, colors):
    # shared palette from a mosaic of all frames
    cols = 8
    rows = (len(frames) + cols - 1) // cols
    mosaic = Image.new("RGB", (256 * cols, 256 * rows))
    for i, f in enumerate(frames):
        mosaic.paste(f, ((i % cols) * 256, (i // cols) * 256))
    pal_img = mosaic.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE)
    pal = np.array(pal_img.getpalette()[:colors * 3], np.float32).reshape(-1, 3)
    TRANS = colors                                   # transparent index (colors <= 255)
    full_pal = list(pal.astype(np.uint8).ravel()) + [0, 0, 0] * (256 - colors)

    shown = None
    out_frames = []
    for k, f in enumerate(frames):
        q = np.asarray(f.quantize(palette=pal_img, dither=Image.Dither.NONE))
        if shown is None or (keyframe and k % keyframe == 0):
            idx = q.copy()
            shown = q.copy()
        else:
            d = np.linalg.norm(pal[q] - pal[shown], axis=-1)
            changed = d > thresh
            idx = np.where(changed, q, TRANS).astype(np.uint8)
            shown = np.where(changed, q, shown)
        im = Image.fromarray(idx.astype(np.uint8), "P")
        im.putpalette(full_pal)
        out_frames.append(im)
    dur_ms = int(round(1000 / fps))
    out_frames[0].save(out, save_all=True, append_images=out_frames[1:], duration=dur_ms, loop=0,
                       disposal=1, transparency=TRANS, optimize=False)
    return Path(out).stat().st_size


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames"); ap.add_argument("out")
    ap.add_argument("--start", type=float, default=3.5)
    ap.add_argument("--dur", type=float, default=3.0)
    ap.add_argument("--fps", type=float, default=15)
    ap.add_argument("--thresh", type=float, default=14)
    ap.add_argument("--keyframe", type=int, default=0)
    ap.add_argument("--colors", type=int, default=255)
    ap.add_argument("--xfade", type=int, default=8)
    a = ap.parse_args()
    frames = load(a.frames, a.start, a.dur, a.fps, a.xfade)
    size = encode(frames, a.out, a.fps, a.thresh, a.keyframe, a.colors)
    print(f"{a.out}: {len(frames)} frames @ {a.fps} fps, thresh {a.thresh}, {a.colors} colours -> {size} bytes ({size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
