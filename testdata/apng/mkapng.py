# Two animated PNGs, written by hand with python's zlib -- an encoder that is not the package's.
import struct, sys, zlib, os

def chunk(name, body):
    c = zlib.crc32(name + body) & 0xffffffff
    return struct.pack('>I', len(body)) + name + body + struct.pack('>I', c)

def rows(w, h, px, bpp_bytes):
    out = b''
    for y in range(h):
        out += b'\x00' + b''.join(px(x, y) for x in range(w))
    return zlib.compress(out, 9)

def fctl(seq, w, h, x, y, dn, dd, dispose, blend):
    return chunk(b'fcTL', struct.pack('>IIIIIHHBB', seq, w, h, x, y, dn, dd, dispose, blend))

sig = b'\x89PNG\r\n\x1a\n'
out = sys.argv[1]

# One: 8x8 RGBA, the default image is the first frame.
def f0(x, y): return bytes([255, x * 32, y * 32, 255])
def f1(x, y): return bytes([0, 255, 0, 128 + x * 16])
def f2(x, y): return bytes([0, 0, 255, 64 * y])
d = sig + chunk(b'IHDR', struct.pack('>IIBBBBB', 8, 8, 8, 6, 0, 0, 0))
d += chunk(b'acTL', struct.pack('>II', 3, 0))
d += fctl(0, 8, 8, 0, 0, 1, 10, 0, 0)
d += chunk(b'IDAT', rows(8, 8, f0, 4))
d += fctl(1, 4, 4, 2, 2, 1, 10, 1, 1)
d += chunk(b'fdAT', struct.pack('>I', 2) + rows(4, 4, f1, 4))
d += fctl(3, 2, 3, 5, 4, 50, 0, 2, 0)
z = rows(2, 3, f2, 4)
d += chunk(b'fdAT', struct.pack('>I', 4) + z[:10])
d += chunk(b'fdAT', struct.pack('>I', 5) + z[10:])
d += chunk(b'IEND', b'')
open(os.path.join(out, 'apng-rgba.png'), 'wb').write(d)

# Two: 6x5 four-bit palette with transparency; the default image is a still, not a frame; plays 3.
pal = bytes([0, 0, 0, 255, 0, 0, 0, 255, 0, 0, 0, 255, 255, 255, 255])
def packed(w, h, idx):
    out = b''
    for y in range(h):
        row = [idx(x, y) for x in range(w)]
        if len(row) % 2: row.append(0)
        out += b'\x00' + bytes(row[i] << 4 | row[i + 1] for i in range(0, len(row), 2))
    return zlib.compress(out)
d = sig + chunk(b'IHDR', struct.pack('>IIBBBBB', 6, 5, 4, 3, 0, 0, 0))
d += chunk(b'acTL', struct.pack('>II', 2, 3))
d += chunk(b'PLTE', pal) + chunk(b'tRNS', bytes([0, 255, 128]))
d += chunk(b'IDAT', packed(6, 5, lambda x, y: 4))
d += fctl(0, 6, 5, 0, 0, 3, 100, 0, 0)
d += chunk(b'fdAT', struct.pack('>I', 1) + packed(6, 5, lambda x, y: (x + y) % 5))
d += fctl(2, 3, 2, 3, 3, 7, 100, 1, 1)
d += chunk(b'fdAT', struct.pack('>I', 3) + packed(3, 2, lambda x, y: 1 + x % 3))
d += chunk(b'IEND', b'')
open(os.path.join(out, 'apng-palette.png'), 'wb').write(d)
