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
def get(rel, old='1.2'):
    k = (rel, old)
    if k not in _cache:
        a = open(os.path.join(base.ROOT, 'work', base.BASES[old]['udir'], *rel.split('/')), 'rb').read()
        _cache[k] = Map(a, base.uread(rel))
    return _cache[k]

if __name__ == '__main__':
    import sys
    m = get(sys.argv[1])
    for s in m.segs:
        print('%06x-%06x %+d' % s)
