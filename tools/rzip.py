"""Decompress a RetroArch RZIP save state; find swanstation VRAM. python rzip.py <state> <out.raw>"""
import struct, zlib, sys
def load(p):
    d = open(p, 'rb').read()
    if not d.startswith(b'#RZIPv'): return d
    chunk, total = struct.unpack_from('<IQ', d, 8)
    o = 20; out = bytearray()
    while o < len(d):
        n = struct.unpack_from('<I', d, o)[0]; o += 4
        out += zlib.decompress(d[o:o + n]); o += n
    assert len(out) == total
    return bytes(out)
if __name__ == '__main__':
    b = load(sys.argv[1]); open(sys.argv[2], 'wb').write(b); print(len(b))
