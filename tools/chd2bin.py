"""Minimal CHD v5 (CD) -> BIN/CUE extractor. Supports cdlz / cdzl, self/none hunks.
Usage: python chd2bin.py in.chd out.bin
"""
import sys, struct, zlib, lzma

def bits_reader(data):
    state = {'pos': 0}
    def read(n):
        v = 0
        p = state['pos']
        for _ in range(n):
            byte = data[p >> 3] if (p >> 3) < len(data) else 0
            v = (v << 1) | ((byte >> (7 - (p & 7))) & 1)
            p += 1
        state['pos'] = p
        return v
    def peek(n):
        p = state['pos']; r = read(n); state['pos'] = p; return r
    def skip(n):
        state['pos'] += n
    return read, peek, skip

def huff_import_rle(read, numcodes=16, maxbits=8):
    numbits = 5 if maxbits >= 16 else (4 if maxbits >= 8 else 3)
    lens = []
    while len(lens) < numcodes:
        nb = read(numbits)
        if nb != 1:
            lens.append(nb)
        else:
            nb = read(numbits)
            if nb == 1:
                lens.append(nb)
            else:
                rep = read(numbits) + 3
                lens.extend([nb] * rep)
    lens = lens[:numcodes]
    histo = [0] * 33
    for l in lens:
        histo[l] += 1
    cur = 0
    for cl in range(32, 0, -1):
        nxt = (cur + histo[cl]) >> 1
        histo[cl] = cur
        cur = nxt
    table = [None] * (1 << maxbits)
    for sym, l in enumerate(lens):
        if l == 0:
            continue
        code = histo[l]; histo[l] += 1
        base = code << (maxbits - l)
        for i in range(1 << (maxbits - l)):
            table[base + i] = (sym, l)
    return table

import numpy as np
_F = np.zeros(256, np.uint8); _B = np.zeros(256, np.uint8)
for _i in range(256):
    _j = ((_i << 1) ^ (0x11D if _i & 0x80 else 0)) & 0xFF
    _F[_i] = _j; _B[_i ^ _j] = _i

def _idx(major_count, minor_count, major_mult, minor_inc):
    size = major_count * minor_count
    out = np.zeros((major_count, minor_count), np.int64)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        for minor in range(minor_count):
            out[major, minor] = index
            index += minor_inc
            if index >= size:
                index -= size
    return out
_PIDX = _idx(86, 24, 2, 86)
_QIDX = _idx(52, 43, 86, 88)
SYNC = bytes([0] + [0xFF] * 10 + [0])

def _ecc_block(src, idx):
    # src: (N, L) uint8 ; idx: (major, minor)
    a = np.zeros((src.shape[0], idx.shape[0]), np.uint8); b = a.copy()
    for m in range(idx.shape[1]):
        t = src[:, idx[:, m]]
        a ^= t; b ^= t; a = _F[a]
    a = _B[_F[a] ^ b]
    return np.concatenate([a, a ^ b], axis=1)

def ecc_fix(sectors):
    """sectors: list of bytearray(2352) with sync/ECC stripped -> regenerate."""
    arr = np.frombuffer(b''.join(sectors), np.uint8).reshape(len(sectors), 2352).copy()
    arr[:, 0:12] = np.frombuffer(SYNC, np.uint8)
    src = arr[:, 12:].copy()
    mode2 = arr[:, 15] == 2
    src[mode2, 0:4] = 0
    p = _ecc_block(src[:, :2064], _PIDX)
    src[:, 2064:2064 + 172] = p
    q = _ecc_block(src[:, :2236], _QIDX)
    arr[:, 0x81C:0x81C + 172] = p
    arr[:, 0x8C8:0x8C8 + 104] = q
    return [bytes(r) for r in arr]

def lzma_raw(data, outlen):
    d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=[{'id': lzma.FILTER_LZMA1, 'dict_size': 1 << 20, 'lc': 3, 'lp': 0, 'pb': 2}])
    return d.decompress(data, max_length=outlen)

def inflate_raw(data, outlen):
    d = zlib.decompressobj(-15)
    out = d.decompress(data, outlen)
    return out

def main(src, dst):
    f = open(src, 'rb')
    h = f.read(124)
    assert h[:8] == b'MComprHD' and struct.unpack('>I', h[12:16])[0] == 5
    codecs = [h[16 + 4 * i:20 + 4 * i] for i in range(4)]
    logical = struct.unpack('>Q', h[32:40])[0]
    mapoff = struct.unpack('>Q', h[40:48])[0]
    hunkbytes, unitbytes = struct.unpack('>II', h[56:64])
    hunkcount = (logical + hunkbytes - 1) // hunkbytes
    f.seek(mapoff)
    mh = f.read(16)
    mapbytes = struct.unpack('>I', mh[0:4])[0]
    firstoffs = int.from_bytes(mh[4:10], 'big')
    lengthbits, selfbits, parentbits = mh[12], mh[13], mh[14]
    comp = f.read(mapbytes)
    read, peek, skip = bits_reader(comp)
    table = huff_import_rle(read)
    def dec():
        sym, l = table[peek(8)]
        skip(l)
        return sym
    types = []
    rep = 0; last = 0
    for _ in range(hunkcount):
        if rep > 0:
            types.append(last); rep -= 1
        else:
            v = dec()
            if v == 7:
                types.append(last); rep = 2 + dec()
            elif v == 8:
                types.append(last); rep = 2 + 16 + (dec() << 4); rep += dec()
            else:
                types.append(v); last = v
    entries = []
    cur = firstoffs; last_self = 0
    for t in types:
        if t <= 3:
            ln = read(lengthbits); entries.append((t, cur, ln)); cur += ln; read(16)
        elif t == 4:
            entries.append((4, cur, hunkbytes)); cur += hunkbytes; read(16)
        elif t == 5:
            last_self = read(selfbits); entries.append((5, last_self, 0))
        elif t == 9:
            entries.append((5, last_self, 0))
        elif t == 10:
            last_self += 1; entries.append((5, last_self, 0))
        else:
            raise SystemExit('unsupported map type %d' % t)
    frames_per_hunk = hunkbytes // 2448
    cache = {}
    out = open(dst, 'wb')
    meta = h  # frames from metadata
    f.seek(struct.unpack('>Q', h[48:56])[0] + 16)
    md = f.read(200).split(b'\0')[0].decode()
    total_frames = int(md.split('FRAMES:')[1].split()[0])
    written = 0
    stats = {}
    def get_hunk(i):
        t, off, ln = entries[i]
        if t == 5:
            return get_hunk(off)
        if i in cache:
            return cache[i]
        f.seek(off)
        raw = f.read(ln)
        if t == 4:
            data = raw
        else:
            codec = codecs[t]
            stats[codec] = stats.get(codec, 0) + 1
            ecc_bytes = (frames_per_hunk + 7) // 8
            clb = 2 if hunkbytes < 65536 else 3
            hb = ecc_bytes + clb
            cbase = int.from_bytes(raw[ecc_bytes:ecc_bytes + clb], 'big')
            eccmask = raw[:ecc_bytes]
            if codec == b'cdlz':
                base = lzma_raw(raw[hb:hb + cbase], frames_per_hunk * 2352)
            elif codec == b'cdzl':
                base = inflate_raw(raw[hb:hb + cbase], frames_per_hunk * 2352)
            else:
                raise SystemExit('unsupported codec %r (hunk %d)' % (codec, i))
            assert len(base) == frames_per_hunk * 2352, (i, len(base))
            secs = [base[k * 2352:(k + 1) * 2352] for k in range(frames_per_hunk)]
            fixk = [k for k in range(frames_per_hunk) if eccmask[k // 8] & (1 << (k % 8))]
            if fixk:
                fixed = ecc_fix([secs[k] for k in fixk])
                for k, s in zip(fixk, fixed):
                    secs[k] = s
            data = b''.join(s + b'\0' * 96 for s in secs)
        if len(cache) > 64:
            cache.clear()
        cache[i] = data
        return data
    for i in range(hunkcount):
        d = get_hunk(i)
        for k in range(frames_per_hunk):
            if written >= total_frames:
                break
            out.write(d[k * 2448:k * 2448 + 2352])
            written += 1
    out.close()
    print('frames', written, 'codec use', stats)

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
