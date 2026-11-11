"""Extract cutscene (PS1 script) text runs from each cutscene overlay into work/trans/<name>.json for translation.
A run = printable ASCII preceded by a script opcode byte (< 0x20) and followed by one. Runs inside the PSP/JP
alternate scripts (at/after the remap 'to' pointers) are skipped: those scripts are unused after the dub unify."""
import os, sys, re, json, struct
sys.path.insert(0, os.path.dirname(__file__))
import build, cutscene
B = 0x80180000
OUT = os.path.join(build.ROOT, 'work', 'trans')

def remap_to(data):
    r = cutscene.find(data, 'remap')
    if len(r) != 1: return None
    w = lambda o: struct.unpack_from('<I', data, o)[0]
    tos = []
    for o in range(r[0], r[0] + 0xB0, 4):
        a = w(o)
        if a >> 26 == 15 and (a >> 16) & 31 == 1:                 # lui at,hi
            for p in range(o + 4, o + 16, 4):
                b = w(p)
                if b >> 26 == 35 and (b >> 21) & 31 == 1:         # lw v0,lo(at)
                    tab = ((a & 0xFFFF) << 16) + (b & 0xFFFF) - (0x10000 if b & 0x8000 else 0)
                    tos.append(tab); break
    ptrs = []
    for t in tos:
        o = t - B
        if 0 <= o < len(data) - 4: ptrs.append(w(o))
    return sorted(set(p for p in ptrs if B <= p < B + len(data)))

def runs(data):
    out = []
    for m in re.finditer(rb'[\x20-\x7e]{2,}', data):
        a, b = m.start(), m.end()
        if a == 0 or b >= len(data): continue
        if not (data[a - 1] < 0x20 and data[b] < 0x20 and data[b] != 0): continue
        s = m.group().decode()
        if not re.search(r'[A-Za-z]{2}', s): continue
        out.append((a, s))
    return out

def main():
    os.makedirs(OUT, exist_ok=True)
    summary = []
    for f in build.CUTSCENE_FILES:
        d = build.read(os.path.join(build.U, *f.split('/')))
        ptrs = remap_to(d) or []
        # 'to' pointers come in pairs (from,to); 'from' = PS1 script. tables hold (from, to): take the larger ones as alt
        alt = min([p for p in ptrs], default=None)
        rr = runs(d)
        items = []
        start = (alt - B) if alt else None
        others = sorted(p - B for p in ptrs if p != alt)
        stop = others[0] if others else len(d)
        last = start
        for a, s in rr:
            if start is None or a < start or a >= stop: continue
            if a - last > 0x200: break
            nxt = d[a + len(s):a + len(s) + 3]
            items.append(dict(off=a, en=s, cap=len(s), after=nxt.hex(), newline_after=nxt[:1] == b'', ko='')); last = a + len(s)
        name = f.split('/')[-1].split('.')[0]
        for k, it in enumerate(items):
            end = it['off'] + it['cap']
            nxt = items[k + 1]['off'] if k + 1 < len(items) else end + 3
            gap = d[end:nxt]
            it['gap'] = gap.hex()
            it['newline_after'] = any(b in (0x01, 0x06, 0x0a, 0x0b, 0x00) for b in gap) or len(gap) > 12
        json.dump(dict(file=f, alt_start=alt and alt - B, items=items), open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        summary.append((name, len(items), alt and hex(alt - B)))
    for s in summary: print(s)



def extract_jp(script='jp'):
    """JP-dub script (PSP-B block, English text timed for the Japanese voice) -> work/trans/<NAME>.jp.json
    script='psp': PSP-dub script (PSP-A block, English text timed for the PSP English re-dub) -> <NAME>.psp.json"""
    out = []; suffix = '.%s.json' % script
    for f in build.CUTSCENE_FILES + ['ST/SEL/SEL.BIN', 'BOSS/MAR/MAR.BIN']:
        d = build.read(os.path.join(build.U, *f.split('/')))
        ri = cutscene.remap_info(d)
        if not ri: continue
        start = ri[script] - B
        ends = sorted(v - B for v in (ri['ps1'], ri['psp'], ri['jp'], ri['ps1_b']) if v - B > start) + [len(d)]
        stop = min(ends[0], start + 0x3000)
        items = []; last = start
        for a, s in runs(d):
            if a < start or a >= stop: continue
            if a - last > 0x200: break
            items.append(dict(off=a, en=s, cap=len(s), ko='')); last = a + len(s)
        for k, it in enumerate(items):
            end = it['off'] + it['cap']
            nxt = items[k + 1]['off'] if k + 1 < len(items) else end + 3
            gap = d[end:nxt]
            it['gap'] = gap.hex()
            it['newline_after'] = any(c in (0x01, 0x06, 0x0a, 0x0b, 0x00) for c in gap) or len(gap) > 12
        name = f.split('/')[-1].split('.')[0]
        fn = os.path.join(OUT, name + suffix)
        if os.path.exists(fn):
            old = {i['off']: i.get('ko', '') for i in json.load(open(fn, encoding='utf-8'))['items']}
            for it in items: it['ko'] = old.get(it['off'], '')
        json.dump(dict(file=f, script=script, alt_start=start, items=items), open(fn, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
        out.append((name, len(items)))
    print(out)

if __name__ == '__main__':
    if '--jp' in sys.argv: extract_jp()
    elif '--psp' in sys.argv: extract_jp('psp')
    else: main()
