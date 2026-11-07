import struct, sys, os, glob, io
from PIL import Image
def lz4_block(src, size):
    dst = bytearray(); i = 0
    while i < len(src):
        tok = src[i]; i += 1
        lit = tok >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255: break
        dst += src[i:i+lit]; i += lit
        if i >= len(src): break
        off = src[i] | (src[i+1] << 8); i += 2
        ml = tok & 15
        if ml == 15:
            while True:
                b = src[i]; i += 1; ml += b
                if b != 255: break
        ml += 4
        st = len(dst) - off
        for k in range(ml): dst.append(dst[st+k])
    return bytes(dst[:size])
def decode(path, out):
    d = open(path, 'rb').read(); p = 0
    def u32():
        nonlocal p; v = struct.unpack_from('<i', d, p)[0]; p += 4; return v
    def tag():
        nonlocal p; e = d.index(b'\0', p); t = d[p:e].decode(); p = e + 1; return t
    tag(); tag()
    fmt, flags, tw, th, iw, ih, _ = [u32() for _ in range(7)]
    tb = tag(); count = u32()
    fif = u32() if tb in ('TEXB0003', 'TEXB0004') else -1
    if tb == 'TEXB0004': u32()
    mips = u32()
    w, h = u32(), u32()
    lz, dsz = (u32(), u32()) if tb != 'TEXB0001' else (0, 0)
    n = u32(); blob = d[p:p+n]
    if lz: blob = lz4_block(blob, dsz)
    if fif != -1:
        im = Image.open(io.BytesIO(blob)); im.load()
    elif fmt == 9:
        im = Image.frombytes('L', (w, h), blob)
    elif fmt == 8:
        import numpy as np
        a = np.frombuffer(blob, np.uint8).reshape(h, w, 2)
        im = Image.fromarray(np.dstack([a, np.zeros((h, w), np.uint8)]), 'RGB')
    elif fmt == 0:
        im = Image.frombytes('RGBA', (w, h), blob)
    else:
        raise SystemExit(f'unsupported fmt {fmt} in {path}')
    im = im.crop((0, 0, min(iw, im.width), min(ih, im.height)))
    im.save(out)
    print(f'{os.path.basename(path)}: fmt={fmt} tex={tw}x{th} img={iw}x{ih} mip0={w}x{h} mode={im.mode} -> {im.size}')
src, outdir = sys.argv[1], sys.argv[2]
os.makedirs(outdir, exist_ok=True)
for f in glob.glob(os.path.join(src, '**', '*.tex'), recursive=True):
    decode(f, os.path.join(outdir, os.path.splitext(os.path.basename(f))[0] + '.png'))
