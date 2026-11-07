import struct, sys, os
src, out = sys.argv[1], sys.argv[2]
data = open(src, 'rb').read()
p = 0
def u32():
    global p
    v = struct.unpack_from('<I', data, p)[0]; p += 4; return v
def s():
    global p
    n = u32(); v = data[p:p+n].decode('utf-8', 'replace'); p += n; return v
print('header', s())
count = u32()
entries = [(s(), u32(), u32()) for _ in range(count)]
base = p
for name, off, ln in entries:
    dst = os.path.join(out, *name.split('/'))
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, 'wb').write(data[base+off: base+off+ln])
    print(f'{ln:10d} {name}')
