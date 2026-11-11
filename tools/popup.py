"""Status pop-up words (potions / resist / status: "GUARD", "STRENGTH -UP", "PROTECTION FROM FIRE" ...) in Korean.

On PS1 these are NOT text strings: they are a small boxed 4bpp picture font in F_GAME.BIN (and the identical
F_GAME2.BIN), 128x128 block #8 at file offset 0x10000 (64 bytes/row, low nibble = even x), words at
x 32..127, y 74..127 of that block (= tpage-relative u,v).  They are drawn by the DRA entity at 0x80118164,
which picks one 8-byte rect from the table at DRA 0xCF40 (VA 0x800ACF40, 21 entries):
    u0, v0, u1, v1 (bytes, u1/v1 exclusive), clut (u16), type (u16)
type 1 = the word alone, type 2 = word + the '-UP' rect (entry 5, appended right),
type 3 = the 'PROTECTION FROM' rect (entry 6, placed left) + word.  The quad width is (u1-u0) (half-width
= (u1-u0)/2), height is fixed 8 rows, so rects can be re-laid out freely as long as height stays 8.

This module redraws the words with Galmuri7 (OFL) Hangul in the Saturn-approved wording (words.SEGS of the
Saturn handoff), re-packs them into the same area and rewrites the rect table.  Colours follow the original
(letters = 4 upper rows / 5 lower rows) but without the box: transparent 0 with a palette-2 drop shadow.

Build use:
    import popup
    dra  = popup.patch_dra_popup(dra)                       # DRA.BIN
    data = popup.patch_fgame_popup('BIN/F_GAME.BIN', data)  # also 'BIN/F_GAME2.BIN' (other names: unchanged)
`python popup.py` prints the layout and writes work/popup_preview.png.
"""
import os, sys, struct, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(HERE, '..', 'work')
BDF7 = os.path.join(WORK, 'dl', 'galmuri', 'Galmuri7.bdf')   # extracted from work/dl/galmuri/g.zip

BLOCK = 0x10000                 # F_GAME block #8 (128x128, 4bpp)
REGION = (32, 74, 128, 128)     # x0, y0, x1, y1 (exclusive) of the word area inside the block
BANDS = (74, 83, 92, 101, 110, 119)   # v0 of each 8-row shelf (original rows)
RH = 8
# a sparkle sprite pokes into the first shelf at x>=116 (rows 68..75): keep it
KEEP = (112, 74, 128, 76)
TABLE = 0xCF40

# Korean words (Saturn words.SEGS wording)
WORDS = {
    'GUARD': '가드', 'POISON': '독', 'CURSE': '저주', 'STONE': '석화', 'MISS': '미스!', 'UP': '상승',
    'PROTECTION FROM': '내성 획득:', 'DOWN': '하락', 'DEFENCE': '방어력', 'OFFENCE': '공격력', 'LUCK': '행운',
    'INTELLIGENCE': '지능', 'STRENGTH': '힘', 'FIRE': '불꽃', 'ICE': '얼음', 'THUNDER': '번개', 'HOLY': '신성',
    'DARK': '어둠',
    # present in the sheet but not referenced by the table (kept translated for completeness)
    'CRITICAL': '크리티컬!', 'PHYSICAL': '물리',
}
# table entry -> (word, original 8 bytes)
ENTRIES = [
    ('GUARD', '434a595285010100'),   # 0
    ('POISON', '4e53665bb1010100'),   # 1
    ('CURSE', '2053365bb1010100'),   # 2
    ('STONE', '37534d5bb1010100'),   # 3
    ('MISS', '5a4a6f5282010100'),   # 4
    ('UP', '205c2d6482010100'),   # 5
    ('PROTECTION FROM', '206e5b7682010100'),   # 6
    ('DOWN', '67537c5b82010100'),   # 7
    ('DEFENCE', '3b65596db4010200'),   # 8
    ('OFFENCE', '5a65786db4010200'),   # 9
    ('LUCK', '20653a6db4010200'),   # 10
    ('INTELLIGENCE', '515c7f64b4010200'),   # 11
    ('STRENGTH', '2e5c5064b4010200'),   # 12
    ('FIRE', '5c6e6c76b8010300'),   # 13
    ('ICE', '33773f7fb8010300'),   # 14
    ('THUNDER', '40775e7fb8010300'),   # 15
    ('CURSE', '2053365bb8010300'),   # 16
    ('HOLY', '2077327fb8010300'),   # 17
    ('STONE', '37534d5bb8010300'),   # 18
    ('DARK', '6d6e7f76b8010300'),   # 19
    ('HOLY', '2077327fb8010300'),   # 20
]
ENTRIES = [(w, bytes.fromhex(h.replace(' ', ''))) for w, h in ENTRIES]

_G = None
def _font():
    global _G
    if _G is None:
        if not os.path.exists(BDF7):
            import zipfile
            zipfile.ZipFile(os.path.join(os.path.dirname(BDF7), 'g.zip')).extract('Galmuri7.bdf', os.path.dirname(BDF7))
        G = {}; lines = open(BDF7, encoding='latin1').read().split('\n'); i = 0
        while i < len(lines):
            l = lines[i]
            if l.startswith('ENCODING'): enc = int(l.split()[1])
            elif l.startswith('BBX'): bbx = list(map(int, l.split()[1:]))
            elif l.startswith('DWIDTH'): dw = int(l.split()[1])
            elif l == 'BITMAP':
                w, h, xo, yo = bbx; nb = ((w + 7) // 8) * 8
                rows = [int(lines[i + 1 + j], 16) for j in range(h)]
                G[enc] = (w, h, xo, yo, dw, [[(r >> (nb - 1 - x)) & 1 for x in range(w)] for r in rows])
                i += h
            i += 1
        _G = G
    return _G

def word_image(s):
    """8 rows x (text width + 2) of palette indices: transparent 0, letters 4 (rows 0-3) / 5 (rows 4-6),
    drop shadow 2."""
    G = _font(); pts = []; x = 0
    for i, c in enumerate(s):
        gw, gh, xo, yo, dw, rows = G[ord(c)]
        top = 7 - gh - yo                       # Hangul (7 tall, yo 0) -> rows 0..6; baseline row 6
        for y in range(gh):
            for xx in range(gw):
                if rows[y][xx]:
                    pts.append((top + y, x + xo + xx))
        x += dw if i < len(s) - 1 else gw + xo
    w = x + 2
    im = [[0] * w for _ in range(RH)]          # no box (it looked like an opaque square behind the Hangul)
    for y, xx in pts:                           # 1-px drop shadow (palette 2, the old box colour) right-down
        assert 0 <= y < RH, (s, y)
        if y + 1 < RH: im[y + 1][xx + 2] = 2
    for y, xx in pts:
        im[y][xx + 1] = 4 if y < 4 else 5
    return im

def layout():
    """Shelf-pack every word: rect = 1 blank column + box (as the original: u0 = blank col, u1 exclusive)."""
    order = sorted(WORDS, key=lambda k: -len(word_image(WORDS[k])[0]))
    free = {v: (REGION[0], KEEP[0] if v == KEEP[1] else REGION[2]) for v in BANDS}
    used = {v: free[v][0] for v in BANDS}
    rects = {}
    for k in order:
        w = len(word_image(WORDS[k])[0]) + 1
        for v in BANDS:
            if used[v] + w <= free[v][1] and used[v] + w <= 127:
                rects[k] = (used[v], v, used[v] + w, v + RH); used[v] += w
                break
        else:
            raise ValueError('pop-up words do not fit: %s' % k)
    return rects

def _px_get(blk, x, y):
    b = blk[y * 64 + x // 2]
    return (b >> 4) if x & 1 else (b & 15)

def _px_set(blk, x, y, v):
    o = y * 64 + x // 2
    blk[o] = (blk[o] & 0x0F) | (v << 4) if x & 1 else (blk[o] & 0xF0) | v

def _check_region(blk):
    """The word area must still be the US original."""
    h = hashlib.sha1()
    for y in range(REGION[1], REGION[3]):
        h.update(bytes(blk[y * 64 + REGION[0] // 2: y * 64 + REGION[2] // 2]))
    return h.hexdigest()

US_REGION_SHA1 = None
def _us_sha1():
    global US_REGION_SHA1
    if US_REGION_SHA1 is None:
        us = open(os.path.join(WORK, 'U', 'BIN', 'F_GAME.BIN'), 'rb').read()
        US_REGION_SHA1 = _check_region(us[BLOCK:BLOCK + 0x2000])
    return US_REGION_SHA1

def patch_block(blk):
    blk = bytearray(blk)
    assert _check_region(blk) == _us_sha1(), 'pop-up word sheet is not the US original'
    for y in range(REGION[1], REGION[3]):
        for x in range(REGION[0], REGION[2]):
            if not (KEEP[0] <= x < KEEP[2] and KEEP[1] <= y < KEEP[3]):
                _px_set(blk, x, y, 0)
    for k, (u0, v0, u1, v1) in layout().items():
        im = word_image(WORDS[k])
        for y in range(RH):
            for x, c in enumerate(im[y]):
                _px_set(blk, u0 + 1 + x, v0 + y, c)
    return bytes(blk)

def patch_fgame_popup(name, data):
    base = name.replace('\\', '/').split('/')[-1].split(';')[0].upper()
    if base not in ('F_GAME.BIN', 'F_GAME2.BIN'):
        return data
    return data[:BLOCK] + patch_block(data[BLOCK:BLOCK + 0x2000]) + data[BLOCK + 0x2000:]

def patch_dra_popup(dra):
    dra = bytearray(dra); rects = layout()
    for i, (k, orig) in enumerate(ENTRIES):
        o = TABLE + i * 8
        assert dra[o:o + 8] == orig, (i, k, dra[o:o + 8].hex())
        dra[o:o + 4] = bytes(rects[k])
    return bytes(dra)

def preview(path):
    import numpy as np
    from PIL import Image
    fg = open(os.path.join(WORK, 'U', 'BIN', 'F_GAME.BIN'), 'rb').read()
    out = []
    for blk in (fg[BLOCK:BLOCK + 0x2000], patch_block(fg[BLOCK:BLOCK + 0x2000])):
        a = np.frombuffer(blk, np.uint8); out.append(np.stack([a & 15, a >> 4], 1).reshape(128, 128)[64:128])
    pal = np.zeros((16, 3), np.uint8); pal[:] = [[i * 17] * 3 for i in range(16)]
    pal[2] = (40, 40, 90); pal[4] = (255, 255, 255); pal[5] = (200, 200, 120)
    img = np.vstack([out[0], np.full((2, 128), 1, np.uint8), out[1]])
    Image.fromarray(pal[img]).resize((128 * 5, img.shape[0] * 5), Image.NEAREST).save(path)

if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    R = layout()
    for k in WORDS:
        print('%-16s %-8s %s' % (k, WORDS[k], R[k]))
    dra = open(os.path.join(WORK, 'U', 'DRA.BIN'), 'rb').read()
    nd = patch_dra_popup(dra)
    for i, (k, _) in enumerate(ENTRIES):
        print(i, k, nd[TABLE + i * 8:TABLE + i * 8 + 8].hex())
    p = os.path.join(WORK, 'popup_preview.png'); preview(p); print('preview ->', p)
