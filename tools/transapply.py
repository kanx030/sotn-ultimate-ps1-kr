"""Apply work/trans/<NAME>.json translations (items with non-empty ko) to an overlay, in place, padded with no-op."""
import os, json
from st0text import enc, PAD
TR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'trans')

TRIMMED = []

def apply(path, data):
    n = 0
    for suffix in ('.json', '.jp.json', '.psp.json'):   # PS1 dub, JP dub, PSP English dub scripts
        data, k = _apply(path, data, suffix); n += k
    return data, n

def _apply(path, data, suffix):
    name = path.split('/')[-1].split('.')[0]
    fn = os.path.join(TR, name + suffix)
    if not os.path.exists(fn):
        return data, 0
    d = json.load(open(fn, encoding='utf-8'))
    runs = []
    for it in d['items']:
        ko = it.get('ko', '')
        if not ko: continue
        en = it['en'].encode()
        assert data[it['off']:it['off'] + len(en)] == en, (name, hex(it['off']))
        runs.append((it['off'], len(en), ko, it.get('block', 0)))   # block: separate script (own repack)
    if suffix == '.json':                         # extra cutscene lines in the same script block: pack together
        ex = os.path.join(TR, 'extra_%s.json' % name)
        if os.path.exists(ex):
            for it in json.load(open(ex, encoding='utf-8'))['items']:
                if it.get('path') == 'cutscene' and it.get('ko'):
                    runs.append((it['off'], it['cap'], it['ko'], 0))
    import build, repack
    groups = sorted(set(r[3] for r in runs))
    if len(groups) > 1:                           # several scripts in one sheet: each block re-packed on its own,
        n = 0                                     # so a later script's start (code lui/addiu) never moves
        for g in groups:
            data, k = _pack(name, data, d, suffix, [r[:3] for r in runs if r[3] == g]); n += k
        return bytes(data), n
    return _pack(name, data, d, suffix, [r[:3] for r in runs])

def _pack(name, data, d, suffix, runs):
    import build, repack
    prefix = None
    if suffix == '.jp.json' and d.get('jptiming', True):    # uniform page timing (jptiming.UNIFORM, 11-13)   # JP dub: typing speed/waits from the PSP Korean script
        import jptiming
        try:
            edits, prefix = jptiming.plan(name, data, d, build.bank().encode)
        except Exception as e:                    # never break the build over timing
            print('  jptiming skipped for %s: %r' % (name, e)); edits, prefix = {}, None
        data = bytearray(data)
        for pos, v in edits.items(): data[pos] = v
        try:
            return bytes(repack.repack(data, None, runs, build.bank().encode, timing=False, prefix=prefix)), len(runs)
        except repack.Overflow:
            print('  jptiming: no room for speed prefixes in %s, using slot edits only' % name)
            prefix = None
    data = repack.repack(data, None, runs, build.bank().encode, timing=True, prefix=prefix)
    n = len(runs)
    return bytes(data), n

def all_strings():
    import glob
    out = []
    for fn in sorted(glob.glob(os.path.join(TR, '*.json'))):
        bn = os.path.basename(fn)
        if bn == 'ST0.json' or bn.startswith('DRA') or bn.endswith('.k.json'): continue
        d = json.load(open(fn, encoding='utf-8'))
        if not isinstance(d, dict): continue
        for it in d.get('items', []):
            if it.get('ko') and it.get('path', 'cutscene') == 'cutscene': out.append(it['ko'])
    return out
