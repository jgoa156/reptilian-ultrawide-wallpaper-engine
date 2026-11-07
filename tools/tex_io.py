"""Read and write Wallpaper Engine .tex files (the subset this project uses).

read_tex(path) -> numpy array (H, W, C) uint8, mip 0, cropped to the image size:
  * FreeImage blobs (imported PNG/JPG, e.g. materials/C.tex)  -> RGBA
  * fmt 0 RGBA8888, fmt 8 RG88, fmt 9 R8 (raw or LZ4-block compressed) -> 4, 2 or 1 channels
read_tex_levels(path) -> every mip level, largest first
write_raw_tex(path, pixels, mips=()) writes fmt 0/8/9 (by channel count 4/2/1), LZ4-compressed
  (real LZ4 when the `lz4` package is installed, literal-only blocks otherwise; WE reads both),
  flags 2 (clamp UVs), the same header our earlier mask writers used.
"""
import io
import struct
from pathlib import Path

import numpy as np
from PIL import Image

try:
    import lz4.block as _lz4
except ImportError:          # pragma: no cover
    _lz4 = None


def _lz4_decode(src, size):
    if _lz4 is not None:
        return _lz4.decompress(src, uncompressed_size=size)
    dst = bytearray()
    i = 0
    while i < len(src):
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        dst += src[i:i + lit]; i += lit
        if i >= len(src):
            break
        off = src[i] | (src[i + 1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255:
                    break
        ml += 4
        st = len(dst) - off
        for k in range(ml):
            dst.append(dst[st + k])
    return bytes(dst[:size])


def _lz4_len(out, n):
    while n >= 255:
        out.append(255); n -= 255
    out.append(n)


def _lz4_encode(raw, period=4, min_run=32):
    """LZ4 block. With the lz4 package: real LZ4 HC. Without it: a run coder that is enough for
    masks (long stretches where every byte equals the one `period` bytes back, e.g. empty RGBA
    pixels or a constant flow value) - those become offset-`period` matches, the rest literals."""
    if _lz4 is not None:
        return _lz4.compress(raw, mode="high_compression", compression=12, store_size=False)
    a = np.frombuffer(raw, np.uint8)
    n = len(a)
    same = np.zeros(n, bool)
    same[period:] = a[period:] == a[:-period]
    # runs of `same`
    d = np.diff(np.concatenate(([0], same.view(np.int8), [0])))
    starts, ends = np.nonzero(d == 1)[0], np.nonzero(d == -1)[0]
    out = bytearray()
    lit_from = 0
    limit = n - 12                      # LZ4: last match must end >= 5 bytes before the end, start >= 12
    for s, e in zip(starts, ends):
        s = max(s, lit_from, period)
        e = min(e, n - 5)
        if e - s < min_run or s > limit:
            continue
        lit = s - lit_from
        ml = e - s
        tok = (min(lit, 15) << 4) | min(ml - 4, 15)
        out.append(tok)
        if lit >= 15:
            _lz4_len(out, lit - 15)
        out += raw[lit_from:s]
        out += struct.pack("<H", period)
        if ml - 4 >= 15:
            _lz4_len(out, ml - 4 - 15)
        lit_from = e
    lit = n - lit_from
    out.append(min(lit, 15) << 4)
    if lit >= 15:
        _lz4_len(out, lit - 15)
    out += raw[lit_from:]
    return bytes(out)


def read_tex(path):
    return read_tex_levels(path)[0]


def read_tex_levels(path):
    """Every mip level, largest first (same decoding as read_tex)."""
    d = Path(path).read_bytes()
    p = 0

    def u32():
        nonlocal p
        v = struct.unpack_from("<i", d, p)[0]; p += 4
        return v

    def tag():
        nonlocal p
        e = d.index(b"\0", p); t = d[p:e].decode(); p = e + 1
        return t

    tag(); tag()
    fmt, flags, tw, th, iw, ih, _ = [u32() for _ in range(7)]
    tb = tag(); u32()
    fif = u32() if tb in ("TEXB0003", "TEXB0004") else -1
    if tb == "TEXB0004":
        u32()
    levels = []
    for m in range(u32()):                   # mip count
        w, h = u32(), u32()
        lz, dsz = (u32(), u32()) if tb != "TEXB0001" else (0, 0)
        n = u32(); blob = d[p:p + n]; p += n
        if lz:
            blob = _lz4_decode(blob, dsz)
        if fif != -1:
            a = np.asarray(Image.open(io.BytesIO(blob)).convert("RGBA"))
        elif fmt in (0, 8, 9):
            a = np.frombuffer(blob, np.uint8).reshape(h, w, {0: 4, 8: 2, 9: 1}[fmt])
        else:
            raise ValueError(f"unsupported fmt {fmt} in {path}")
        mw, mh = max(iw >> m, 1), max(ih >> m, 1)
        levels.append(a[:min(mh, a.shape[0]), :min(mw, a.shape[1])].copy())
    return levels


def write_raw_tex(path, pixels, mips=()):
    """pixels: mip 0; mips: the smaller levels (each half the previous), stored after it."""
    levels = []
    for a in (pixels, *mips):
        a = np.asarray(a)
        levels.append(a[..., None] if a.ndim == 2 else a)
    h, w, c = levels[0].shape
    fmt = {4: 0, 2: 8, 1: 9}[c]
    hdr = b"TEXV0005\0TEXI0001\0" + struct.pack("<6i", fmt, 2, w, h, w, h) + bytes((0x7f, 0x7f, 0x00, 0xff))
    hdr += b"TEXB0003\0" + struct.pack("<3i", 1, -1, len(levels))
    body = b""
    for a in levels:
        mh, mw = a.shape[:2]
        raw = np.ascontiguousarray(np.clip(np.round(a), 0, 255).astype(np.uint8)).tobytes()
        comp = _lz4_encode(raw)
        body += struct.pack("<5i", mw, mh, 1, len(raw), len(comp)) + comp
    Path(path).write_bytes(hdr + body)
