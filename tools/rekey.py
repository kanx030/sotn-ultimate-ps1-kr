"""Re-key translation sheets from one base to another (offsets of the old base -> offsets of the new one).

    python rekey.py 1.2 1.4 [--write]

Every sheet item's 'off' (plus the sheet's 'alt_start' / 'script_start') is an offset in the ORIGINAL file of
the old base. For a changed file the item's original bytes (cap bytes, at least 8) are looked up in the new
file: first at the place the anchor map (addrmap.py) predicts, else the occurrence nearest to that place.
Items whose bytes are nowhere in the new file are reported (text changed upstream -> translate again).
Without --write it only reports.
"""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import base, addrmap

def old_path(old, rel):
    return os.path.join(base.ROOT, 'work', base.BASES[old]['udir'], *rel.split('/'))

def find_new(a, b, m, off, n):
    pat = a[off:off + n]
    pred = m(off)
    if pred is not None and b[pred:pred + n] == pat:
        return pred, 'map'
    hits = []
    i = b.find(pat)
    while i >= 0 and len(hits) < 50:
        hits.append(i); i = b.find(pat, i + 1)
    if not hits:
        return None, 'gone'
    if len(hits) == 1:
        return hits[0], 'uniq'
    ref = pred if pred is not None else off
    hits.sort(key=lambda h: abs(h - ref))
    return hits[0], 'near%d' % len(hits)

def rekey_sheet(path, old, write, log):
    d = json.load(open(path, encoding='utf-8'))
    if not isinstance(d, dict) or 'file' not in d:
        return 0
    rel = d['file']
    a = open(old_path(old, rel), 'rb').read()
    b = base.uread(rel)
    if a == b:
        return 0
    m = addrmap.Map(a, b)
    bad = 0; moved = 0
    starts = {k: d[k] for k in ('alt_start', 'script_start') if isinstance(d.get(k), int)}
    deltas = []
    for it in d.get('items', []):
        o = it['off']; n = max(it.get('cap', 0), 8)
        no, how = find_new(a, b, m, o, n)
        if no is None:
            no, how = find_new(a, b, m, o, max(it.get('cap', 0), 1))
        if no is None:
            if not it.get('ko'):
                log.append('%s 0x%x %r: not in new file (untranslated junk, kept)' % (os.path.basename(path), o, it.get('en')))
                continue
            log.append('%s 0x%x %r: not in new file' % (os.path.basename(path), o, it.get('en'))); bad += 1
            continue
        deltas.append((o, no - o))
        if how.startswith('near'):
            log.append('%s 0x%x %r -> 0x%x (%s)' % (os.path.basename(path), o, it.get('en'), no, how))
        if no != o: moved += 1
        it['off'] = no
    for k, o in starts.items():        # script start: its own bytes (nibble pointers change), else the next item's delta
        no, how = find_new(a, b, m, o, 16)
        if no is None:
            nxt = [dl for io, dl in sorted(deltas) if io >= o]
            if nxt:
                no = o + nxt[0]; log.append('%s %s 0x%x -> 0x%x (next item delta)' % (os.path.basename(path), k, o, no))
            else:
                log.append('%s %s 0x%x: gone' % (os.path.basename(path), k, o)); bad += 1; continue
        d[k] = no
    if write and not bad and d != json.load(open(path, encoding='utf-8')):
        raw = open(path, 'rb').read(64).replace(b'\r', b'')
        nl = '\r\n' if b'\r\n' in open(path, 'rb').read(64) else '\n'
        ind = 1 if raw[:4] in (b'{\n "', b'[\n {') else 0
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline=nl) as f:
            json.dump(d, f, ensure_ascii=False, indent=ind)
        os.replace(tmp, path)
    log.append('%s: %s, %d items, %d moved, %d bad' % (os.path.basename(path), rel, len(d.get('items', [])), moved, bad))
    return bad

if __name__ == '__main__':
    old, new = sys.argv[1], sys.argv[2]
    assert base.VERSION == new, 'set SOTN_BASE=%s' % new
    write = '--write' in sys.argv
    log = []; bad = 0
    for p in sorted(glob.glob(os.path.join(base.ROOT, 'work', 'trans', '*.json'))):
        bad += rekey_sheet(p, old, write, log)
    print('\n'.join(log))
    print('bad', bad)
