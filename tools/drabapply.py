"""Write DRA engine-B Korean strings (work/trans/DRA_B.json) into DRA.BIN: the English strings' spans are pooled,
Korean strings are re-packed into them (first fit, largest first) and every data pointer / lui+lo pair is updated."""
import os, sys, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import drab, fontext, kmap
BASE = 0x800A0000

def apply(dra):
    dra = bytearray(dra)
    items = [e for e in drab.load() if e.get('ko')]
    for e in items:
        if isinstance(e['va'], str): e['va'] = int(e['va'], 16)
    base = set(kmap._load_map()[0])
    need = {c for e in items for c in e['ko'] if '가' <= c <= '힣' and c not in base}
    if need:
        fontext.ensure(''.join(sorted(need)))
    blobs = []
    for e in items:
        b, bad, _ = drab.encode(e['ko'], e['cat'] in drab.TWO_BYTE_ONLY)
        assert not bad, (e['id'], bad)
        blobs.append((e, b + b'\0'))
    spans = sorted((e['va'] - BASE, e['va'] - BASE + e['len']) for e in items)
    for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
        assert a1 <= b0, ('overlapping strings', hex(a0), hex(b0))
    for a, b in spans:
        dra[a:b] = b'\0' * (b - a)
    free = [list(s) for s in spans]
    placed = 0
    for e, b in sorted(blobs, key=lambda x: -len(x[1])):
        for s in free:
            if s[1] - s[0] >= len(b):
                o = s[0]; s[0] += len(b); break
        else:
            raise SystemExit('DRA_B: no room for %s (%d bytes)' % (e['id'], len(b)))
        dra[o:o + len(b)] = b; va = BASE + o; placed += 1
        for r in e.get('refs', []):
            assert struct.unpack_from('<I', dra, r)[0] == e['va'], (e['id'], hex(r))
            struct.pack_into('<I', dra, r, va)
        for hi_off, lo_off in e.get('code_refs', []):
            hi = struct.unpack_from('<I', dra, hi_off)[0]; lo = struct.unpack_from('<I', dra, lo_off)[0]
            op = lo >> 26
            h = (va >> 16) if op == 13 else ((va + 0x8000) >> 16) & 0xFFFF
            struct.pack_into('<I', dra, hi_off, (hi & 0xFFFF0000) | h)
            struct.pack_into('<I', dra, lo_off, (lo & 0xFFFF0000) | (va & 0xFFFF))
    left = sum(s[1] - s[0] for s in free)
    return bytes(dra), placed, left

if __name__ == '__main__':
    import build
    d, n, left = apply(build.read(os.path.join(build.U, 'DRA.BIN')))
    print('placed', n, 'free bytes left', left)
