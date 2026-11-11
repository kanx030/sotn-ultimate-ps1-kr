"""Extension Hangul glyphs for the Korean SOTN 16x15 font (kfont.bin).

The original font has 685 Hangul syllables (idx 524..1209, see kmap.py). Syllables
the translation needs beyond those get a free glyph slot (idx 1210..2047 except the
reserved 1536..1599) and a persistent code in work/fontext.json.

Glyph synthesis, best first (leave-one-out over the 685 real glyphs, see --eval):
  1. jamo analogy, depth 1: target = (A - (C - B)) | (B - C) for REAL glyphs A,B,C that
     differ from the target / each other by one jamo (final swap with same final
     presence, or vowel swap within the same vowel class). Pixel vote over all triples.
     -> reproduces the original bitmap style (1px strokes, original jamo shapes).
  2. jamo analogy, depth 2: same, A/B/C may be depth-1 syntheses.
  3. outline render: Noto Sans KR (OFL) VF, rendered x4, box-downsampled,
     stroke non-max-suppression + threshold, offset tuned for max agreement.
Only free fonts are used (Noto Sans KR VF; Nanum Gothic Bold was tried, scored lower).

API:  ensure(chars) -> {syl: code}; code_of(ch); glyph(ch) -> 30 bytes; apply(font) -> font
CLI:  python fontext.py <hangul text>   (ensures, writes work/fontext_check.png)
      python fontext.py --eval          (leave-one-out agreement report)
"""
import json, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kmap

WORK = kmap.WORK
TABLE = os.path.join(WORK, 'fontext.json')
CHECK_PNG = os.path.join(WORK, 'fontext_check.png')
FIRST_FREE, LAST_FREE = 1210, 2047
RESERVED = range(1536, 1600)
FREE_SLOTS = [i for i in range(FIRST_FREE, min(LAST_FREE, 1289) + 1) if i not in RESERVED]   # 1290..1535 = Galmuri7 bank (g7.py)

NOTO = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'
# tuned render fallback (grid search over Noto 14-18px, wght 100-400, Nanum Gothic Bold,
# offsets, thresholds, plain-threshold vs NMS): font px, weight, supersample, offset in
# supersampled px, coverage threshold, NMS on
R_SIZE, R_WGHT, R_S, R_DX, R_DY, R_T, R_NMS = 17, 300, 4, 16, 28, 0.40, True


def is_hangul(ch):
    return '\uac00' <= ch <= '\ud7a3'

# ------------------------------------------------------------------ table
def _load_table():
    if os.path.exists(TABLE):
        return json.load(open(TABLE, encoding='utf-8'))
    return {}

def _save_table(t):
    tmp = TABLE + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(t, f, ensure_ascii=False, indent=0)
    os.replace(tmp, TABLE)

def _existing():
    return kmap._load_map()[0]          # syllable -> canonical code

def ensure(chars):
    """Allocate slots for Hangul syllables in chars missing from the font. Stable:
    existing entries are never changed; new ones take the lowest unused free slot."""
    enc = _existing()
    t = _load_table()
    used = {int(c, 16) for c in t.values()}
    changed = False
    for ch in dict.fromkeys(chars):
        if not is_hangul(ch) or ch in enc or ch in t:
            continue
        for idx in FREE_SLOTS:
            c = kmap.index_to_code(idx)
            if c not in used:
                break
        else:
            raise RuntimeError('font extension full (%d slots)' % len(FREE_SLOTS))
        assert kmap.code_to_index(c) == idx and kmap._valid_lo(c & 0xFF), (idx, hex(c))
        t[ch] = '%04x' % c
        used.add(c)
        changed = True
    if changed:
        _save_table(t)
    return {s: int(c, 16) for s, c in t.items()}

def code_of(ch):
    enc = _existing()
    if ch in enc:
        return enc[ch]
    t = _load_table()
    if ch in t:
        return int(t[ch], 16)
    raise KeyError(ch)

# ------------------------------------------------------------------ real glyphs
_REAL = None
def real_glyphs():
    """syllable -> (15,16) bool, from the original Hangul block of kfont.bin."""
    global _REAL
    if _REAL is None:
        bits = kmap.load_font().astype(bool)
        _REAL = {}
        for c, s in sorted(kmap._load_map()[1].items()):
            idx = kmap.code_to_index(c)
            if is_hangul(s) and kmap.HANGUL_FIRST <= idx <= kmap.HANGUL_LAST:
                _REAL.setdefault(s, bits[idx])
    return _REAL

def _dec(s):
    o = ord(s) - 0xAC00
    return o // 588, (o // 28) % 21, o % 28

def _enc(l, v, t):
    return chr(0xAC00 + l * 588 + v * 28 + t)

# vowel classes: 0 vertical (a ae ya yae eo e yeo ye i), 1 horizontal (o yo u yu eu), 2 compound
_VCLS = {v: (0 if v in (0, 1, 2, 3, 4, 5, 6, 7, 20) else 1 if v in (8, 12, 13, 17, 18) else 2)
         for v in range(21)}

def _swap(A, B, C):
    return (A & ~(C & ~B)) | (B & ~C)

def _analogies(s, K):
    l, v, t = _dec(s)
    out = []
    # final swap: A=(l,v,ta) B=(lb,v,t) C=(lb,v,ta), same final presence
    for ta in range(28):
        if ta == t or (ta > 0) != (t > 0):
            continue
        A = _enc(l, v, ta)
        if A not in K:
            continue
        for lb in range(19):
            if lb == l:
                continue
            B, C = _enc(lb, v, t), _enc(lb, v, ta)
            if B in K and C in K:
                out.append(_swap(K[A], K[B], K[C]))
    # initial swap: A=(la,v,t) B=(l,v,tb) C=(la,v,tb)
    for la in range(19):
        A = _enc(la, v, t)
        if la == l or A not in K:
            continue
        for tb in range(28):
            if tb == t or (tb > 0) != (t > 0):
                continue
            B, C = _enc(l, v, tb), _enc(la, v, tb)
            if B in K and C in K:
                out.append(_swap(K[A], K[B], K[C]))
    # vowel swap within vowel class: A=(l,va,t) B=(lb,v,t) C=(lb,va,t)
    for va in range(21):
        if va == v or _VCLS[va] != _VCLS[v]:
            continue
        A = _enc(l, va, t)
        if A not in K:
            continue
        for lb in range(19):
            if lb == l:
                continue
            B, C = _enc(lb, v, t), _enc(lb, va, t)
            if B in K and C in K:
                out.append(_swap(K[A], K[B], K[C]))
    return out

def _vote(a):
    return (np.mean(a, 0) >= 0.5) if a else None

def _neighbours(s):
    """Syllables sharing at least one jamo position with s (possible A/B/C)."""
    l, v, t = _dec(s)
    out = set()
    for L in range(19):
        for V in range(21):
            out.add(_enc(L, V, t))
        for T in range(28):
            out.add(_enc(L, v, T))
    for V in range(21):
        for T in range(28):
            out.add(_enc(l, V, T))
    out.discard(s)
    return out

def synth(s, K=None, depth=2):
    """Analogy synthesis from glyph dict K (default: real glyphs) -> (bits, depth) or (None, 0)."""
    K = real_glyphs() if K is None else K
    p = _vote(_analogies(s, K))
    if p is not None:
        return p, 1
    if depth >= 2:
        K2 = dict(K)
        for n in _neighbours(s):
            if n not in K2:
                q = _vote(_analogies(n, K))
                if q is not None:
                    K2[n] = q
        p = _vote(_analogies(s, K2))
        if p is not None:
            return p, 2
    return None, 0

# ------------------------------------------------------------------ render fallback
_RFONT = None
def render(s):
    from PIL import Image, ImageDraw, ImageFont
    global _RFONT
    if _RFONT is None:
        _RFONT = ImageFont.truetype(NOTO, R_SIZE * R_S)
        _RFONT.set_variation_by_axes([R_WGHT])
    S = R_S
    im = Image.new('L', (26 * S, 26 * S), 0)
    ImageDraw.Draw(im).text((4 * S, 4 * S), s, fill=255, font=_RFONT, anchor='la')
    a = np.asarray(im, np.float32)[R_DY:R_DY + 15 * S, R_DX:R_DX + 16 * S] / 255
    c = a.reshape(15, S, 16, S).mean((1, 3))
    if not R_NMS:
        return c > R_T
    p = np.pad(c, 1)
    m = p[1:-1, 1:-1]
    h = (m >= p[1:-1, :-2]) & (m >= p[1:-1, 2:])
    v = (m >= p[:-2, 1:-1]) & (m >= p[2:, 1:-1])
    return (c > R_T) & (h | v)

# ------------------------------------------------------------------ glyph / apply
def bits_to_bytes(g):
    out = bytearray()
    for r in range(15):
        v = 0
        for x in range(16):
            if g[r, x]:
                v |= 0x8000 >> x
        out += bytes([v >> 8, v & 0xFF])
    return bytes(out)

_GCACHE = {}
def glyph_bits(ch):
    """(bits (15,16) bool, method) with method in real / analogy1 / analogy2 / render."""
    if ch in _GCACHE:
        return _GCACHE[ch]
    R = real_glyphs()
    if ch in R:
        r = (R[ch], 'real')
    else:
        p, d = synth(ch)
        r = (p, 'analogy%d' % d) if p is not None else (render(ch), 'render')
    _GCACHE[ch] = r
    return r

def glyph(ch):
    return bits_to_bytes(glyph_bits(ch)[0])

def apply(font):
    """Write glyphs of all table entries into font (bytearray, 2048*30), return it."""
    for s, c in _load_table().items():
        idx = kmap.code_to_index(int(c, 16))
        assert idx in FREE_SLOTS, (s, c, idx)
        font[idx * 30:idx * 30 + 30] = glyph(s)
    return font

# ------------------------------------------------------------------ evaluation / check image
def _score(p, g):
    return (p == g).mean(), 2 * (p & g).sum() / max(1, p.sum() + g.sum())

def evaluate():
    R = real_glyphs()
    res = {'analogy1': [], 'analogy2': [], 'render': [], 'final': []}
    for s, g in R.items():
        K = dict(R); del K[s]
        p, d = synth(s, K)
        r = render(s)
        res['render'].append(_score(r, g))
        if d:
            res['analogy%d' % d].append(_score(p, g))
        res['final'].append(_score(p if d else r, g))
    for k, v in res.items():
        if v:
            a, f = np.mean(v, 0)
            print('%-9s n=%3d  pixel agreement %.2f%%  ink F1 %.3f' % (k, len(v), a * 100, f))
    return res

def check_png(new, path=CHECK_PNG):
    from PIL import Image, ImageDraw, ImageFont
    lab = ImageFont.truetype(NOTO, 14)
    R = real_glyphs()
    known = sorted(R)[::57][:12]
    Z = 4
    cw, chh = 16 * Z, 15 * Z
    def tile(g):
        return Image.fromarray(np.where(g, 0, 255).astype(np.uint8)).resize((cw, chh), Image.NEAREST)
    gw = 3 * (cw + 4) + 14
    W = max(8 + 4 * gw, 8 + 8 * (cw + 40))
    H = 26 + ((len(known) + 3) // 4) * (chh + 24) + 30 + max(1, (len(new) + 7) // 8) * (chh + 24) + 6
    im = Image.new('RGB', (W, H), (200, 210, 220))
    d = ImageDraw.Draw(im)
    y = 4
    d.text((6, y), 'known: real | analogy (leave-one-out, blank=none) | Noto render', fill='black', font=lab)
    y += 22
    for i, s in enumerate(known):
        x = 8 + (i % 4) * gw
        yy = y + (i // 4) * (chh + 24)
        K = dict(R); del K[s]
        p, dd = synth(s, K)
        for j, g in enumerate([R[s], p if dd else np.zeros((15, 16), bool), render(s)]):
            im.paste(tile(g), (x + j * (cw + 4), yy))
        d.text((x, yy + chh + 2), '%s  depth=%s' % (s, dd or '-'), fill='black', font=lab)
    y += ((len(known) + 3) // 4) * (chh + 24) + 6
    d.text((6, y), 'new glyphs (a1/a2 = analogy depth, r = render)', fill='black', font=lab)
    y += 22
    for i, s in enumerate(new):
        g, m = glyph_bits(s)
        x = 8 + (i % 8) * (cw + 40)
        yy = y + (i // 8) * (chh + 24)
        im.paste(tile(g), (x, yy))
        d.text((x, yy + chh + 2), '%s %s' % (s, m.replace('analogy', 'a').replace('render', 'r')), fill='black', font=lab)
    im.save(path)
    return path

if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if '--eval' in sys.argv:
        evaluate()
        sys.exit()
    text = ''.join(a for a in sys.argv[1:] if not a.startswith('--'))
    tab = ensure(text)
    enc = _existing()
    new = [s for s in dict.fromkeys(text) if is_hangul(s) and s not in enc]
    for s in new:
        c = tab[s]
        print(s, '%04x' % c, 'idx', kmap.code_to_index(c), glyph_bits(s)[1])
    print('ext table: %d entries / %d slots' % (len(tab), len(FREE_SLOTS)))
    print('wrote', check_png(new))
