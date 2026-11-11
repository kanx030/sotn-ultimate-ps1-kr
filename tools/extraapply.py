"""Apply an extra translation sheet work/trans/extra_<NAME>.json to an overlay, in place (not wired into build.py).

Sheet: {file, script_start, items:[{off, en, cap, path, ko, orig?, nl?}]}
  path 'cutscene' : ST0-type cutscene script run (Galmuri bank codes via build.bank().encode, padded like
                    transapply: speed rescale / waits / 0x0D no-op). Needs the cutscene hook in that overlay.
  path 'api'      : 2-byte glyph-API string (drab.encode). '\n' in ko -> the sheet's line-break byte
                    (item 'nl': '\x01' message box, '@' librarian enemy list). Rest of cap zero-filled; the
                    original terminator (at off+cap) is kept.
  path 'menu8'    : DRA engine-A 8x8 menu string (draa.encode_a) + FF 00, zero-filled to cap.
  path 'ascii8'   : raw-ASCII 8x8 VRAM font (LIB menu 0x801B191C). Hangul needs a code hook, so for now the
                    English is written in UPPER case (the Korean 8x8 sheet keeps only upper-case cells).
apply(path, data) -> (data, n)   path = overlay path as in build ('ST/LIB/LIB.BIN'), n = items written.
python extraapply.py [NAME ...]  -> dry-run check of the sheets (lengths / encodability / widths).
"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
TR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'work', 'trans')
API_NL = {'\x01': 0x01, '@': 0x40}


def sheet_path(path):
    name = path.replace('\\', '/').split('/')[-1].split('.')[0]
    return os.path.join(TR, 'extra_' + name + '.json')


def enc_api(ko, nl='\x01'):
    import drab
    out = bytearray()
    for k, line in enumerate(ko.split('\n')):
        if k:
            out.append(API_NL[nl])
        b, bad, new = drab.encode(line)
        if bad:
            raise ValueError('api: cannot encode %r in %r' % (bad, ko))
        if new and any(ch not in drab._ext() for ch in new):
            raise ValueError('api: glyphs not in font %r in %r' % ([c for c in new if c not in drab._ext()], ko))
        out += b
    return bytes(out)


def enc_menu8(ko):
    import draa
    return draa.encode_a(ko) + b'\xff\x00'


def upper8(en):
    """Raw upper-case ASCII (the ascii8 routine indexes the 8x8 sheet by the raw byte; upper-case cells survive)."""
    return en.upper().encode()


def encode(it):
    p, ko, cap = it['path'], it.get('ko', ''), it['cap']
    if p == 'cutscene':
        import build
        b = build.bank().encode(ko, cap)
    elif p == 'api':
        b = enc_api(ko, it.get('nl', '\x01'))
    elif p == 'menu8':
        b = enc_menu8(ko)
        if it.get('noterm'):
            b = b[:-2]
    elif p == 'ascii8':
        b = upper8(it['en'])
    else:
        raise ValueError(p)
    if len(b) > cap:
        raise ValueError('%s %x: %d > cap %d: %r' % (p, it['off'], len(b), cap, ko))
    return b


def apply(path, data, skip_cutscene=False):
    fn = sheet_path(path)
    if not os.path.exists(fn):
        return data, 0
    d = json.load(open(fn, encoding='utf-8'))
    data = bytearray(data); n = 0; cruns = []
    for it in d['items']:
        if not it.get('ko') and it['path'] != 'ascii8':
            continue
        if it['path'] == 'cutscene' and (skip_cutscene or os.path.exists(os.path.join(TR, os.path.basename(fn)[6:]))):
            continue                                  # no hook / packed together by transapply                                  # no Galmuri hook in this file's engine yet: keep English
        off, cap = it['off'], it['cap']
        if 'orig' in it:
            assert data[off:off + len(it['orig']) // 2].hex() == it['orig'], (fn, hex(off))
        else:
            assert data[off:off + cap] == it['en'].encode(), (fn, hex(off))
        if it['path'] == 'cutscene':
            cruns.append((off, cap, it['ko'])); n += 1
            continue
        b = encode(it)
        data[off:off + cap] = b + bytes(cap - len(b))
        n += 1
    if cruns:
        import build, repack
        data = bytearray(repack.repack(data, None, cruns, build.bank().encode))
    return bytes(data), n


def check(names):
    import drab
    sys.stdout.reconfigure(encoding='utf-8')
    for name in names:
        d = json.load(open(os.path.join(TR, 'extra_' + name + '.json'), encoding='utf-8'))
        errs, done = [], 0
        for it in d['items']:
            if not it.get('ko'):
                continue
            try:
                b = encode(it); done += 1
            except Exception as e:
                errs.append(str(e)); continue
            if it['path'] == 'api' and it.get('limit'):
                for line in it['ko'].split('\n'):
                    px = drab.px_bytes(enc_api(line))
                    if px > it['limit']:
                        errs.append('%x line %dpx > %d: %s' % (it['off'], px, it['limit'], it['ko']))
        print('%s: %d/%d ok, %d errors' % (name, done, len(d['items']), len(errs)))
        for e in errs:
            print('   ', e)


if __name__ == '__main__':
    import glob
    names = sys.argv[1:] or sorted(os.path.basename(f)[6:-5] for f in glob.glob(os.path.join(TR, 'extra_*.json')))
    check(names)
