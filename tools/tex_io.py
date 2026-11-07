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
        elif fmt == 4:
            a = decode_dxt5(blob, w, h)
        else:
            raise ValueError(f"unsupported fmt {fmt} in {path}")
        mw, mh = max(iw >> m, 1), max(ih >> m, 1)
        levels.append(a[:min(mh, a.shape[0]), :min(mw, a.shape[1])].copy())
    return levels


# ---------------------------------------------------------------- DXT5 (BC3)
# Used for layers that are one flat colour plus alpha (every creature layer): the colour block is
# the same for the whole texture, chosen so one palette entry hits the colour as closely as 565
# allows; the alpha block is encoded per 4x4 block with the better of BC3's two alpha modes.

def _x5(v):
    return (v << 3) | (v >> 2)


def _x6(v):
    return (v << 2) | (v >> 4)


def _bc1_constant(rgb):
    """(c0, c1, index) so palette[index] is as close to rgb as possible."""
    best = None
    for w in (1.0, 2.0 / 3.0):                     # palette entry 0 / entry 2 (or 3 when swapped)
        ends, err = [], 0.0
        for v, bits in zip(rgb, (5, 6, 5)):
            n = 1 << bits
            ex = np.array([_x5(i) if bits == 5 else _x6(i) for i in range(n)], float)
            val = w * ex[:, None] + (1 - w) * ex[None, :]
            k = int(np.argmin(np.abs(val - v)))
            ends.append((k // n, k % n))
            err += float(np.abs(val.flat[k] - v))
        if best is None or err < best[0] - 1e-9:
            best = (err, w, ends)
    _, w, ends = best
    c0 = (ends[0][0] << 11) | (ends[1][0] << 5) | ends[2][0]
    c1 = (ends[0][1] << 11) | (ends[1][1] << 5) | ends[2][1]
    if w == 1.0:
        return c0, c0, 0
    if c0 > c1:
        return c0, c1, 2
    if c0 < c1:
        return c1, c0, 3
    return c0, c1, 0


def _alpha_palette(a0, a1):
    """BC3 alpha palette for endpoint arrays (N,) -> (N, 8) float."""
    a0 = a0.astype(float)[:, None]
    a1 = a1.astype(float)[:, None]
    k7 = np.arange(1, 7)[None, :]
    k5 = np.arange(1, 5)[None, :]
    p8 = np.concatenate([a0, a1, ((7 - k7) * a0 + k7 * a1) / 7], 1)
    p6 = np.concatenate([a0, a1, ((5 - k5) * a0 + k5 * a1) / 5,
                         np.zeros_like(a0), np.full_like(a0, 255.0)], 1)
    return np.round(np.where(a0 > a1, p8, p6))


def _nearest(blocks, pal):
    d = np.abs(blocks[:, :, None] - pal[:, None, :])
    idx = np.argmin(d, 2)
    err = np.take_along_axis(d, idx[..., None], 2)[..., 0]
    return idx, (err ** 2).sum(1)


def _bc4_encode(blocks):
    """blocks (N,16) uint8 -> (a0, a1, idx (N,16)), best of the two BC3 alpha modes."""
    b = blocks.astype(float)
    lo, hi = b.min(1), b.max(1)
    # mode 8 (a0 > a1): endpoints max/min, then one least-squares refit of the endpoints
    a0, a1 = hi.copy(), lo.copy()
    for _ in range(2):
        idx, _ = _nearest(b, _alpha_palette(a0, a1))
        t = np.choose(idx, [np.zeros_like(b), np.ones_like(b)] + [np.full_like(b, k / 7) for k in range(1, 7)])
        s0, s1 = (1 - t), t                         # value = s0*a0 + s1*a1
        A = np.stack([(s0 * s0).sum(1), (s0 * s1).sum(1), (s1 * s1).sum(1)], 1)
        r0, r1 = (s0 * b).sum(1), (s1 * b).sum(1)
        det = A[:, 0] * A[:, 2] - A[:, 1] ** 2
        ok = np.abs(det) > 1e-9
        n0 = np.where(ok, (r0 * A[:, 2] - r1 * A[:, 1]) / np.where(ok, det, 1), a0)
        n1 = np.where(ok, (r1 * A[:, 0] - r0 * A[:, 1]) / np.where(ok, det, 1), a1)
        n0, n1 = np.clip(np.round(n0), 0, 255), np.clip(np.round(n1), 0, 255)
        keep = n0 > n1
        a0, a1 = np.where(keep, n0, a0), np.where(keep, n1, a1)
    m8 = a0 > a1
    i8, e8 = _nearest(b, _alpha_palette(a0, a1))
    e8 = np.where(m8, e8, np.inf)
    # mode 6 (a0 <= a1): endpoints over the values that are not exactly 0 or 255
    mid = (b > 0) & (b < 255)
    lo6 = np.where(mid, b, 255).min(1)
    hi6 = np.where(mid, b, 0).max(1)
    none = ~mid.any(1)
    lo6, hi6 = np.where(none, 0, lo6), np.where(none, 0, hi6)
    i6, e6 = _nearest(b, _alpha_palette(lo6, hi6))
    use8 = e8 < e6
    ra0 = np.where(use8, a0, lo6)
    ra1 = np.where(use8, a1, hi6)
    ridx = np.where(use8[:, None], i8, i6)
    rerr = np.minimum(e8, e6)
    # blocks that still miss by more than a few levels (mixed edge blocks): local search of both
    # endpoints in both modes
    bad = np.nonzero(rerr > 16 * 2.0 ** 2)[0]
    if len(bad):
        bb = b[bad]
        best = (rerr[bad].copy(), ra0[bad].copy(), ra1[bad].copy(), ridx[bad].copy())
        offs = range(-12, 13, 2)
        for base0, base1 in ((ra0[bad], ra1[bad]), (lo6[bad], hi6[bad]), (hi[bad], lo[bad])):
            for d0 in offs:
                for d1 in offs:
                    c0 = np.clip(base0 + d0, 0, 255)
                    c1 = np.clip(base1 + d1, 0, 255)
                    i, e = _nearest(bb, _alpha_palette(c0, c1))
                    m = e < best[0]
                    best = (np.where(m, e, best[0]), np.where(m, c0, best[1]), np.where(m, c1, best[2]),
                            np.where(m[:, None], i, best[3]))
        ra0[bad], ra1[bad], ridx[bad] = best[1], best[2], best[3]
    return ra0.astype(np.uint8), ra1.astype(np.uint8), ridx


def _to_blocks(a):
    h, w = a.shape
    return a.reshape(h // 4, 4, w // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16)


def encode_dxt5_flat(rgb, alpha):
    """One mip level: flat colour rgb (3 ints) + alpha (H, W), H and W multiples of 4."""
    a0, a1, idx = _bc4_encode(_to_blocks(np.asarray(alpha, np.uint8)))
    n = len(a0)
    bits = (idx.astype(np.uint64) << (3 * np.arange(16, dtype=np.uint64))[None, :]).sum(1, dtype=np.uint64)
    c0, c1, ci = _bc1_constant(rgb)
    out = np.zeros((n, 16), np.uint8)
    out[:, 0], out[:, 1] = a0, a1
    for k in range(6):
        out[:, 2 + k] = ((bits >> np.uint64(8 * k)) & np.uint64(0xFF)).astype(np.uint8)
    cidx = sum(ci << (2 * i) for i in range(16))
    out[:, 8:16] = np.frombuffer(struct.pack("<HHI", c0, c1, cidx), np.uint8)[None, :]
    return out.tobytes()


def decode_dxt5(data, w, h):
    """-> (H, W, 4) uint8 (reference decoder, palette rounding as in _alpha_palette)."""
    blk = np.frombuffer(data, np.uint8)[: (w // 4) * (h // 4) * 16].reshape(-1, 16)
    a0, a1 = blk[:, 0], blk[:, 1]
    bits = sum(blk[:, 2 + k].astype(np.uint64) << np.uint64(8 * k) for k in range(6))
    aidx = ((bits[:, None] >> (3 * np.arange(16, dtype=np.uint64))[None, :]) & np.uint64(7)).astype(int)
    alpha = np.take_along_axis(_alpha_palette(a0, a1), aidx, 1)
    c = blk[:, 8:12].copy().view("<u2")
    def rgb(v):
        return np.stack([_x5((v >> 11) & 31), _x6((v >> 5) & 63), _x5(v & 31)], 1).astype(float)
    p0, p1 = rgb(c[:, 0].astype(int)), rgb(c[:, 1].astype(int))
    pal = np.stack([p0, p1, (2 * p0 + p1) / 3, (p0 + 2 * p1) / 3], 1)   # BC3 colour is always 4-colour
    cbits = blk[:, 12:16].copy().view("<u4")[:, 0].astype(np.uint64)
    cidx = ((cbits[:, None] >> (2 * np.arange(16, dtype=np.uint64))[None, :]) & np.uint64(3)).astype(int)
    col = np.take_along_axis(pal, cidx[..., None].repeat(3, 2), 1)
    px = np.concatenate([np.round(col), alpha[..., None]], 2).astype(np.uint8)
    return px.reshape(h // 4, w // 4, 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(h, w, 4)


def write_dxt5_tex(path, rgb, alpha, mips=()):
    """Flat-colour DXT5 .tex: alpha (mip 0) + smaller alpha levels, every level a multiple of 4."""
    levels = [np.asarray(alpha, np.uint8), *[np.asarray(m, np.uint8) for m in mips]]
    h, w = levels[0].shape
    hdr = b"TEXV0005\0TEXI0001\0" + struct.pack("<6i", 4, 2, w, h, w, h) + bytes((0x7f, 0x7f, 0x00, 0xff))
    hdr += b"TEXB0003\0" + struct.pack("<3i", 1, -1, len(levels))
    body = b""
    for a in levels:
        mh, mw = a.shape
        assert mh % 4 == 0 and mw % 4 == 0, (mw, mh)
        raw = encode_dxt5_flat(rgb, a)
        comp = _lz4_encode(raw)
        body += struct.pack("<5i", mw, mh, 1, len(raw), len(comp)) + comp
    Path(path).write_bytes(hdr + body)


def _pack565(c):
    c = np.clip(np.round(c), 0, 255)
    return ((np.round(c[..., 0] * 31 / 255).astype(np.uint32) << 11)
            | (np.round(c[..., 1] * 63 / 255).astype(np.uint32) << 5)
            | np.round(c[..., 2] * 31 / 255).astype(np.uint32))


def _unpack565(v):
    v = v.astype(np.int64)
    return np.stack([_x5((v >> 11) & 31), _x6((v >> 5) & 63), _x5(v & 31)], -1).astype(float)


def encode_dxt5(rgba):
    """General DXT5 for one level (H, W multiples of 4): colour endpoints along each block's
    alpha-weighted principal axis (4-colour mode), alpha as in encode_dxt5_flat."""
    a = np.asarray(rgba, np.uint8)
    h, w = a.shape[:2]
    blk = a.reshape(h // 4, 4, w // 4, 4, 4).transpose(0, 2, 1, 3, 4).reshape(-1, 16, 4).astype(float)
    a0, a1, aidx = _bc4_encode(blk[..., 3].astype(np.uint8))
    col, wt = blk[..., :3], blk[..., 3] / 255.0 + 0.02
    mean = (col * wt[..., None]).sum(1) / wt.sum(1)[:, None]
    x = col - mean[:, None, :]
    cov = np.einsum("nki,nkj,nk->nij", x, x, wt)
    axis = np.linalg.eigh(cov)[1][..., -1]                          # largest eigenvector
    proj = np.einsum("nki,ni->nk", x, axis)
    e0 = mean + proj.max(1)[:, None] * axis
    e1 = mean + proj.min(1)[:, None] * axis
    c0, c1 = _pack565(e0), _pack565(e1)
    swap = c0 < c1
    c0, c1 = np.where(swap, c1, c0), np.where(swap, c0, c1)
    p0, p1 = _unpack565(c0), _unpack565(c1)
    four = (c0 > c1)[:, None, None]
    pal = np.stack([p0, p1, np.where(four[:, 0], (2 * p0 + p1) / 3, (p0 + p1) / 2),
                    np.where(four[:, 0], (p0 + 2 * p1) / 3, 0)], 1)
    d = ((col[:, :, None, :] - pal[:, None, :, :]) ** 2).sum(-1)
    if (~four[:, 0, 0]).any():                                      # c0 == c1: one colour, index 0
        d[~four[:, 0, 0], :, 1:] = np.inf
    cidx = np.argmin(d, 2).astype(np.uint32)
    n = len(a0)
    out = np.zeros((n, 16), np.uint8)
    out[:, 0], out[:, 1] = a0, a1
    bits = (aidx.astype(np.uint64) << (3 * np.arange(16, dtype=np.uint64))[None, :]).sum(1, dtype=np.uint64)
    for k in range(6):
        out[:, 2 + k] = ((bits >> np.uint64(8 * k)) & np.uint64(0xFF)).astype(np.uint8)
    out[:, 8:10] = np.stack([c0 & 255, c0 >> 8], 1).astype(np.uint8)
    out[:, 10:12] = np.stack([c1 & 255, c1 >> 8], 1).astype(np.uint8)
    cb = (cidx << (2 * np.arange(16, dtype=np.uint32))[None, :]).sum(1, dtype=np.uint64).astype(np.uint32)
    out[:, 12:16] = cb.view(np.uint8).reshape(-1, 4)
    return out.tobytes()


def write_dxt5_rgba_tex(path, levels, image_size=None):
    """General DXT5 .tex from RGBA levels (largest first, each a multiple of 4). image_size
    (w, h) <= the level 0 size marks padding, like WE's own padded imports."""
    h, w = levels[0].shape[:2]
    iw, ih = image_size or (w, h)
    hdr = b"TEXV0005\0TEXI0001\0" + struct.pack("<6i", 4, 2, w, h, iw, ih) + bytes((0x7f, 0x7f, 0x00, 0xff))
    hdr += b"TEXB0003\0" + struct.pack("<3i", 1, -1, len(levels))
    body = b""
    for a in levels:
        mh, mw = a.shape[:2]
        assert mh % 4 == 0 and mw % 4 == 0, (mw, mh)
        raw = encode_dxt5(a)
        comp = _lz4_encode(raw)
        body += struct.pack("<5i", mw, mh, 1, len(raw), len(comp)) + comp
    Path(path).write_bytes(hdr + body)


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
