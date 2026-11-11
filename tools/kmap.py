"""Code <-> Hangul mapping for the Korean SOTN (SLPM-86023 K) 16x15 font.

Build:  python kmap.py         -> work/kmap.json, work/kmap_check.png
Use:    from kmap import encode, decode

Glyph identification: every Hangul glyph (font idx 524..1220) is compared with
renderings of all 11172 modern syllables in several Windows Korean TTFs
(bbox-normalised, blurred, normalised cross-correlation, averaged over fonts),
with a small bonus for the KS X 1001 2350 set.
"""
import json, os, struct, sys
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
WORK = os.path.join(ROOT, 'work')
FONT = os.path.join(WORK, 'kfont.bin')
EXE = os.path.join(WORK, 'K', 'SLPM_860.23')
OUT_JSON = os.path.join(WORK, 'kmap.json')
OUT_PNG = os.path.join(WORK, 'kmap_check.png')

HANGUL_FIRST, HANGUL_LAST = 524, 1209   # inclusive; 1210+ are hanzi/garbage
NON_HANGUL = {1204: '©'}          # (c) sign inside the extras block
VERIFIED = {1203: '뭔'}           # visually verified overrides (matcher said 원)
BASE89 = 618   # idx of code 0x8940 (= 524 + 94: 0x889F..0x88FC fill 524..617)
SORTED_LAST = 1195  # 524..1195 are KS X 1001 syllables in ascending order; 1196..1209 extras
LOW_CONF = 0.06                          # margin (best - 2nd best) below this = low confidence

# ---------------------------------------------------------------- code <-> index
def _load_table():
    d = open(EXE, 'rb').read()[0xE00:0xE00 + 80]
    return [struct.unpack('>HH', d[i * 4:i * 4 + 4]) for i in range(20)]

_TABLE = None
def code_to_index(c):
    global _TABLE
    if c >= 0x8940:
        hi, lo = c >> 8, c & 0xFF
        l2 = lo - 0x40 - (1 if lo >= 0x7F else 0)
        return 188 * (hi - 0x89) + l2 + BASE89
    if _TABLE is None:
        _TABLE = _load_table()
    for start, sidx in reversed(_TABLE):
        if c >= start:
            return c - start + sidx
    return None

def index_to_code(idx):
    """Code for a glyph index (>=618 via 0x89xx formula, 524..617 via table 0x889F..)."""
    if idx >= BASE89:
        n = idx - BASE89
        hi, l2 = divmod(n, 188)
        lo = l2 + 0x40 + (1 if l2 >= 0x3F else 0)
        return ((hi + 0x89) << 8) | lo
    return 0x889F + (idx - 524)

def _valid_lo(lo):
    return 0x40 <= lo <= 0xFC and lo != 0x7F

# ---------------------------------------------------------------- font bitmaps
def load_font():
    f = np.frombuffer(open(FONT, 'rb').read(), np.uint8).reshape(2048, 15, 2)
    v = (f[:, :, 0].astype(np.uint32) << 8) | f[:, :, 1]
    sh = np.arange(15, -1, -1, dtype=np.uint32)
    return ((v[:, :, None] >> sh) & 1).astype(np.uint8)   # (2048,15,16)

# ---------------------------------------------------------------- matching
FEATS = [(24, 1.2)]   # (normalised size, blur); ensembles with sharper features were tried and did worse

def _norm(img):
    """bbox crop -> resize SxS -> blur -> zero-mean unit vector, per FEATS, concatenated."""
    from PIL import Image, ImageFilter
    ys, xs = np.nonzero(img)
    out = []
    for S, blur in FEATS:
        if len(ys) == 0:
            out.append(np.zeros(S * S, np.float32)); continue
        c = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.uint8) * 255
        im = Image.fromarray(c).resize((S, S), Image.BILINEAR).filter(ImageFilter.GaussianBlur(blur))
        a = np.asarray(im, np.float32).ravel()
        a -= a.mean()
        n = np.linalg.norm(a)
        out.append((a / n if n else a) / np.sqrt(len(FEATS)))
    return np.concatenate(out)

FONTS = [('malgun.ttf', 0), ('gulim.ttc', 0), ('gulim.ttc', 2), ('batang.ttc', 0),
         ('HANDotum.ttf', 0)]

def _render(ch, font):
    from PIL import Image, ImageDraw
    im = Image.new('L', (40, 40), 0)
    ImageDraw.Draw(im).text((4, 4), ch, fill=255, font=font)
    return (np.asarray(im) > 110).astype(np.uint8)

def _final_box_kind(g):
    """For a glyph whose final is a box (ieung/mieum): 'o' if the bottom stroke is inset
    from the side strokes (rounded ieung), 'm' if flush (square mieum), None if unclear."""
    rows = np.nonzero(g.any(1))[0]
    if len(rows) < 3:
        return None
    r = rows[-1]
    xs = np.nonzero(g[r])[0]
    if len(xs) < 4:
        return None
    l, rr = xs.min(), xs.max()
    above = g[r - 1]
    if l > 0 and rr < 15 and above[l - 1] and above[rr + 1] and not above[l + 1]:
        return 'o'
    if above[l] and above[rr] and not (l > 0 and above[l - 1]):
        return 'm'
    return None

def _swap_final(ch, a, b):
    o = ord(ch) - 0xAC00
    f = o % 28
    if f == a:
        return chr(ord(ch) - a + b)
    return None

def candidates():
    syl = [chr(c) for c in range(0xAC00, 0xD7A4)]
    ks = set()
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            try:
                ks.add(bytes([hi, lo]).decode('euc-kr'))
            except UnicodeDecodeError:
                pass
    return syl, np.array([s in ks for s in syl])

def build():
    from PIL import ImageFont
    bits = load_font()
    gl = np.stack([_norm(bits[i]) for i in range(HANGUL_FIRST, HANGUL_LAST + 1)])
    syl, isks = candidates()
    fontdir = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
    score = np.zeros((len(gl), len(syl)), np.float32)
    nf = 0
    for name, ix in FONTS:
        p = os.path.join(fontdir, name)
        if not os.path.exists(p):
            continue
        for size in (15, 16):
            font = ImageFont.truetype(p, size, index=ix)
            C = np.stack([_norm(_render(s, font)) for s in syl])
            score += gl @ C.T
            nf += 1
        print('font', name, ix, file=sys.stderr)
    score /= nf
    score += 0.02 * isks[None, :]
    n = len(gl)
    K = SORTED_LAST - HANGUL_FIRST + 1
    dps = np.where(isks[None, :], score, -1.0)   # sorted part = KS X 1001 subset
    # --- monotonic DP over the sorted part: chosen syllables strictly increasing
    M = len(syl)
    back = np.zeros((K, M), np.int32)
    prev = dps[0].copy()
    for k in range(1, K):
        pm = np.maximum.accumulate(prev)
        pa = np.zeros(M, np.int32)
        am = 0
        # argmax of prefix max (strictly before j)
        best_i = np.where(prev == pm, np.arange(M), 0)
        pa = np.maximum.accumulate(best_i).astype(np.int32)
        cur = np.full(M, -1e9, np.float32)
        cur[1:] = dps[k, 1:] + pm[:-1]
        back[k, 1:] = pa[:-1]
        prev = cur
    choice = np.zeros(n, np.int64)
    j = int(np.argmax(prev))
    for k in range(K - 1, -1, -1):
        choice[k] = j
        j = back[k, j]
    # --- ieung/mieum final disambiguation by stroke geometry
    FM, FO = 16, 21   # jongseong indices of mieum / ieung
    nfix = 0
    rulefix = set()
    for k in range(n):
        ch = syl[choice[k]]
        kind = _final_box_kind(bits[HANGUL_FIRST + k])
        want = {'o': (FM, FO), 'm': (FO, FM)}.get(kind)
        if not want:
            continue
        alt_ch = _swap_final(ch, *want)
        if not alt_ch:
            continue
        j = ord(alt_ch) - 0xAC00
        if k < K:
            lo = choice[k - 1] if k > 0 else -1
            hi = choice[k + 1] if k + 1 < K else M
            if not (isks[j] and lo < j < hi):
                continue
        score[k, j] = dps[k, j] = score[k, choice[k]] + 0.05
        choice[k] = j
        rulefix.add(k)
        nfix += 1
    print('ieung/mieum fixes:', nfix, file=sys.stderr)
    conf_k = np.zeros(n)
    for k in range(K):
        lo = choice[k - 1] + 1 if k > 0 else 0
        hi = choice[k + 1] if k + 1 < K else M
        seg = dps[k, lo:hi].copy()
        seg[choice[k] - lo] = -1e9
        other = seg.max() if len(seg) > 1 else -1.0
        conf_k[k] = min(1.0, score[k, choice[k]] - other)
        if k in rulefix:
            conf_k[k] = 0.2   # decided by the ieung/mieum stroke rule
    # --- extras: free best match
    for k in range(K, n):
        o = np.argsort(-score[k])[:2]
        choice[k] = o[0]
        conf_k[k] = score[k, o[0]] - score[k, o[1]]
    free = np.argmax(score, axis=1)
    mapping, conf, alt = {}, {}, {}
    for k, idx in enumerate(range(HANGUL_FIRST, HANGUL_LAST + 1)):
        h = '%04x' % index_to_code(idx)
        if idx in NON_HANGUL:
            mapping[h] = NON_HANGUL[idx]; conf[h] = 1.0; alt[h] = []
            continue
        if idx in VERIFIED:
            mapping[h] = VERIFIED[idx]; conf[h] = 1.0
            alt[h] = [syl[free[k]], round(float(score[k, free[k]]), 3), None]
            continue
        mapping[h] = syl[choice[k]]
        conf[h] = round(float(conf_k[k]), 4)
        alt[h] = [syl[free[k]], round(float(score[k, free[k]]), 3),
                  round(float(score[k, choice[k]]), 3)]
    json.dump({'map': mapping, 'confidence': conf, 'alt': alt,
               'note': 'map: code->syllable. confidence: score margin of chosen over best other candidate allowed by sort order (idx<=%d) or over 2nd best (extras); 0.2 = set by ieung/mieum geometry rule; <%.2f is low. alt: [free best, its score, chosen score]' % (SORTED_LAST, LOW_CONF)},
              open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    _check_png(bits, mapping, conf)
    return mapping, conf

def _check_png(bits, mapping, conf):
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.truetype(os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'malgun.ttf'), 30)
    lab = ImageFont.truetype(os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', 'malgun.ttf'), 11)
    low = sorted([h for h in conf if conf[h] < LOW_CONF], key=lambda h: conf[h])
    cols = 8
    rows = max(1, (len(low) + cols - 1) // cols)
    W, H = 130, 62
    im = Image.new('RGB', (cols * W, rows * H), 'white')
    d = ImageDraw.Draw(im)
    for n, h in enumerate(low):
        y, x = divmod(n, cols)
        ox, oy = x * W, y * H
        g = bits[code_to_index(int(h, 16))]
        gi = Image.fromarray((255 - g * 255).astype(np.uint8)).resize((48, 45), Image.NEAREST)
        im.paste(gi, (ox + 2, oy + 2))
        d.text((ox + 54, oy - 2), mapping[h], fill='black', font=font)
        d.text((ox + 54, oy + 44), '%s %.3f' % (h, conf[h]), fill='red', font=lab)
    im.save(OUT_PNG)

# ---------------------------------------------------------------- encode / decode
_MAP = None
def _load_map():
    global _MAP
    if _MAP is None:
        m = json.load(open(OUT_JSON, encoding='utf-8'))['map']
        dec = {int(h, 16): s for h, s in m.items()}
        enc = {}
        for c in sorted(dec):           # canonical code only 
            if c == index_to_code(code_to_index(c)):
                enc.setdefault(dec[c], c)
        _MAP = (enc, dec)
    return _MAP

_ASCII_FW = {' ': 0x8140}
def _fw(ch):
    """Full-width Shift-JIS code for an ASCII char if the font has it."""
    if ch in _ASCII_FW:
        return _ASCII_FW[ch]
    if ch == '~':
        return 0x8160
    o = ord(ch)
    if 0x21 <= o <= 0x7E:
        try:
            b = chr(o + 0xFEE0).encode('cp932')
        except UnicodeEncodeError:
            return None
        if len(b) == 2:
            c = (b[0] << 8) | b[1]
            idx = code_to_index(c)
            if idx is not None and idx < HANGUL_FIRST and _bits()[idx].any():
                return c
    return None

_B = None
def _bits():
    global _B
    if _B is None:
        _B = load_font()
    return _B

def encode(s):
    enc, _ = _load_map()
    out = bytearray()
    for ch in s:
        if ch in enc:
            c = enc[ch]
        elif ch == '\n':
            out.append(0x0A); continue
        else:
            c = _fw(ch)
            if c is None:
                try:
                    b = ch.encode('cp932')
                except UnicodeEncodeError:
                    raise ValueError('cannot encode %r' % ch)
                if len(b) == 1:
                    out += b; continue
                c = (b[0] << 8) | b[1]
        out += bytes([c >> 8, c & 0xFF])
    return bytes(out)

def decode(b):
    _, dec = _load_map()
    out, i = [], 0
    while i < len(b):
        x = b[i]
        if x >= 0x81 and i + 1 < len(b):
            c = (x << 8) | b[i + 1]
            i += 2
            if c in dec:
                out.append(dec[c])
            elif c == 0x8140:
                out.append(' ')
            else:
                try:
                    u = bytes([c >> 8, c & 0xFF]).decode('cp932')
                    if u == '～':
                        u = '~'
                    elif 0xFF01 <= ord(u) <= 0xFF5E:   # full-width ASCII -> ASCII
                        u = chr(ord(u) - 0xFEE0)
                    out.append(u)
                except UnicodeDecodeError:
                    out.append('{%04x}' % c)
        else:
            out.append(chr(x) if 0x20 <= x < 0x7F or x == 0x0A else '{%02x}' % x)
            i += 1
    return ''.join(out)

GROUND_TRUTH = [
    ('89df 89cd 8bde 8997', '멸망하라'),
    ('8ac9 88d7 8958 8944 889f 8a6f 8a7d 88bb 889f 8aa9 895b 8960', '여기는네가살세계가아니다'),
]

def check_gt():
    _, dec = _load_map()
    ok = tot = 0
    for codes, txt in GROUND_TRUTH:
        got = ''.join(dec.get(int(c, 16), '?') for c in codes.split())
        for a, e in zip(got, txt):
            ok += a == e; tot += 1
        print(codes, '->', got, '(expected', txt + ')')
    print('GT %d/%d' % (ok, tot))
    return ok, tot

if __name__ == '__main__':
    if '--check' not in sys.argv:
        build()
    check_gt()
