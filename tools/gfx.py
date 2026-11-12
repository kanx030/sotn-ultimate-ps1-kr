"""Korean replacements for English text that exists as *graphics* (not strings).

Called by the build for every file it writes (and for every path in GFX_FILES):
    data = gfx.patch_file('BIN/F_GAME.BIN', data)
Only graphics bytes are changed. Every patch checks that the target region still holds the
original US bytes and silently skips it otherwise, so running twice or on an already-changed
file is harmless. draa.patch_fgame's 8x8 sheet (F_GAME 0x30000-0x31FFF) is never touched.

Layout notes (see work/gfx_report.md):
  * F_*.BIN graphics files are 64hw x 256 VRAM columns, each stored as four 32hw x 128 4bpp
    blocks of 0x2000 bytes in the order TL, TR, BL, BR.
  * DRA's "Life max up / Heart max up / Level up / Got an item" picture is a compressed
    128x128 4bpp image (DecompressData 0x800E8FAC format) at va 0x800C217C, uploaded to (800,256).

Fonts (all SIL OFL): Galmuri7/9/11 (work/dl/galmuri), Noto Sans KR / Noto Serif KR (Windows fonts dir).

Run `python gfx.py` to write before/after previews to work/gfx_preview/.
"""
import os, sys
import numpy as np

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
WORK = os.path.join(ROOT, 'work')
U_DIR = os.path.join(WORK, 'U')
K_DIR = os.path.join(WORK, 'K')
GALMURI = os.path.join(WORK, 'dl', 'galmuri')
FONTS_DIR = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts')
NOTO_SANS = os.path.join(FONTS_DIR, 'NotoSansKR-VF.ttf')
NOTO_SERIF = os.path.join(FONTS_DIR, 'NotoSerifKR-VF.ttf')
PREVIEW = os.path.join(WORK, 'gfx_preview')

GFX_FILES = ['BIN/F_GAME.BIN', 'BIN/F_GAME2.BIN', 'BIN/F_TITLE0.BIN', 'BIN/F_TITLE1.BIN', 'ST/SEL/F_SEL.BIN',
             'ST/SEL/SEL.BIN', 'DRA.BIN', 'BIN/F_PROLO0.BIN']

LOG = []          # (file, what, status) - filled by patch_file, used for the report / previews


def _rd(*p):
    with open(os.path.join(*p), 'rb') as f:
        return f.read()


_UCACHE = {}
def _u(name):
    if name not in _UCACHE:
        _UCACHE[name] = _rd(U_DIR, *name.split('/'))
    return _UCACHE[name]


def _k(name):
    return _rd(K_DIR, *name.split('/'))


# ------------------------------------------------------------------ 4bpp block helpers
def blk_get(d, off):
    a = np.frombuffer(bytes(d[off:off + 0x2000]), np.uint8).reshape(128, 64)
    o = np.zeros((128, 128), np.uint8)
    o[:, 0::2] = a & 15
    o[:, 1::2] = a >> 4
    return o


def blk_put(d, off, img):
    img = img.astype(np.uint8)
    d[off:off + 0x2000] = ((img[:, 0::2] & 15) | ((img[:, 1::2] & 15) << 4)).astype(np.uint8).tobytes()


# ------------------------------------------------------------------ fonts
_BDF = {}
def bdf(size):
    if size not in _BDF:
        G = {}
        lines = open(os.path.join(GALMURI, 'Galmuri%d.bdf' % size), encoding='latin1').read().split('\n')
        i = 0
        while i < len(lines):
            l = lines[i]
            if l.startswith('ENCODING'):
                enc = int(l.split()[1])
            elif l.startswith('BBX'):
                bbx = list(map(int, l.split()[1:]))
            elif l.startswith('DWIDTH'):
                dw = int(l.split()[1])
            elif l == 'BITMAP':
                w, h, xo, yo = bbx
                nb = ((w + 7) // 8) * 8
                rows = [int(lines[i + 1 + j], 16) for j in range(h)]
                G[enc] = (w, h, xo, yo, dw, np.array([[(r >> (nb - 1 - x)) & 1 for x in range(w)] for r in rows], np.uint8))
                i += h
            i += 1
        _BDF[size] = G
    return _BDF[size]


def galmuri(text, size, spacing=0, space_w=None):
    """1-bit mask, height = size (cell top = ascent line). Returns (mask)."""
    G = bdf(size)
    asc = size  # Galmuri: Hangul cell is size px tall with yo=0 baseline at bottom
    x = 0
    pts = []
    for i, ch in enumerate(text):
        if ch == ' ' and space_w is not None:
            x += space_w
            continue
        w, h, xo, yo, dw, rows = G[ord(ch)]
        top = asc - h - yo
        pts.append((x + xo, top, rows))
        x += (dw if i < len(text) - 1 else w + xo) + (spacing if i < len(text) - 1 else 0)
    W = max(1, x)
    m = np.zeros((size + 3, W + 2), np.uint8)
    for px, py, rows in pts:
        hh, ww = rows.shape
        y0 = max(0, py)
        m[y0:py + hh, px:px + ww] |= rows[y0 - py:]
    m = m[:size]
    xs = np.nonzero(m.any(0))[0]
    return m[:, :xs[-1] + 1] if len(xs) else m


def noto(text, px, weight=700, serif=False, shear=0.0, box_h=None):
    """Anti-aliased coverage (float 0..1), cropped to the ink bbox horizontally and to the
    font's line box vertically (so lines share a baseline)."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(NOTO_SERIF if serif else NOTO_SANS, px * 4)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    l, t, r, b = f.getbbox(text)
    im = Image.new('L', (r - l + 8 + px * 4, b - t + 8), 0)
    ImageDraw.Draw(im).text((4 - l + (px * 2 if shear else 0), 4 - t), text, font=f, fill=255)
    if shear:
        h = im.height
        im = im.transform(im.size, Image.AFFINE, (1, shear, -shear * h / 2, 0, 1, 0), resample=Image.BICUBIC)
    a = np.asarray(im, np.float32) / 255.0
    ys = np.nonzero(a.max(1) > 0.02)[0]
    xs = np.nonzero(a.max(0) > 0.02)[0]
    a = a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]
    # box-filter down by 4
    H, W = (a.shape[0] + 3) // 4, (a.shape[1] + 3) // 4
    pad = np.zeros((H * 4, W * 4), np.float32)
    pad[:a.shape[0], :a.shape[1]] = a
    return pad.reshape(H, 4, W, 4).mean((1, 3))


def fit_noto(text, max_w, max_h, weight=700, serif=False, shear=0.0, start=None):
    px = start or max_h + 4
    while px > 6:
        c = noto(text, px, weight, serif, shear)
        if c.shape[0] <= max_h and c.shape[1] <= max_w:
            return c
        px -= 1
    return noto(text, 6, weight, serif, shear)


def dilate(m):
    o = m.copy()
    o[1:, :] |= m[:-1, :]; o[:-1, :] |= m[1:, :]
    o[:, 1:] |= m[:, :-1]; o[:, :-1] |= m[:, 1:]
    o[1:, 1:] |= m[:-1, :-1]; o[:-1, :-1] |= m[1:, 1:]
    o[1:, :-1] |= m[:-1, 1:]; o[:-1, 1:] |= m[1:, :-1]
    return o


def bold(m):
    o = m.copy()
    o[:, 1:] |= m[:, :-1]
    return o


def aa_outline_indices(cov, lo=2, hi=15, outline=1):
    """coverage -> palette ramp lo..hi, plus a dark 1-px outline (index `outline`) around it,
    the way the US 'Now Loading' / 'Level up' pictures are drawn. Returns an array 2px larger."""
    H, W = cov.shape
    c = np.zeros((H + 2, W + 2), np.float32)
    c[1:-1, 1:-1] = cov
    ink = c >= 0.08
    out = np.zeros(c.shape, np.uint8)
    out[dilate(ink)] = outline
    v = np.clip(np.round(lo + c * (hi - lo)), lo, hi).astype(np.uint8)
    out[ink] = v[ink]
    return out


def paste(dst, src, x, y, transparent=0):
    h, w = src.shape
    sub = dst[y:y + h, x:x + w]
    m = src != transparent
    sub[m[:sub.shape[0], :sub.shape[1]]] = src[:sub.shape[0], :sub.shape[1]][m[:sub.shape[0], :sub.shape[1]]]


# ------------------------------------------------------------------ guarded block editing
class Blocks:
    """Edit a set of 0x2000 blocks of a file as images; commit only if all source blocks are
    still the US originals."""
    def __init__(self, data, name, offs):
        self.d, self.name, self.offs = data, name, offs
        U = _u(name)
        self.ok = all(bytes(data[o:o + 0x2000]) == U[o:o + 0x2000] for o in offs)
        self.img = {o: blk_get(data, o) for o in offs}

    def commit(self):
        if self.ok:
            for o, im in self.img.items():
                blk_put(self.d, o, im)
        return self.ok


def _log(name, what, ok):
    LOG.append((name, what, 'patched' if ok else 'SKIPPED (region not US original)'))


# ------------------------------------------------------------------ F_GAME / F_GAME2
FG_LOGO = (0x2C000, 0x30000)      # 128x128 8bpp logo (two 32hw blocks side by side)
FG_LOGO_CLUT = (0x41A00, 0x41C00)  # its 256-colour palette (CLUT rows 208-223)

# status / potion pop-up words, F_GAME block 0x10000.  (x0, x1, y0) box, Korean, align
WORDS = [
    (33, 65, 75, '치명타!', 'c'), (68, 88, 75, '가드', 'c'), (91, 110, 75, '미스!', 'c'),
    (33, 53, 84, '저주', 'c'), (56, 76, 84, '석화', 'c'), (79, 101, 84, '독', 'c'), (104, 123, 84, '다운', 'l'),
    (33, 44, 93, '업', 'l'), (47, 79, 93, '힘', 'r'), (82, 126, 93, '지능', 'r'),
    (37, 57, 102, '행운', 'r'), (60, 88, 102, '방어력', 'r'), (91, 119, 102, '공격력', 'r'),
    (33, 71, 111, '내성 획득', 'r'), (74, 90, 111, ':', 'l'), (93, 107, 111, '불꽃', 'l'), (110, 126, 111, '어둠', 'l'),
    (33, 49, 120, '신성', 'l'), (52, 62, 120, '빙', 'l'), (65, 93, 120, '번개', 'l'), (96, 126, 120, '물리', 'l'),
]
WORD_EN = ['CRITICAL!!', 'GUARD', 'MISS!!', 'CURSE', 'STONE', 'POISON', '-DOWN', '-UP', 'STRENGTH',
           'INTELLIGENCE', 'LUCKY', 'DEFENCE', 'OFFENCE', 'PROTECTION', 'FROM', 'FIRE', 'DARK',
           'HOLY', 'ICE', 'THUNDER', 'PHYSICAL']


def _word_img(text, w):
    """7-row word in the pop-up style: box colour 2, glyph 4 (upper rows) / 5 (lower rows)."""
    for sp in (1, 0):
        m = galmuri(text, 7, spacing=sp - 1, space_w=3)
        if m.shape[1] <= w:
            break
    if m.shape[1] > w:
        m = m[:, :w]
    im = np.full((7, m.shape[1]), 2, np.uint8)
    im[m.astype(bool)] = 4
    low = np.zeros_like(m, bool)
    low[4:] = True
    im[m.astype(bool) & low] = 5
    return im


def patch_words(d, name):
    B = Blocks(d, name, [0x10000])
    o = B.img[0x10000]
    for x0, x1, y0, ko, al in WORDS:
        w = x1 - x0 + 1
        o[y0:y0 + 7, x0:x1 + 1] = 0
        g = _word_img(ko, w - 2)
        gw = g.shape[1] + 2
        box = np.full((7, gw), 2, np.uint8)
        box[:, 1:-1] = g
        x = {'l': x0, 'r': x1 + 1 - gw, 'c': x0 + (w - gw) // 2}[al]
        o[y0:y0 + 7, x:x + gw] = box
    _log(name, 'status pop-up words (0x10000)', B.commit())


def patch_loading(d, name):
    B = Blocks(d, name, [0x16000])
    o = B.img[0x16000]
    o[104:128, :] = 0
    cov = fit_noto('불러오는 중', 120, 15, weight=800, shear=0.22)
    g = aa_outline_indices(cov)
    x = (128 - g.shape[1]) // 2
    y = 108 + (19 - g.shape[0]) // 2
    paste(o, g, x, y)
    _log(name, "'Now Loading' (0x16000)", B.commit())


def _outlined(mask, fill_top, fill_bot, split, outline, bg=None, pad=1):
    """mask -> indexed image with 1px outline; rows < split use fill_top."""
    H, W = mask.shape
    m = np.zeros((H + 2 * pad, W + 2 * pad), bool)
    m[pad:pad + H, pad:pad + W] = mask.astype(bool)
    out = np.zeros(m.shape, np.uint8) if bg is None else np.full(m.shape, bg, np.uint8)
    out[dilate(m)] = outline
    top = np.zeros(m.shape, bool)
    top[:pad + split] = True
    out[m & top] = fill_top
    out[m & ~top] = fill_bot
    return out


def patch_hud_status(d, name):
    """'DEAD' / 'STONE' HUD labels, block 0x38000 rows 50-60: letter colour 1 outlined with 9."""
    B = Blocks(d, name, [0x38000])
    o = B.img[0x38000]
    parts = [(48, 70), (73, 95)]          # 'DEAD' | 'STONE' (letters joined, gap only on row 50)
    o[50:61, 48:96] = 0
    for (x0, x1), ko in zip(parts, ('사망', '석화')):
        o[50:61, x0:x1 + 1] = 0
        m = bold(galmuri(ko, 9, spacing=0))
        im = _outlined(m, 1, 1, 9, 9)
        x = x0 + max(0, (x1 - x0 + 1 - im.shape[1]) // 2)
        paste(o, im[:, :x1 - x + 1], x, 50)
    # ON/OFF toggle pills, rows 116-123: (x0, x1, background, letter colour, text)
    for x0, x1, bg, col, ko in ((6, 23, 3, 1, '켬'), (24, 43, 5, 4, '끔'), (55, 71, 5, 4, '켬'), (72, 93, 3, 1, '끔')):
        seg = o[116:124, x0:x1 + 1]
        seg[:] = bg
        m = galmuri(ko, 7).astype(bool)
        g = np.full((8, m.shape[1] + 1), bg, np.uint8)
        sh = np.zeros(g.shape, bool)
        sh[1:, 1:] = m
        g[sh] = 6
        g[:7, :m.shape[1]][m] = col
        x = (x1 - x0 + 1 - g.shape[1]) // 2
        seg[:, x:x + g.shape[1]] = g[:, :seg.shape[1] - x]
    _log(name, "HUD 'DEAD' / 'STONE', ON/OFF toggles (0x38000)", B.commit())


def patch_richter_hud(d, name):
    """F_GAME2 0x18000: 'RICHTER REST x00' and 'PAUSE PUSH START' panels (bg 9, text F)."""
    B = Blocks(d, name, [0x18000])
    o = B.img[0x18000]
    # panel 1: name + REST
    o[47:51, 106:125] = 9                  # 'REST' -> blank
    o[47:58, 66:104] = 9                   # 'RICHTER'
    m = bold(galmuri('리히터', 9, spacing=1))
    paste(o, np.where(m, 15, 9).astype(np.uint8), 66 + (38 - m.shape[1]) // 2, 48)
    # panel 2: PAUSE PUSH START
    o[70:82, 66:126] = 9
    m = bold(galmuri('일시정지', 9, spacing=1))
    paste(o, np.where(m, 15, 9).astype(np.uint8), 66 + (60 - m.shape[1]) // 2, 71)
    _log(name, "Richter HUD 'RICHTER/REST', 'PAUSE PUSH START' (0x18000)", B.commit())


# '마리아' in the style of bold(galmuri 9) used for '리히터', drawn by hand: bold(galmuri) cuts off the last column
# (the 'ㅏ' stub of '아') and leaves '마' a 1px stub that is lost on screen -> 2px stubs here.
_MARIA_PLATE = np.array([[c == '#' for c in r] for r in (
    '######.##....######.##..####..##..',
    '##..##.##........##.##.##..##.##..',
    '##..##.##........##.##.##..##.##..',
    '##..##.##....######.##.##..##.##..',
    '##..##.####..##.....##.##..##.####',
    '##..##.##....##.....##.##..##.##..',
    '##..##.##....##.....##.##..##.##..',
    '######.##....######.##..####..##..',
    '.......##...........##........##..')])


def patch_maria_hud(d, name):
    """F_GAME2 0x6000: Ultimate's 'MARIA' HUD name plate (rows 12-27, x 40-103; inner bg 9, letters F at rows
    16-23 x 54-89; ornaments at x <= 49 / >= 94) -> '마리아' like the Richter plate. Found by matching the
    plate pixels in VRAM (Maria start, VRAM row 400) against the file. F_GAME2 goes to VRAM at boot only:
    check on a freshly booted game, not on an old state."""
    B = Blocks(d, name, [0x6000])
    o = B.img[0x6000]
    o[15:25, 51:93] = 9
    m = _MARIA_PLATE
    paste(o, np.where(m, 15, 9).astype(np.uint8), 51 + (42 - m.shape[1]) // 2, 15 + (10 - m.shape[0]) // 2)
    _log(name, "Maria HUD name plate 'MARIA' (0x6000)", B.commit())


# '얼티메이트' added to the K logo the way the Saturn Korean Ultimate patch did it (stat/titlelogo4.py):
# orange fill, light top -> red-orange bottom, dark brown outline, under the right part of the logo.
ULT_TOP_RGB, ULT_BOT_RGB, ULT_OUT_RGB = (255, 184, 80), (216, 72, 16), (48, 16, 0)
T0_ULT_PX = 18
T0_ULT_RIGHT, T0_ULT_TOP = 472, 74      # F_TITLE0 512x128 logo: K ink rows 0-73; US ink reaches row 122 / x 482


def _pal_rgb(pal):
    pal = np.asarray(pal, np.uint32)
    return np.stack([(pal & 31) << 3, ((pal >> 5) & 31) << 3, ((pal >> 10) & 31) << 3], -1).astype(np.float32)


def _ultimate_onto(logo, pal, cov, right, top, ow):
    """Draw coverage `cov` onto an 8bpp logo: gradient fill blended into an `ow`-px dark outline, each pixel mapped
    to the nearest existing CLUT colour (index 0 / black-transparent entries excluded), so every CLUT row
    (normal / dark / fade) stays consistent. Asserts the target area is empty in the logo."""
    H, W = cov.shape
    c = np.zeros((H + 2 * ow, W + 2 * ow), np.float32)
    c[ow:ow + H, ow:ow + W] = cov
    o = c >= 0.15
    for _ in range(ow):
        o = dilate(o)
    t = (np.arange(c.shape[0], dtype=np.float32) - ow) / max(1, H - 1)
    t = np.clip(t, 0, 1)[:, None, None]
    fill = np.array(ULT_TOP_RGB, np.float32) * (1 - t) + np.array(ULT_BOT_RGB, np.float32) * t
    col = np.array(ULT_OUT_RGB, np.float32) * (1 - c[..., None]) + fill * c[..., None]
    rgb = _pal_rgb(pal)
    ok = (np.asarray(pal) & 0x7FFF) != 0
    ok[0] = False
    cand = np.nonzero(ok)[0]
    dist = ((col[o][:, None, :] - rgb[cand][None]) ** 2).sum(-1)
    idx = np.zeros(c.shape, np.uint8)
    idx[o] = cand[dist.argmin(1)]
    y, x = top, right - c.shape[1]
    sub = logo[y:y + c.shape[0], x:x + c.shape[1]]
    assert sub.shape == c.shape and not sub[o].any(), 'Ultimate text area not empty'
    sub[o] = idx[o]


# Now Loading screen logo. DRA 0x800E5120-0x800E519C draws ONE sprite from it: tpage 0x9D (8bpp, VRAM 832,256),
# CLUT 0x1D0, uv (0,128)-(127,191) on screen (112,160)-(239,223), i.e. texture rows 0-63, 1:1. The PS1 leaves the
# right/bottom edge out, so only cols 0-126 x rows 0-62 show (US ink: cols 4-122, rows 0-62; K's port reached col 127).
# The loading screen is 256 px wide and the title 512, so 1 texel here is as wide as 2 title texels while rows match:
# a faithful shrink is sx, 2*sx. Built fresh from the title logo (K art + our '얼티메이트'), not K's blurry small copy.
FG_VIS_W, FG_VIS_H = 127, 63
FG_SX = 123 / 473                       # title ink x 20-492 -> 123 texels (x 2-124)
FG_SUB_K = 1.5                          # '월하의 야상곡' drawn 1.5x the faithful size (else 6 px per syllable)
FG_SHARPEN = 0.5
FG_ULT_PX, FG_ULT_RIGHT, FG_ULT_TOP = 12, 125, 46   # '얼티메이트': Noto Sans KR Black 12 px, unsmoothed + 1 px outline


def _title0_rgba():
    """The patched F_TITLE0 logo (K art + Ultimate) as float RGBA 128x512, index 0 = transparent."""
    name = 'BIN/F_TITLE0.BIN'
    d = bytearray(_u(name))
    n = len(LOG)
    patch_title0(d, name)
    ok = LOG[n][2] == 'patched'
    del LOG[n:]
    assert ok, 'F_TITLE0 logo port failed'
    logo = np.hstack([np.frombuffer(bytes(d[o:o + 0x2000]), np.uint8).reshape(128, 64) for o in T0_LOGO])
    rgb = _pal_rgb(np.hstack([np.frombuffer(bytes(d[o + 112 * 64:o + 113 * 64]), '<u2') for o in T0_CLUT_BLKS]))
    im = np.zeros((128, 512, 4), np.float32)
    im[..., :3] = rgb[logo]
    im[..., 3] = (logo > 0) * 255.0
    return im


def _resize_pm(src, W, H):
    """Premultiplied-alpha Lanczos resize of float RGBA."""
    from PIL import Image
    pm = np.concatenate([src[..., :3] * (src[..., 3:] / 255.0), src[..., 3:]], -1)
    return np.clip(np.stack([np.asarray(Image.fromarray(pm[..., c].astype(np.float32), 'F').resize((W, H), Image.LANCZOS))
                             for c in range(4)], -1), 0, 255)


def _over(dst, src, x, y):
    h, w = src.shape[:2]
    sub = dst[y:y + h, x:x + w]
    assert sub.shape == src.shape, 'logo part outside the visible sprite'
    sub[:] = src + sub * (1 - src[..., 3:] / 255.0)


def _mono_text(text, px, weight):
    """1-bit FreeType rendering (hinted, no anti-aliasing), cropped to ink."""
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype(NOTO_SANS, px)
    f.set_variation_by_axes([weight])
    im = Image.new('1', (px * (len(text) + 2), px * 2), 0)
    dr = ImageDraw.Draw(im)
    dr.fontmode = '1'
    x = 0
    for ch in text:
        dr.text((x, 0), ch, font=f, fill=1)
        x += f.getbbox(ch)[2]
    a = np.asarray(im, np.uint8)
    ys, xs = np.nonzero(a.any(1))[0], np.nonzero(a.any(0))[0]
    return a[ys[0]:ys[-1] + 1, xs[0]:xs[-1] + 1]


def _ultimate_small():
    """'얼티메이트' as RGBA, Saturn style (gradient fill, 1 px dark outline), pixel-sharp."""
    m = _mono_text('얼티메이트', FG_ULT_PX, 900).astype(np.float32)
    H, W = m.shape
    c = np.zeros((H + 2, W + 2), np.float32)
    c[1:-1, 1:-1] = m
    o = dilate(c > 0)
    t = np.clip((np.arange(H + 2) - 1) / (H - 1), 0, 1)[:, None, None]
    fill = np.array(ULT_TOP_RGB, np.float32) * (1 - t) + np.array(ULT_BOT_RGB, np.float32) * t
    col = np.where(c[..., None] > 0, fill, np.array(ULT_OUT_RGB, np.float32))
    out = np.zeros((H + 2, W + 2, 4), np.float32)
    out[o, :3] = col[o]
    out[o, 3] = 255
    return out


def _to_clut(rgba, thr=96):
    """Composite on black, alpha < thr -> index 0 (transparent); others -> <=255 colours (median cut + k-means in
    15-bit RGB). Returns (idx uint8 HxW, pal uint16[256]) with pal[0] = 0 and no other entry 0x0000."""
    from PIL import Image
    op = rgba[..., 3] >= thr
    px = np.clip(rgba[..., :3][op], 0, 255)
    q5 = np.clip(np.round(px / 8.0), 0, 31)
    uniq, inv, cnt = np.unique(q5, axis=0, return_inverse=True, return_counts=True)
    inv = inv.reshape(-1)
    if len(uniq) <= 255:
        cent = uniq
    else:
        im = Image.fromarray((uniq * 8).astype(np.uint8)[None])
        qi = im.quantize(255, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        cent = np.array(qi.getpalette()[:255 * 3], np.float32).reshape(-1, 3) / 8.0
        for _ in range(12):                       # weighted k-means refinement
            lab = ((uniq[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
            for k in range(len(cent)):
                s = lab == k
                if s.any():
                    cent[k] = (uniq[s] * cnt[s, None]).sum(0) / cnt[s].sum()
        cent = np.clip(np.round(cent), 0, 31)
    lab = ((uniq[:, None] - cent[None]) ** 2).sum(-1).argmin(1)
    pal = np.zeros(256, np.uint16)
    c = cent.astype(np.uint16)
    v = c[:, 0] | (c[:, 1] << 5) | (c[:, 2] << 10)
    v[v == 0] = 0x0421                            # opaque black must not be the transparent 0x0000
    pal[1:1 + len(v)] = v
    idx = np.zeros(rgba.shape[:2], np.uint8)
    idx[op] = (lab[inv] + 1).astype(np.uint8)
    return idx, pal


_FG_LOGO_CACHE = []
def fgame_logo():
    """New 128x128 8bpp loading-screen logo + its 256-colour CLUT, rendered from the title logo."""
    if _FG_LOGO_CACHE:
        return _FG_LOGO_CACHE[0]
    src = _title0_rgba()
    yy, xx = np.mgrid[0:128, 0:512]
    al = src[..., 3] > 0
    sub = al & (yy >= 47) & (yy <= 69) & (xx >= 180) & (xx <= 339)   # '월하의 야상곡' (two components)
    main = src.copy()
    main[~(al & ~sub & (yy < 74))] = 0                               # title + X + swoosh, minus subtitle/Ultimate
    sy = 2 * FG_SX
    cv = np.zeros((FG_VIS_H, FG_VIS_W, 4), np.float32)
    _over(cv, _resize_pm(main[0:74, 20:493], 123, round(74 * sy)), 2, 0)
    s = src[47:70, 180:340].copy()
    s[~sub[47:70, 180:340]] = 0
    s = _resize_pm(s, round(160 * FG_SX * FG_SUB_K), round(23 * sy * FG_SUB_K))
    _over(cv, s, 2 + round(320 * FG_SX) - s.shape[1], round(47 * sy))  # right edge where the title has it
    if FG_SHARPEN:                                                     # light unsharp mask
        p = np.pad(cv, ((1, 1), (1, 1), (0, 0)), 'edge')
        k = np.array([1, 2, 1], np.float32) / 4
        bl = sum(k[i] * k[j] * p[i:i + FG_VIS_H, j:j + FG_VIS_W] for i in range(3) for j in range(3))
        cv = np.clip(cv + FG_SHARPEN * (cv - bl), 0, 255)
        cv[..., :3] = np.minimum(cv[..., :3], cv[..., 3:])             # stay premultiplied
    u = _ultimate_small()
    _over(cv, u, FG_ULT_RIGHT - u.shape[1], FG_ULT_TOP)
    idx, pal = _to_clut(cv)
    logo = np.zeros((128, 128), np.uint8)
    logo[:FG_VIS_H, :FG_VIS_W] = idx
    _FG_LOGO_CACHE.append((logo, pal))
    return logo, pal


def patch_logo(d, name):
    U = _u(name)
    a, b = FG_LOGO
    c0, c1 = FG_LOGO_CLUT
    ok = bytes(d[a:b]) == U[a:b] and bytes(d[c0:c1]) == U[c0:c1]
    if ok:
        logo, pal = fgame_logo()
        d[a:a + 0x2000] = logo[:, :64].tobytes()
        d[a + 0x2000:b] = logo[:, 64:].tobytes()
        d[c0:c1] = pal.astype('<u2').tobytes()
    _log(name, 'loading-screen logo 0x2C000-0x2FFFF + CLUT 0x41A00-0x41BFF: rendered from the title logo '
               '(+ Ultimate text, Korean)', ok)


def patch_fgame(d, name):
    patch_logo(d, name)
    patch_words(d, name)
    patch_loading(d, name)
    patch_hud_status(d, name)
    if name.endswith('F_GAME2.BIN'):
        patch_richter_hud(d, name)
        patch_maria_hud(d, name)


# ------------------------------------------------------------------ F_TITLE1
def _press_start_strip():
    """Korean 'PRESS START BUTTON' in the US style: 9 rows, colour 2/3/4 top->bottom, 1 shadow."""
    m = bold(galmuri('스타트 버튼을 누르세요', 9, spacing=1, space_w=5))
    H, W = m.shape
    im = np.zeros((H + 1, W + 1), np.uint8)
    sh = np.zeros_like(im, bool)
    sh[1:, 1:] = m.astype(bool)
    im[sh] = 1
    mm = np.zeros_like(im, bool)
    mm[:H, :W] = m.astype(bool)
    rows = np.array([2, 2, 2, 3, 3, 4, 4, 4, 4, 4])[:H + 1]
    im[mm] = np.repeat(rows[:, None], W + 1, 1)[mm]
    return im[:9]


def patch_title1(d, name):
    # PRESS START BUTTON: one 279-px line split into 128-px pieces at rows 52 / 68 / 84
    B = Blocks(d, name, [0x6000])
    o = B.img[0x6000]
    line = np.zeros((9, 384), np.uint8)
    s = _press_start_strip()
    x = 140 - s.shape[1] // 2
    line[:, x:x + s.shape[1]] = s
    o[52:61, :] = line[:, 0:128]
    o[68:77, :] = line[:, 128:256]
    o[84:93, 0:32] = line[:, 256:288]
    _log(name, "'PRESS START BUTTON' (0x6000)", B.commit())

    # prologue caption, 256x48 over blocks 0x20000|0x22000: two Korean lines, left-aligned at the US
    # leftmost ink column (x 4, line 2); the JP third line (rows 31-47) is left empty.
    B = Blocks(d, name, [0x20000, 0x22000])
    o = np.hstack([B.img[0x20000], B.img[0x22000]])
    o[31:48] = 0
    for (y0, y1), ko in (((1, 16), '1792년으로 거슬러 올라가'), ((16, 31), '루마니아의 트란실바니아 지방.')):
        o[y0:y1] = 0
        cov = fit_noto(ko, 236, y1 - y0 - 2, weight=500, serif=True, shear=0.15)
        v = np.clip(np.round(cov * 15), 0, 15).astype(np.uint8)
        x = CAPTION_X
        y = y0 + (y1 - y0 - v.shape[0]) // 2
        paste(o, v, x, y)
    B.img[0x20000], B.img[0x22000] = o[:, :128].copy(), o[:, 128:].copy()
    _log(name, "prologue caption 'JOURNEY BACK TO 1792 ...' (0x20000-0x23FFF)", B.commit())


CAPTION_X = 4          # leftmost ink column of the US caption (line 2)


# ------------------------------------------------------------------ F_PROLO0 ("CASTLEVANIA" after the crawl)
# ST0 draws it as 4 quads (type 4, tpage 0xB = VRAM (704,0), clut 0x220, 1:1, 512-px-wide screen):
#   screen x 32/160/288/416, y 104-136  <-  uv (0..128, 0..32) / (0..128, 32..64) / (0..128, 64..96) / (0..64, 96..128)
# i.e. one 448x32 strip folded into 32-row bands of the 128x128 block at F_PROLO0 0x18000 (copy 0x1A000).
# Indices: 0 = clear, 1 = full ink (beige), 2..7 = weaker AA levels. The other 7 blocks hold copies of
# rows 0-111 (their rows 112-127 are other data) and are rewritten the same way for consistency.
PROLO_MAIN = [0x18000, 0x1A000]
PROLO_COPIES = [0x4000, 0x6000, 0xC000, 0xE000, 0x14000, 0x16000, 0x1C000, 0x1E000]
PROLO_BANDS = [(0, 128), (32, 128), (64, 128), (96, 64)]       # (v0, width)


PROLO_PX, PROLO_WEIGHT, PROLO_SX, PROLO_GAP, PROLO_SPACE = 16, 700, 1.7, 8, 18


def prolo_strip():
    """448x32 coverage strip: '악마성 드라큘라' / '월하의 야상곡', Noto Serif KR, letter-spaced like the
    US 'C A S T L E V A N I A', drawn PROLO_SX wide (a texel of the 512-px screen is ~0.6 as wide as tall at 4:3;
    slightly wider than true aspect, like the wide US tracking). Each line has 16 rows (two lines in the 32-row strip).
    Glyphs share one baseline (drawn into the same line box); spacing is between ink boxes."""
    from PIL import Image, ImageDraw, ImageFont
    S = 4
    f = ImageFont.truetype(NOTO_SERIF, PROLO_PX * S)
    try:
        f.set_variation_by_axes([PROLO_WEIGHT])
    except Exception:
        pass
    W, H = 448, 32
    out = np.zeros((H, W), np.float32)
    for (y0, y1), text in (((0, 16), '악마성 드라큘라'), ((16, 32), '월하의 야상곡')):
        _, t, _, b = f.getbbox(text)
        glyphs = []
        for ch in text:
            if ch == ' ':
                glyphs.append(None); continue
            l, _, r, _ = f.getbbox(ch)
            im = Image.new('L', (r - l + 8, b - t + 8), 0)
            ImageDraw.Draw(im).text((4 - l, 4 - t), ch, font=f, fill=255)
            im = im.resize((max(1, round(im.width * PROLO_SX / S)), max(1, round(im.height / S))), Image.BOX)
            a = np.asarray(im, np.float32) / 255.0
            xs = np.nonzero(a.max(0) > 0.02)[0]
            glyphs.append(a[:, xs[0]:xs[-1] + 1])
        g0 = [g for g in glyphs if g is not None]
        ys = np.nonzero(np.max([g.max(1) for g in g0], 0) > 0.02)[0]
        top, bot = ys[0], ys[-1] + 1
        hh = bot - top
        assert hh <= y1 - y0, (text, hh)
        gap, space = PROLO_GAP, PROLO_SPACE
        tw = sum(space if g is None else g.shape[1] for g in glyphs) + gap * (len(glyphs) - 1)
        assert tw <= W, (text, tw)
        x = (W - tw) // 2
        y = y0 + (y1 - y0 - hh) // 2
        for g in glyphs:
            if g is None:
                x += space + gap; continue
            g = g[top:bot]
            sub = out[y:y + g.shape[0], x:x + g.shape[1]]
            np.maximum(sub, g, out=sub)
            x += g.shape[1] + gap
    return out


def prolo_indices():
    c = prolo_strip()
    idx = np.zeros(c.shape, np.uint8)
    m = c >= 0.12
    idx[m] = np.clip(np.round(1 + (1 - c[m]) * 6 / 0.88), 1, 7).astype(np.uint8)
    idx[c >= 0.94] = 1
    return idx


def patch_prolo0(d, name):
    strip = prolo_indices()
    B = Blocks(d, name, PROLO_MAIN + PROLO_COPIES)
    ref = blk_get(_u(name), PROLO_MAIN[0])
    for o in PROLO_MAIN + PROLO_COPIES:          # all copies share the US letters in rows 0-111
        assert (B.img[o][:112] == ref[:112]).all() or not B.ok, hex(o)
    x = 0
    for v0, w in PROLO_BANDS:
        for o in PROLO_MAIN + PROLO_COPIES:
            rows = 32 if o in PROLO_MAIN else min(32, 112 - v0)
            B.img[o][v0:v0 + rows, :w] = strip[:rows, x:x + w]
            if w < 128 and o in PROLO_MAIN:
                assert v0 + rows == 128
        x += w
    _log(name, "'CASTLEVANIA' strip after the opening crawl (0x18000/0x1A000 + copies)", B.commit())


# ------------------------------------------------------------------ F_TITLE0 (title screen logo)
T0_LOGO = [0x20000, 0x22000, 0x28000, 0x2A000, 0x30000, 0x32000, 0x38000, 0x3A000]   # 512x128 8bpp
T0_CLUT_BLKS = [0x4000, 0x6000, 0xC000, 0xE000, 0x14000, 0x16000, 0x1C000, 0x1E000]  # rows 112-114 = CLUT


def patch_title0(d, name):
    U, K = _u(name), _k(name)
    spans = [(o, o + 0x2000) for o in T0_LOGO] + [(o + 112 * 64, o + 115 * 64) for o in T0_CLUT_BLKS]
    ok = all(bytes(d[a:b]) == U[a:b] for a, b in spans)
    # outside the CLUT rows the bottom blocks must be identical in U and K (pure background)
    ok = ok and all(U[o:o + 112 * 64] == K[o:o + 112 * 64] and U[o + 115 * 64:o + 0x2000] == K[o + 115 * 64:o + 0x2000]
                    for o in T0_CLUT_BLKS)
    if ok:
        for a, b in spans:
            d[a:b] = K[a:b]
        logo = np.hstack([np.frombuffer(bytes(d[o:o + 0x2000]), np.uint8).reshape(128, 64) for o in T0_LOGO]).copy()
        pal = np.hstack([np.frombuffer(bytes(d[o + 112 * 64:o + 113 * 64]), '<u2') for o in T0_CLUT_BLKS])
        _ultimate_onto(logo, pal, noto('얼티메이트', T0_ULT_PX, weight=900), T0_ULT_RIGHT, T0_ULT_TOP, 2)
        for i, o in enumerate(T0_LOGO):
            d[o:o + 0x2000] = logo[:, i * 64:(i + 1) * 64].tobytes()
    _log(name, 'title-screen logo (8 blocks) + its CLUT rows from K, + Ultimate text (Korean)', ok)


# ------------------------------------------------------------------ SEL headers (F_SEL, SEL.BIN)
LETTER_COLS = (1, 3, 4, 5)


ORN_COLS = (9, 10, 11, 12)      # gold ornament (key, '&', flourish); letters use 1 (outline) + 2..5


def _header_word(text, size, bottom_outline=True):
    """Lower-case-line word in the header style: vertical ramp 3,4,5..5,4,3 inside a 1-px outline (colour 1),
    the way the US 'ile', 'copy', 'ound' ... are drawn. Returns (img, ink mask, outline mask).
    bottom_outline=False drops the outline row under the glyphs (used where the ornament leaves only 12 rows)."""
    m = bold(galmuri(text, size, spacing=1, space_w=4)).astype(bool)
    H, W = m.shape
    mm = np.zeros((H + 2, W + 2), bool)
    mm[1:-1, 1:-1] = m
    ol = dilate(mm) & ~mm
    g = np.zeros(mm.shape, np.uint8)
    g[ol] = 1
    ramp = [3, 4] + [5] * max(0, H - 4) + [4, 3]
    rows = np.array(ramp[:H] if H >= 4 else [5] * H, np.uint8)
    full = np.zeros(mm.shape, np.uint8)
    full[1:-1, 1:-1] = np.repeat(rows[:, None], W, 1)
    g[mm] = full[mm]
    if not bottom_outline:
        g, mm, ol = g[:-1], mm[:-1], ol[:-1]
    return g, mm, ol


def _components(mask):
    """4-connected components of a bool mask -> list of index arrays."""
    seen = np.zeros(mask.shape, bool)
    out = []
    H, W = mask.shape
    for y, x in zip(*np.nonzero(mask)):
        if seen[y, x]:
            continue
        st, comp = [(y, x)], []
        seen[y, x] = True
        while st:
            cy, cx = st.pop()
            comp.append((cy, cx))
            for ny, nx in ((cy + 1, cx), (cy - 1, cx), (cy, cx + 1), (cy, cx - 1)):
                if 0 <= ny < H and 0 <= nx < W and mask[ny, nx] and not seen[ny, nx]:
                    seen[ny, nx] = True
                    st.append((ny, nx))
        out.append(tuple(np.array(comp).T))
    return out


def _header_text(o, y0, parts, width, x_start=33, clear_below=None, gap=5):
    """Remove the Latin lower-case word(s) of a gothic header (rows y0..y0+31, x >= 32) but keep every
    ornament pixel (key, fleurons, '&', flourish), then put the Korean parts on the same text line,
    each one in the first gap of the line that is free of ornament, left to right - i.e. where the
    English lower-case letters were (part 0 under the key, the next part after the '&' / fleuron).
    The text's dark outline may touch the ornament's dark outline (as the English letters do), the
    letters themselves never touch the ornament."""
    reg = o[y0:y0 + 32, 32:width]
    orn = np.isin(reg, ORN_COLS)
    letters = np.isin(reg, (2, 3, 4, 5))
    near_l = dilate(dilate(letters))
    near_o = dilate(orn)
    reg[letters | ((reg == 1) & near_l & ~near_o)] = 0
    if clear_below is not None:                 # ornament fragments cut by the old letters
        reg[clear_below:] = 0
    for c in _components(reg != 0):             # stray outline pixels left over from the letters
        if len(c[0]) < 8 and not np.isin(reg[c], ORN_COLS).any():
            reg[c] = 0
    used = reg != 0
    gold = used & (reg != 1)
    placed, ok = [], False
    # one size and one text row for the whole header (so all headers look alike: Galmuri11 if it fits)
    for size, bo, tops in ((11, True, (19,)), (11, False, (19, 20)), (9, True, (20, 21))):
        for t in tops:
            ok, x, placed = True, x_start - 32, []
            for p in parts:
                g, ink, ol = _header_word(p, size, bo)
                h, w = g.shape
                if t + h > 32:
                    ok = False
                    break
                for xx in range(x, reg.shape[1] - w + 1):
                    if not ((used[t:t + h, xx:xx + w] & ink).any() or (gold[t:t + h, xx:xx + w] & ol).any()):
                        placed.append((g, ink, xx, t)); x = xx + w + gap
                        break
                else:
                    ok = False
                    break
            if ok:
                break
        if ok:
            break
    assert ok, ('header text does not fit', parts)
    for g, ink, xx, t in placed:
        sub = reg[t:t + g.shape[0], xx:xx + g.shape[1]]
        wr = ink | ((g == 1) & (sub == 0))
        sub[wr] = g[wr]
    return placed


def _header(o, y0, first, rest, width=128, **kw):
    """Gothic header (width x 32) at row y0: illuminated box x0-31 + ornaments + lower-case text line.
    `rest` is the rest of the word, '|' separates the parts that go into separate gaps of the line."""
    # drop cap: wipe the Latin capital (fill 3/4/5 and its dark 1 outline), keep the box texture
    box = o[y0 + 3:y0 + 29, 3:29]
    letter = np.isin(box, (3, 4, 5))
    edge = dilate(letter) & (box == 1)
    box[letter | edge] = 6
    cov = fit_noto(first, 22, 22, weight=900, serif=True)
    m = cov >= 0.45
    g = _outlined(m, 4, 5, m.shape[0] // 2, 1)
    paste(o, g, 3 + (26 - g.shape[1]) // 2, y0 + 3 + (26 - g.shape[0]) // 2)
    # lower-case part of the Latin capital that pokes out of the box (x 29-31 rows 20-30): leave the box frame
    return _header_text(o, y0, rest.split('|'), width, **kw)


SEL_HEADERS = [  # (block, y0, first syllable, rest)
    (0x4000, 0, '파', '일|복사'), (0x4000, 32, '파', '일|삭제'), (0x4000, 64, '이', '름|입력'),
    (0x4000, 96, '이', '름|변경'), (0x6000, 16, '파', '일|선택'),
]


def patch_fsel(d, name):
    for base in (0x0000, 0x20000):          # two identical copies of the sheet
        B = Blocks(d, name, [base + 0x4000, base + 0x6000])
        for blk, y0, f, r in SEL_HEADERS:
            _header(B.img[base + blk], y0, f, r)
        o = B.img[base + 0x6000]
        # 'Name :' 'Place :'
        o[111:126, 0:80] = 0
        for x, ko in ((2, '이름 :'), (42, '장소 :')):
            m = bold(galmuri(ko, 9, spacing=1, space_w=3))
            g = _outlined(m, 5, 4, 5, 1)
            paste(o, g, x, 113)
        # 'TIME:' (keep the small 'lv' and the digits)
        o[0:8, 104:128] = 0
        m = galmuri('시간', 7)
        g = np.zeros((8, m.shape[1] + 1), np.uint8)
        sh = np.zeros_like(g, bool)
        sh[1:, 1:] = m.astype(bool)
        g[sh] = 1
        g[:7, :m.shape[1]][m.astype(bool)] = 4
        paste(o, g, 106, 0)
        _log(name, 'file menu headers + Name/Place/TIME (blocks 0x%X-0x%X)' % (base + 0x4000, base + 0x7FFF), B.commit())


SOUND_HDR = 0x275BC    # SEL.BIN: raw 32hw x 32 'Sound mode' header (VRAM 960,96), Ultimate addition


def patch_sel_bin(d, name):
    U = _u(name)
    a, b = SOUND_HDR, SOUND_HDR + 32 * 64
    ok = len(d) >= b and bytes(d[a:b]) == U[a:b]
    if ok:
        arr = np.frombuffer(bytes(d[a:b]), np.uint8).reshape(32, 64)
        o = np.zeros((32, 128), np.uint8)
        o[:, 0::2] = arr & 15
        o[:, 1::2] = arr >> 4
        _header(o, 0, '사', '운드|모드', clear_below=21)
        d[a:b] = ((o[:, 0::2] & 15) | ((o[:, 1::2] & 15) << 4)).astype(np.uint8).tobytes()
    _log(name, "'Sound mode' header (0x275BC)", ok)


# ------------------------------------------------------------------ DRA compressed picture
DRA_BASE = 0x800A0000
LVUP_VA = 0x800C217C          # compressed 128x128; next stream starts at 0x800C27B0
LVUP_MAX = 0x800C27B0 - LVUP_VA
LVUP_LINES = [((3, 22), '최대 HP 증가'), ((27, 46), '최대 하트 증가'), ((51, 70), '레벨 업'), ((76, 95), '아이템 획득')]
LVUP_EN = ['Life max up', 'Heart max up', 'Level up', 'Got an item']


def decompress(src, o=0):
    d = src
    dic = d[o:o + 8]
    p = [o + 8, 0]
    out = []
    def rn():
        b = d[p[0]]
        if p[1]:
            p[1] = 0; p[0] += 1
            return b & 15
        p[1] = 1
        return b >> 4
    while True:
        op = rn()
        if op == 0:
            n = (rn() << 4); n += rn(); out += [0] * (n + 19)
        elif op == 1: out.append(rn())
        elif op == 2: c = rn(); out += [c, c]
        elif op == 3: out += [rn(), rn()]
        elif op == 4: out += [rn(), rn(), rn()]
        elif op == 5: c = rn(); out += [c] * (rn() + 3)
        elif op == 6: out += [0] * (rn() + 3)
        elif op == 15: break
        else:
            ch = dic[op - 7]
            t, c = ch & 0xF0, ch & 15
            if t == 0x10: out.append(c)
            elif t == 0x20: out += [c, c]
            elif t == 0x60: out += [0] * (c + 3)
    return out, p[0] + p[1] - o


def _dp(n, dic):
    """min-nibble encoding of nibble list n with dictionary dic (list of bytes)."""
    N = len(n)
    single = {e & 15: k for k, e in enumerate(dic) if e & 0xF0 == 0x10}
    double = {e & 15: k for k, e in enumerate(dic) if e & 0xF0 == 0x20}
    zrun = {(e & 15) + 3: k for k, e in enumerate(dic) if e & 0xF0 == 0x60}
    INF = 1 << 30
    cost = [INF] * (N + 1)
    choice = [None] * (N + 1)
    cost[N] = 0
    # run lengths
    run = [0] * (N + 1)
    for i in range(N - 1, -1, -1):
        run[i] = run[i + 1] + 1 if i + 1 < N and n[i + 1] == n[i] else 1
    for i in range(N - 1, -1, -1):
        c = n[i]
        best, bc = INF, None
        def t(k, nib, ch):
            nonlocal best, bc
            if i + k <= N and nib + cost[i + k] < best:
                best, bc = nib + cost[i + k], ch
        t(1, 1 if c in single else 2, ('s',) if c in single else ('1',))
        t(2, 3, ('3',))
        t(3, 4, ('4',))
        r = run[i]
        if r >= 2:
            t(2, 1 if c in double else 2, ('d',) if c in double else ('2',))
        if c == 0:
            for L, k in zrun.items():
                if L <= r:
                    t(L, 1, ('z', k))
            for L in range(3, min(18, r) + 1):
                t(L, 2, ('6', L))
            for L in range(19, min(274, r) + 1):
                t(L, 3, ('0', L))
        if r >= 3:
            for L in range(3, min(18, r) + 1):
                t(L, 3, ('5', L))
        cost[i], choice[i] = best, bc
    return cost, choice


def compress(img):
    """img: 128x128 nibbles -> bytes in DecompressData format."""
    n = [int(v) for v in img.ravel()]
    # pick dictionary: most frequent short zero runs and single literals from a dict-less pass
    from collections import Counter
    cost, ch = _dp(n, [])
    cz, cs, cd = Counter(), Counter(), Counter()
    i = 0
    while i < len(n):
        c = ch[i]
        if c[0] == '6': cz[c[1]] += 1; i += c[1]
        elif c[0] == '0': i += c[1]
        elif c[0] == '5': i += c[1]
        elif c[0] == '1': cs[n[i]] += 1; i += 1
        elif c[0] == '2': cd[n[i]] += 1; i += 2
        elif c[0] == '3': i += 2
        else: i += 3
    cands = [(v * 1, 0x60 | (L - 3)) for L, v in cz.items()] + [(v, 0x10 | k) for k, v in cs.items()] + \
            [(v, 0x20 | k) for k, v in cd.items()]
    cands.sort(reverse=True)
    dic = [e for _, e in cands[:8]]
    while len(dic) < 8:
        dic.append(0)
    cost, ch = _dp(n, dic)
    nib = []
    i = 0
    while i < len(n):
        c = ch[i]
        k = c[0]
        if k == 's': nib += [7 + [e for e in dic].index(0x10 | n[i])]; i += 1
        elif k == 'd': nib += [7 + dic.index(0x20 | n[i])]; i += 2
        elif k == 'z': nib += [7 + c[1]]; i += (dic[c[1]] & 15) + 3
        elif k == '1': nib += [1, n[i]]; i += 1
        elif k == '2': nib += [2, n[i]]; i += 2
        elif k == '3': nib += [3, n[i], n[i + 1]]; i += 2
        elif k == '4': nib += [4, n[i], n[i + 1], n[i + 2]]; i += 3
        elif k == '5': nib += [5, n[i], c[1] - 3]; i += c[1]
        elif k == '6': nib += [6, c[1] - 3]; i += c[1]
        elif k == '0': L = c[1] - 19; nib += [0, L >> 4, L & 15]; i += c[1]
    nib.append(15)
    if len(nib) & 1:
        nib.append(0)
    body = bytes((nib[j] << 4) | nib[j + 1] for j in range(0, len(nib), 2))
    return bytes(dic) + body


LVUP_CONFIGS = [(15, 600, 0), (14, 600, 0), (14, 500, 6), (14, 500, 5), (14, 500, 4), (13, 500, 4),
                (13, 500, 3), (12, 500, 3)]       # (max glyph height, weight, AA levels) best first


def lvup_image(maxh=14, weight=500, levels=4):
    """Each Korean line is kept inside the ink box of the English line it replaces."""
    o = np.zeros((128, 128), np.uint8)
    for (y0, y1), ko in LVUP_LINES:
        ex0, ex1, ey0, ey1 = _lvup_box(y0, y1)
        cov = fit_noto(ko, ex1 - ex0 - 1, min(maxh, ey1 - ey0 - 1), weight=weight, serif=True, shear=0.18)
        if levels:
            cov = np.round(cov * (levels - 1)) / (levels - 1)
        g = aa_outline_indices(cov)
        x = ex0 + (ex1 - ex0 + 1 - g.shape[1]) // 2
        y = ey0 + (ey1 - ey0 + 1 - g.shape[0]) // 2
        paste(o, g, x, y)
    return o


_LVC = {}
def _lvup_box(y0, y1):
    if not _LVC:
        _LVC['u'] = np.array(decompress(_u('DRA.BIN'), LVUP_VA - DRA_BASE)[0][:16384], np.uint8).reshape(128, 128)
    sub = _LVC['u'][y0 - 3:y1 + 2]
    xs = np.nonzero(sub.any(0))[0]
    ys = np.nonzero(sub.any(1))[0] + y0 - 3
    return xs[0], xs[-1], ys[0], ys[-1]


def patch_dra(d, name):
    U = _u(name)
    a = LVUP_VA - DRA_BASE
    orig_len = decompress(U, a)[1]
    ok = bytes(d[a:a + orig_len]) == U[a:a + orig_len]
    if ok:
        c = None
        for cfg in LVUP_CONFIGS:
            img = lvup_image(*cfg)
            c = compress(img)
            out, ln = decompress(c)
            assert np.array_equal(np.array(out[:16384], np.uint8).reshape(128, 128), img) and len(out) == 16384
            if len(c) <= LVUP_MAX:
                break
        ok = len(c) <= LVUP_MAX
        if ok:
            d[a:a + len(c)] = c
            if len(c) < orig_len:
                d[a + len(c):a + orig_len] = bytes(orig_len - len(c))
    _log(name, "'Life max up / Heart max up / Level up / Got an item' (va 0x%08X, compressed)" % LVUP_VA, ok)


# ------------------------------------------------------------------ entry point
def _base(path):
    p = path.replace('\\', '/').split(';')[0].lstrip('/')
    return p.upper()


def patch_file(path: str, data: bytes) -> bytes:
    name = _base(path)
    if name in ('BIN/F_GAME.BIN', 'BIN/F_GAME2.BIN'):
        fn = patch_fgame
    elif name == 'BIN/F_TITLE0.BIN':
        fn = patch_title0
    elif name == 'BIN/F_TITLE1.BIN':
        fn = patch_title1
    elif name == 'ST/SEL/F_SEL.BIN':
        fn = patch_fsel
    elif name == 'ST/SEL/SEL.BIN':
        fn = patch_sel_bin
    elif name == 'DRA.BIN':
        fn = patch_dra
    elif name == 'BIN/F_PROLO0.BIN':
        fn = patch_prolo0
    else:
        return data
    d = bytearray(data)
    fn(d, name)
    if name in ('BIN/F_TITLE1.BIN', 'ST/SEL/F_SEL.BIN', 'ST/SEL/SEL.BIN'):
        import selui                    # SEL-screen fonts / strings / tiles (see selui.py)
        d = bytearray(selui.patch(name, bytes(d)))
    return bytes(d)


# ------------------------------------------------------------------ previews
def _gray(img, z=3):
    from PIL import Image
    return Image.fromarray((img.astype(np.uint8) * 17)).resize((img.shape[1] * z, img.shape[0] * z), 0)


def _pair(before, after, out, z=3):
    from PIL import Image
    a, b = _gray(before, z), _gray(after, z)
    im = Image.new('L', (a.width + b.width + 12, max(a.height, b.height)), 100)
    im.paste(a, (0, 0))
    im.paste(b, (a.width + 12, 0))
    im.save(out)


def _logo_v2_preview(U, P):
    """f_game_logo_v2.png: the 127x63 area the game shows, x3 nearest, on black.
    Top: US | previous (K's small logo + Galmuri7 Ultimate) | new. Bottom: same three at display aspect
    (loading screen 256 px wide: texels 2.5 wide x 2 tall at 640x480)."""
    from PIL import Image
    name = 'BIN/F_GAME.BIN'
    K = _k(name)
    def rgbimg(D, logo=None):
        pal = np.frombuffer(D[0x41A00:0x41C00], '<u2')
        if logo is None:
            logo = np.hstack([np.frombuffer(D[o:o + 0x2000], np.uint8).reshape(128, 64) for o in (0x2C000, 0x2E000)])
        return _pal_rgb(pal).astype(np.uint8)[logo[:FG_VIS_H, :FG_VIS_W]]
    kl = np.hstack([np.frombuffer(K[o:o + 0x2000], np.uint8).reshape(128, 64) for o in (0x2C000, 0x2E000)]).copy()
    _ultimate_onto(kl, np.frombuffer(K[0x41A00:0x41C00], '<u2'), galmuri('얼티메이트', 7).astype(np.float32), 114, 45, 1)
    ims = [rgbimg(U), rgbimg(K, kl), rgbimg(P)]
    W3, H3 = FG_VIS_W * 3, FG_VIS_H * 3
    Wa, Ha = FG_VIS_W * 5 // 2, FG_VIS_H * 2
    out = Image.new('RGB', (3 * W3 + 24, H3 + Ha + 12), (90, 90, 90))
    for i, a in enumerate(ims):
        out.paste(Image.fromarray(a).resize((W3, H3), 0), (i * (W3 + 12), 0))
        out.paste(Image.fromarray(a).resize((Wa, Ha), 0), (i * (W3 + 12), H3 + 12))
    out.save(os.path.join(PREVIEW, 'f_game_logo_v2.png'))


def previews():
    from PIL import Image
    os.makedirs(PREVIEW, exist_ok=True)
    for name in ('BIN/F_GAME.BIN', 'BIN/F_GAME2.BIN'):
        U = _u(name)
        P = patch_file(name, U)
        tag = name.split('/')[-1].split('.')[0].lower()
        for off, y0, y1, lab in ((0x10000, 60, 128, 'words'), (0x16000, 100, 128, 'loading'),
                                 (0x38000, 44, 128, 'hud_status')):
            _pair(blk_get(U, off)[y0:y1], blk_get(P, off)[y0:y1], os.path.join(PREVIEW, '%s_%s.png' % (tag, lab)), 4)
        if tag == 'f_game2':
            _pair(blk_get(U, 0x18000)[40:86, 60:128], blk_get(P, 0x18000)[40:86, 60:128],
                  os.path.join(PREVIEW, 'f_game2_richter_hud.png'), 5)
            _pair(blk_get(U, 0x6000)[8:32, 40:120], blk_get(P, 0x6000)[8:32, 40:120],
                  os.path.join(PREVIEW, 'f_game2_maria_hud.png'), 5)
        # logo in real colours
        ims = []
        for D in (U, P):
            pal = np.frombuffer(D[0x41A00:0x41C00], '<u2').astype(np.uint32)
            rgb = np.stack([(pal & 31) << 3, ((pal >> 5) & 31) << 3, ((pal >> 10) & 31) << 3], -1).astype(np.uint8)
            idx = np.hstack([np.frombuffer(D[o:o + 0x2000], np.uint8).reshape(128, 64) for o in (0x2C000, 0x2E000)])
            ims.append(Image.fromarray(rgb[idx]).resize((384, 384), 0))
        im = Image.new('RGB', (780, 384), (90, 90, 90))
        im.paste(ims[0], (0, 0)); im.paste(ims[1], (396, 0))
        im.save(os.path.join(PREVIEW, '%s_logo.png' % tag))
        if tag == 'f_game':
            _logo_v2_preview(U, P)
    name = 'BIN/F_TITLE0.BIN'
    U = _u(name); P = patch_file(name, U)
    ims = []
    for D in (U, P):                    # real colours (CLUT row 112) on a dark stone-grey background
        logo = np.hstack([np.frombuffer(D[o:o + 0x2000], np.uint8).reshape(128, 64) for o in T0_LOGO])
        rgb = _pal_rgb(np.hstack([np.frombuffer(D[o + 112 * 64:o + 113 * 64], '<u2') for o in T0_CLUT_BLKS]))
        im = np.full((128, 512, 3), (40, 44, 48), np.uint8)
        im[logo > 0] = rgb.astype(np.uint8)[logo][logo > 0]
        ims.append(Image.fromarray(im).resize((1024, 256), 0))
    im = Image.new('RGB', (1024, 524), (90, 90, 90))
    im.paste(ims[0], (0, 0)); im.paste(ims[1], (0, 268))
    im.save(os.path.join(PREVIEW, 'f_title0_logo.png'))
    name = 'BIN/F_TITLE1.BIN'
    U = _u(name); P = patch_file(name, U)
    _pair(blk_get(U, 0x6000)[48:96], blk_get(P, 0x6000)[48:96], os.path.join(PREVIEW, 'f_title1_press_start.png'), 4)
    def line(D):
        a = blk_get(D, 0x6000)
        return np.hstack([a[50:62], a[66:78], a[82:94, :32]])
    _pair(line(U), line(P), os.path.join(PREVIEW, 'f_title1_press_start_joined.png'), 3)
    cu = np.hstack([blk_get(U, 0x20000), blk_get(U, 0x22000)])[:48]
    cp = np.hstack([blk_get(P, 0x20000), blk_get(P, 0x22000)])[:48]
    _pair(cu, cp, os.path.join(PREVIEW, 'f_title1_prologue_caption.png'), 3)
    name = 'BIN/F_PROLO0.BIN'                    # 'CASTLEVANIA' strip, as the game lays it out (448x32)
    U = _u(name); P = patch_file(name, U)
    def strip(D):
        b = blk_get(D, PROLO_MAIN[0])
        return np.vstack([np.hstack([b[v0:v0 + 32, :w] for v0, w in PROLO_BANDS])])
    _pair(strip(U), strip(P), os.path.join(PREVIEW, 'f_prolo0_castlevania.png'), 2)
    name = 'ST/SEL/F_SEL.BIN'
    U = _u(name); P = patch_file(name, U)
    _pair(np.hstack([blk_get(U, 0x4000), blk_get(U, 0x6000)]), np.hstack([blk_get(P, 0x4000), blk_get(P, 0x6000)]),
          os.path.join(PREVIEW, 'f_sel_headers.png'), 3)
    def plates(D):
        return np.hstack([blk_get(D, 0x2000)[0:18, 70:106], blk_get(D, 0x2A000)[0:18, 38:74], blk_get(D, 0)[80:98, 62:98]])
    _pair(plates(U), plates(P), os.path.join(PREVIEW, 'f_sel_plates.png'), 6)
    name = 'ST/SEL/SEL.BIN'
    U = _u(name); P = patch_file(name, U)
    def hdr(D):
        a = np.frombuffer(D[SOUND_HDR:SOUND_HDR + 2048], np.uint8).reshape(32, 64)
        o = np.zeros((32, 128), np.uint8); o[:, 0::2] = a & 15; o[:, 1::2] = a >> 4
        return o
    _pair(hdr(U), hdr(P), os.path.join(PREVIEW, 'sel_sound_mode.png'), 4)
    name = 'DRA.BIN'
    U = _u(name); P = patch_file(name, U)
    a = LVUP_VA - DRA_BASE
    bu = np.array(decompress(U, a)[0][:16384], np.uint8).reshape(128, 128)
    bp = np.array(decompress(P, a)[0][:16384], np.uint8).reshape(128, 128)
    _pair(bu[:100], bp[:100], os.path.join(PREVIEW, 'dra_levelup.png'), 3)
    c = compress(bp)
    print('DRA level-up stream: %d bytes (limit %d, original %d)' % (len(c), LVUP_MAX, decompress(U, a)[1]))
    import selui
    selui.previews()


if __name__ == '__main__':
    LOG.clear()
    previews()
    for l in LOG:
        print(*l)
