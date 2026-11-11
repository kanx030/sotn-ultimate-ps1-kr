"""Locate the cutscene text engine (ST0-type) in an overlay by instruction patterns. '??' = wildcard byte."""
import re

SIGS = {
    'clear':  '40100400 21104400 80100200 ????4224 1200a2a7',
    'sprite': '0c000234 190062a0 ff010234 260062a4 320060a4 40100400 21104400 80100200',
    'chary':  '40300300 2130c300 80300600 ????c624',
    'scroll': '02000434 ????023c ????4284 00000000 06004228',
    'newline':'fcff0296 00000000 0c004224 fcff02a6',
    'thresh': '04000286 00000000 04004228',
    'clip':   '01004724 0500e228',
    'remap':  '0980023c af7b4290 20000334 28004230',
    'char':   '0f00c230 40100200 80034224',
}

def _rx(sig):
    out = b''
    for w in sig.split():
        for k in range(0, 8, 2):
            h = w[k:k + 2]
            out += b'.' if h == '??' else re.escape(bytes.fromhex(h))
    return re.compile(out, re.S)

def find(data, name):
    r = _rx(SIGS[name])
    return [m.start() for m in r.finditer(data) if m.start() % 4 == 0]

def locate(data):
    return {n: find(data, n) for n in SIGS}

if __name__ == '__main__':
    import glob, os
    for f in sorted(glob.glob(r'E:\SOTNKR\work\U\**\*.BIN', recursive=True)):
        x = open(f, 'rb').read()
        loc = locate(x)
        if loc['char']:
            print('%-22s %s' % (os.path.relpath(f, r'E:\SOTNKR\work\U'), ' '.join('%s:%d' % (n, len(v)) for n, v in loc.items())))

import struct
BASE = 0x80180000

def params(data):
    """Per-overlay values for the Korean hook: char-path va, return va, exit va, cursor global va."""
    c = find(data, 'char')[0]
    w = lambda o: struct.unpack_from('<I', data, o)[0]
    # exit: the 'j' just before the char path (space branch: sh v0; j exit)
    ex = None
    for o in range(c - 4, c - 0x40, -4):
        if w(o) >> 26 == 2:
            ex = 0x80000000 | ((w(o) & 0x3FFFFFF) << 2); break
    cur = None
    for o in range(c, c + 0x40, 4):
        a, b = w(o), w(o + 4)
        if a >> 26 == 15 and b >> 26 == 33 and ((a >> 16) & 31) == 5 and ((b >> 21) & 31) == 5 and ((b >> 16) & 31) == 5:
            cur = ((a & 0xFFFF) << 16) + (b & 0xFFFF) - (0x10000 if b & 0x8000 else 0); break
    disp = re.compile(re.escape(bytes.fromhex('0000228e00000000010043240000 23ae00004690'.replace(' ', ''))))
    ch = find(data, 'chary')
    yb = struct.unpack_from('<h', data, ch[0] + 12)[0] if len(ch) == 1 else None
    return dict(char=BASE + c, ret=BASE + c + 8, exit=ex, cursor=cur, ybase=yb, disp=len(disp.findall(data)))

if __name__ == '__main__':
    for f in sorted(glob.glob(r'E:\SOTNKR\work\U\**\*.BIN', recursive=True)):
        x = open(f, 'rb').read()
        if find(x, 'char'):
            p = params(x)
            print('%-22s %s' % (os.path.relpath(f, r'E:\SOTNKR\work\U'), ' '.join('%s=%s' % (k, hex(v) if isinstance(v, int) and v > 99 else v) for k, v in p.items())))

def remap_info(data):
    """(ps1, jp, psp) script VAs + file offsets of the 'to' words, from the dub remap function:
    first table (flag&0x28==0x20 -> JP dub), second table (flag&8==0 -> PSP dub)."""
    r = find(data, 'remap')
    if len(r) != 1: return None
    w = lambda o: struct.unpack_from('<I', data, o)[0]
    lws = []
    hi = None
    for o in range(r[0], r[0] + 0xB0, 4):
        a = w(o)
        if a >> 26 == 15 and (a >> 16) & 31 == 1: hi = a & 0xFFFF
        if a >> 26 == 35 and (a >> 21) & 31 == 1 and hi is not None:
            lo = a & 0xFFFF
            lws.append((hi << 16) + lo - (0x10000 if lo & 0x8000 else 0))
    if len(lws) < 4: return None
    jp_from, jp_to, psp_from, psp_to = lws[:4]
    g = lambda va: w(va - BASE)
    return dict(ps1=g(jp_from), jp=g(jp_to), psp=g(psp_to), jp_to_off=jp_to - BASE, psp_to_off=psp_to - BASE,
                ps1_b=g(psp_from))
