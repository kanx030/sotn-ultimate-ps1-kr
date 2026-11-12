"""Old base -> new base address map for one file, from unique byte windows (anchors).

    import addrmap; m = addrmap.get('DRA.BIN', '1.2'); new_off = m(old_off)
Anchors: every 4-aligned 16-byte window that occurs exactly once in both files. Runs of anchors with the
same delta form segments; an offset maps with the delta of the segment containing it (None if it falls in
a region with no consistent anchor around it)."""
import os, bisect, base

W = 16

def _windows(d):
    seen = {}
    for i in range(0, len(d) - W + 1, 4):
        k = d[i:i + W]
        seen[k] = -1 if k in seen else i
    return seen

def anchors(a, b):
    wa, wb = _windows(a), _windows(b)
    out = []
    for k, i in wa.items():
        if i >= 0 and k.count(0) < W - 2:
            j = wb.get(k)
            if j is not None and j >= 0:
                out.append((i, j - i))
    out.sort()
    return out

def segments(anc, minrun=3):
    segs = []           # (start_old, end_old, delta)
    cur = None
    for o, dl in anc:
        if cur and cur[2] == dl:
            cur[1] = o + W; cur[3] += 1
        else:
            if cur and cur[3] >= minrun: segs.append(tuple(cur[:3]))
            cur = [o, o + W, dl, 1]
    if cur and cur[3] >= minrun: segs.append(tuple(cur[:3]))
    return segs

class Map:
    def __init__(self, a, b):
        self.segs = segments(anchors(a, b))
        self.starts = [s[0] for s in self.segs]
    def delta(self, off, slack=0x200):
        i = bisect.bisect_right(self.starts, off) - 1
        if i >= 0 and off < self.segs[i][1] + slack:
            # inside a segment, or in a gap whose two neighbours agree
            if off < self.segs[i][1] or (i + 1 < len(self.segs) and self.segs[i + 1][2] == self.segs[i][2]):
                return self.segs[i][2]
            if i + 1 >= len(self.segs) or off < self.segs[i][1] + 0x40:
                return self.segs[i][2]
        if i + 1 < len(self.segs) and i >= 0 and self.segs[i][2] == self.segs[i + 1][2]:
            return self.segs[i][2]
        return None
    def __call__(self, off):
        d = self.delta(off)
        return None if d is None else off + d

_cache = {}
_fcache = {}
def _files(rel, old):
    k = (rel, old)
    if k not in _fcache:
        _fcache[k] = (open(os.path.join(base.ROOT, 'work', base.BASES[old]['udir'], *rel.split('/')), 'rb').read(),
                      base.uread(rel))
    return _fcache[k]

def get(rel, old='1.2'):
    k = (rel, old)
    if k not in _cache:
        _cache[k] = Map(*_files(rel, old))
    return _cache[k]

if __name__ == '__main__':
    import sys
    m = get(sys.argv[1])
    for s in m.segs:
        print('%06x-%06x %+d' % s)


# ---------------------------------------------------------------- relocating single addresses
def _ptr(w):
    return 0x80000000 <= w < 0x80200000

def _insn_key(w):
    """Word with its relocatable part masked: jal/j targets, lui/addiu/ori/lw/sw immediates, pointers."""
    op = w >> 26
    if _ptr(w):
        return 'P'
    if op in (2, 3):
        return op << 26
    if op in (15, 9, 13, 35, 43, 32, 36, 33, 37, 40, 41, 34, 38, 42, 46) :
        return w & 0xFFFF0000
    return w

def _keys(d, off, n):
    import struct
    return [_insn_key(struct.unpack_from('<I', d, off + 4 * i)[0]) for i in range(n // 4)]

def reloc(rel, old_va, load, n=16, old='1.2', window=0x20000, masked=True):
    """Address in the current base of what sits at old_va in the old base's file `rel` (loaded at `load`).
    Checks the n bytes there (exact first, then with pointers/immediates/jump targets masked) and searches
    near the mapped place if the map is off. Raises if nothing (or more than one place) matches."""
    if old == base.VERSION:
        return old_va
    a, b = _files(rel, old)
    m = get(rel, old)
    off = old_va - load
    pat = a[off:off + n]
    pred = m(off)
    if pred is not None and b[pred:pred + n] == pat:
        return load + pred
    hits = []
    i = b.find(pat)
    while i >= 0 and len(hits) < 3:
        hits.append(i); i = b.find(pat, i + 1)
    if len(hits) == 1:
        return load + hits[0]
    if masked and off % 4 == 0:
        k = _keys(a, off, n)
        ref = pred if pred is not None else off
        lo, hi = max(0, ref - window) & ~3, min(len(b) - n, ref + window)
        if pred is not None and _keys(b, pred, n) == k:
            return load + pred
        mh = [j for j in range(lo, hi, 4) if _keys(b, j, n) == k] if not hits else [h for h in hits if abs(h - ref) < window]
        if len(mh) == 1:
            return load + mh[0]
        if len(mh) > 1:
            mh.sort(key=lambda j: abs(j - ref))
            if abs(mh[0] - ref) < abs(mh[1] - ref) and pred is not None and abs(mh[0] - ref) < 0x100:
                return load + mh[0]
        if not mh:
            r = _shrink(a, b, off, n, ref)
            if r is not None:
                return load + r
        raise LookupError('%s 0x%08X: %d masked matches' % (rel, old_va, len(mh)))
    r = _shrink(a, b, off, n, pred if pred is not None else off)
    if r is not None:
        return load + r
    raise LookupError('%s 0x%08X: %d exact matches, no masked search' % (rel, old_va, len(hits)))

def _shrink(a, b, off, n, ref, near=0x400):
    """Shorter exact patterns (data whose neighbours changed, e.g. a string followed by an edited one):
    the occurrence nearest to the predicted place, if it is clearly the nearest and close."""
    for k in range(n - 4, 5, -2):
        pat = a[off:off + k]
        hits = []; i = b.find(pat)
        while i >= 0 and len(hits) < 200:
            hits.append(i); i = b.find(pat, i + 1)
        hits = sorted((h for h in hits if abs(h - ref) < near), key=lambda h: abs(h - ref))
        if len(hits) == 1 or (len(hits) > 1 and abs(hits[0] - ref) < abs(hits[1] - ref) // 4):
            return hits[0]
    return None

def dra(old_va, n=16, **kw):
    return reloc('DRA.BIN', old_va, 0x800A0000, n, **kw)

def ovl(rel, old_va, n=16, **kw):
    return reloc(rel, old_va, 0x80180000, n, **kw)

def port_code(b, rel='DRA.BIN', load=0x800A0000, size=None):
    """v1.2 code bytes -> the same code in the current base: j/jal targets inside the file are relocated."""
    import struct
    b = bytearray(b)
    size = size or len(_files(rel, '1.2')[0])
    for i in range(0, len(b) - 3, 4):
        w = struct.unpack_from('<I', b, i)[0]
        if w >> 26 in (2, 3):
            t = 0x80000000 | ((w & 0x3FFFFFF) << 2)
            if load <= t < load + size:
                nt = reloc(rel, t, load)
                struct.pack_into('<I', b, i, (w & 0xFC000000) | ((nt >> 2) & 0x3FFFFFF))
    return bytes(b)

def _hilo_refs(d, target=None):
    """{address: [(lui_off, lo_off)]} for lui rX,hi ... (addiu/ori/lw/sw/lh/lb..) rY,lo(rX) within 12 insns."""
    import struct
    out = {}
    LO = (9, 13, 35, 43, 32, 36, 33, 37, 40, 41, 34, 38, 42, 46)
    for o in range(0, len(d) - 4, 4):
        x = struct.unpack_from('<I', d, o)[0]
        if x >> 26 != 15:
            continue
        rt = (x >> 16) & 31; hi = (x & 0xFFFF) << 16
        for k in range(1, 12):
            p = o + 4 * k
            if p + 4 > len(d): break
            y = struct.unpack_from('<I', d, p)[0]
            op, rs, rt2 = y >> 26, (y >> 21) & 31, (y >> 16) & 31
            if op in LO and rs == rt:
                imm = y & 0xFFFF
                if op != 13: imm -= 0x10000 if imm & 0x8000 else 0
                v = ((hi | imm) if op == 13 else hi + imm) & 0xFFFFFFFF
                if target is None or v == target:
                    out.setdefault(v, []).append((o, p))
                if rt2 == rt and op not in (43, 41, 40, 46): break
            if (op == 15 and rt2 == rt) or op in (2, 3) or (op == 0 and (y & 0x3F) == 8):
                break
    return out

def var(rel, old_va, load, old='1.2'):
    """New address of a variable (e.g. in an overlay's BSS, outside the file) referenced by code: decode the
    same lui/lo pairs at the mapped code places in the new file; all must agree."""
    import struct
    if old == base.VERSION:
        return old_va
    a, b = _files(rel, old)
    m = get(rel, old)
    refs = _hilo_refs(a, old_va).get(old_va, [])
    got = {}
    for lo_, p in refs:
        nl, np_ = m(lo_), m(p)
        if nl is None or np_ is None or np_ - nl != p - lo_:
            continue
        r = _hilo_refs(b[nl:np_ + 4]).items()
        for v, prs in r:
            if (0, np_ - nl) in prs:
                got[v] = got.get(v, 0) + 1
    assert got, '%s 0x%08X: no mapped code reference' % (rel, old_va)
    best = max(got, key=got.get)
    assert got[best] >= sum(got.values()) * 0.8, ('%s 0x%08X: references disagree' % (rel, old_va), got)
    return best

def ovl_var(rel, old_va, **kw):
    return var(rel, old_va, 0x80180000, **kw)

def remap_runs(rel, runs, load=0x80180000, old='1.2'):
    """[(v1.2 file offset, original bytes|str, ...)] -> same tuples with the offset in the current base
    (found by the original bytes near the mapped place)."""
    if old == base.VERSION:
        return list(runs)
    out = []
    for t in runs:
        en = t[1].encode('latin1') if isinstance(t[1], str) else t[1]
        no = reloc(rel, load + t[0], load, n=len(en), old=old, masked=False) - load
        out.append((no,) + tuple(t[1:]))
    return out
