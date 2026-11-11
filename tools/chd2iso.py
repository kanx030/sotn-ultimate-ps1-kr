"""CHD v5 (DVD/raw, zlib only) -> ISO. Reuses the map decoder from chd2bin."""
import sys, struct
from chd2bin import bits_reader, huff_import_rle, inflate_raw

def main(src, dst):
    f = open(src, 'rb'); h = f.read(124)
    codecs = [h[16 + 4 * i:20 + 4 * i] for i in range(4)]
    logical = struct.unpack('>Q', h[32:40])[0]; mapoff = struct.unpack('>Q', h[40:48])[0]
    hunkbytes = struct.unpack('>I', h[56:60])[0]
    hunkcount = (logical + hunkbytes - 1) // hunkbytes
    f.seek(mapoff); mh = f.read(16)
    mapbytes = struct.unpack('>I', mh[0:4])[0]; firstoffs = int.from_bytes(mh[4:10], 'big')
    lengthbits, selfbits = mh[12], mh[13]
    read, peek, skip = bits_reader(f.read(mapbytes)); table = huff_import_rle(read)
    def dec():
        sym, l = table[peek(8)]; skip(l); return sym
    types = []; rep = 0; last = 0
    for _ in range(hunkcount):
        if rep > 0: types.append(last); rep -= 1; continue
        v = dec()
        if v == 7: types.append(last); rep = 2 + dec()
        elif v == 8: types.append(last); rep = 2 + 16 + (dec() << 4); rep += dec()
        else: types.append(v); last = v
    entries = []; cur = firstoffs; ls = 0
    for t in types:
        if t <= 3: ln = read(lengthbits); entries.append((t, cur, ln)); cur += ln; read(16)
        elif t == 4: entries.append((4, cur, hunkbytes)); cur += hunkbytes; read(16)
        elif t == 5: ls = read(selfbits); entries.append((5, ls, 0))
        elif t == 9: entries.append((5, ls, 0))
        elif t == 10: ls += 1; entries.append((5, ls, 0))
        else: raise SystemExit('map type %d' % t)
    out = open(dst, 'wb'); cache = {}
    def get(i):
        t, off, ln = entries[i]
        if t == 5: return get(off)
        if i in cache: return cache[i]
        f.seek(off); raw = f.read(ln)
        d = raw if t == 4 else inflate_raw(raw, hunkbytes)
        if len(cache) > 256: cache.clear()
        cache[i] = d; return d
    for i in range(hunkcount): out.write(get(i))
    out.truncate(logical); out.close(); print('ok', logical)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
