"""Korean for the remaining English on the title-menu (SEL) screens.

    data = selui.patch(path, data)      # path: 'ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN', 'BIN/F_TITLE1.BIN', 'ST/SEL/F_SEL.BIN'

gfx.patch_file() calls this for SEL.BIN, F_TITLE1.BIN and F_SEL.BIN (after its own edits), so the build needs
no change for those. BIN/SELRIC2.BIN (same code/data layout as SEL.BIN) is not passed through gfx by the
build; call selui.patch('BIN/SELRIC2.BIN', data) there too if SELRIC2 should match.
Every edit checks that the bytes are still the US originals (assert); running twice is a no-op.

What is changed (see work/gfx_report.md, "SEL screens"):
 1. Small 8x8 font (SEL 0x801BB9F8 draws one byte = one cell of the 8x8 sheet at VRAM (896,256), byte FF ends;
    during the title/SEL screens that sheet comes from F_TITLE1.BIN 0x30000, a copy of the US F_GAME sheet).
    Hangul syllables are drawn (Galmuri7) into the kana cells 0x60-0xDF of the F_TITLE1 copy (SEL never uses
    kana), and the SEL strings are rewritten with those cell codes: button legends, "Select a player",
    option labels / values of Ultimate's player-select screen, and the memory-card prompts.
 2. Ultimate's player-select header "Player select" and the RICHTER / ALUCARD / MARIA name plates are built at
    run time from 8x8 tiles (SEL 0x801B3A48: tile bank 0x801AD518, 232 tiles; lists 0x801AF218 (18x4) and
    0x801AF308/32C/350 (11x3)). New images are drawn and re-tiled into the tile slots those four lists use
    exclusively (the portrait frame list 0x801AF260 is not touched).
 3. Gothic 16x16 strings ("select your destiny", "new game", "used", "no data", "no" / "card"): the US drawer
    0x801BB8BC looks letters up in a 32-entry a-z table (texture page 0xC = F_SEL's second sheet copy); the name
    entry keeps using it. The unused 12x16 drawer at 0x801BB7D0 (no callers) is replaced by a drawer that takes
    a byte as a 16x16 cell of texture page 0xD (VRAM 832,0 = F_SEL 0x28000-0x2FFFF): u = (b & 15) * 16,
    v = b & 0xF0, 0 ends. Korean glyphs (Noto Serif KR Black, gothic palette 2-5) go into empty cells there,
    and the six call sites are pointed at the new drawer (x positions re-centred).
 4. Save-location (area) names in the file-select boxes (0x801B2F90: table 0x80180128, 80 areas x 2 lines,
    small 8x8 font): the string pool 0x801A7438-0x801A75BC is rebuilt with Korean (Saturn title_ko.AREA, US
    two-line split) and the table re-pointed. Their syllables share the small-font cells (0x60-0xBD in use).
"""
import os, sys, struct
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gfx
from asm import Asm, jal_word

LOG = []

# ------------------------------------------------------------------ helpers
def _base(path):
    return path.replace('\\', '/').split(';')[0].lstrip('/').upper()


def _put(d, off, orig, new, what):
    assert bytes(d[off:off + len(orig)]) == orig, (what, hex(off), bytes(d[off:off + len(orig)]).hex(), orig.hex())
    d[off:off + len(new)] = new


# ------------------------------------------------------------------ 1. small 8x8 font
import addrmap as _am
def _o(off):
    """v1.2 SEL file offset -> current base (SEL and SELRIC2 share the layout)."""
    n = _am.get('ST/SEL/SEL.BIN')(off)
    assert n is not None, hex(off)
    return n
def _v(va):
    return 0x80180000 + _o(va - 0x80180000)

SMALL_SHEET = 0x30000                   # F_TITLE1 block holding the 8x8 sheet (VRAM 896,256)
SMALL_FIRST = 0x60                      # first kana cell we take over
SMALL_LAST = 0xDF

# (file offset in SEL.BIN, US text (as drawn), Korean). PS1 / PSP / JP are kept.
SMALL_STRINGS = [
    (0x27E34, 'Select', '선택'),
    (0x27E2C, 'Decide', '결정'),
    (0x27E24, 'Cancel', '취소'),
    (0x27E1C, 'Input', '입력'),
    (0x27E10, 'Not for-', '포맷되지'),      # "Not for-" / "matted"
    (0x27DE8, 'matted', '않음'),
    (0x27E08, 'Yes', '예'),
    (0x27E04, 'No', '아니오'),
    (0x27DF8, 'Confirm', '확인'),
    (0x27DF0, 'Error', '오류'),
    (0x2F4A4, 'Select a player', '플레이어 선택'),
    (0x2F494, 'Boss Richter', '보스 리히터'),
    (0x2F478, 'Boss Maria', '보스 마리아'),
    (0x2F484, 'Saturn', '새턴'),
    (0x2F4B8, 'Balance', '밸런스'),
    (0x2F4C8, 'Dub', '음성'),
    (0x2F464, 'Costume', '의상'),
    (0x2F458, 'Version', '버전'),
]


# Save-location (area) names in the file-select boxes: SEL 0x801B2F90 draws two lines with 0x801BB9F8 from the
# pointer table 0x80180128 (80 areas x 2 pointers, both lines at x 160). Strings live in the pool
# 0x801A7438-0x801A75BC (only this table points there). Korean = Saturn title_ko.AREA (work/saturn_handoff/
# translations_ko.json), kept on the US two-line split; 'Abandoned Mine' is not in the Saturn list.
AREA_TABLE = 0x128
AREA_COUNT = 80
AREA_POOL = (0x27438, 0x275BD)
AREA_KO = {
    ('Marble', 'Gallery'): ('대리석', '회랑'),
    ('Outer', 'Wall'): ('외벽', ''),
    ('Long', 'Library'): ('장서관', ''),
    ('Catacombs', ''): ('지하 묘지', ''),
    ("Olrox's", 'Quarters'): ('올록스의', '거처'),
    ('Abandoned', 'Mine'): ('버려진', '광산'),
    ('Royal', 'Chapel'): ('왕실', '예배당'),
    ('Entrance', ''): ('입구', ''),
    ('Underground', 'Caverns'): ('지하', '동굴'),
    ('Colosseum', ''): ('콜로세움', ''),
    ('Castle', 'Keep'): ('성', '본관'),
    ('Alchemy', 'Laboratory'): ('연금술', '연구소'),
    ('Cursed', 'Prison'): ('저주받은', '감옥'),
    ('Underground', 'Garden'): ('지하', '정원'),
    ('Black Marble', 'Gallery'): ('검은 대리석', '회랑'),
    ('Reverse', 'Outer Wall'): ('역', '외벽'),
    ('Forbidden', 'Library'): ('금단의', '도서관'),
    ('Floating', 'Catacombs'): ('부유', '지하 묘지'),
    ("Death Wing's", 'Lair'): ('데스윙의', '둥지'),
    ('Cave', ''): ('동굴', ''),
    ('Anti-Chapel', ''): ('역 예배당', ''),
    ('Reverse', 'Entrance'): ('역', '입구'),
    ('Reverse', 'Caverns'): ('역', '동굴'),
    ('Reverse', 'Colosseum'): ('역', '콜로세움'),
    ('Reverse', 'Keep'): ('역', '본관'),
    ('Necromancy', 'Laboratory'): ('강령술', '연구소'),
    ('Soul', 'Prison'): ('영혼의', '감옥'),
    ('Hell', 'Garden'): ('지옥', '정원'),
}


# Sound mode (Ultimate, file-menu 'Sound mode'): 44 track names drawn by 0x801B4260 (same 8x8 sheet, page 0x1E)
# from the table 0x801AFBC4 (8-byte entries: name pointer, track) into the pool 0x801AFD24-0x801B005C, plus three
# fixed strings (lui/addiu refs). The classic series song titles (I Am the Wind, Bloody Tears / Beginning /
# Vampire Killer remixes) keep their English titles (like 'I AM THE WIND' in the staff roll; also no cells left).
SOUND_TABLE = _o(0x2FBC4)
SOUND_COUNT = 44
SOUND_POOL = (_o(0x2FD24), _o(0x3005C))
SOUND_KO = {
    'Maria Battle': '마리아 결전', 'Chaconne C Moll': '샤콘 C단조', 'The Old Librarian': '늙은 사서',
    'Metamorphosis III': '변신 III', 'Black Banquet': '검은 연회', 'Final Toccata': '피날레',
    'Metamorphosis II': '변신 II', 'Blood Relations': '피의 인연', 'Death Ballad': '사신의 곡',
    'Heavenly Doorway': '천상의 문', 'The Door to the Abyss': '심연의 문', 'The Tragic Prince': '비극의 왕자',
    'Wandering Ghosts': '방황하는 유령', 'Enchanted Banquet': '마성의 연회', 'Curse Zone': '저주의 영역',
    'Dance of Pales': '망령의 춤', 'Lost Painting': '사라진 회화', 'Silence': '정적',
    'Rainbow Cemetery': '무지개 묘지', 'Abandoned Pit': '버려진 광산', 'Crystal Teardrops': '수정의 눈물',
    'Requiem for the Gods': '신들의 진혼곡', 'Land of Benediction': '축복의 대지',
    'Festival of Servants': '하인들의 축제', 'Door of Holy Spirits': '성령의 문',
    'Wood Carving Partita': '목각 모음곡', 'Nocturne (JP)': '야상곡 (JP)', 'Nocturne': '야상곡',
    'Tower of Mist': '안개의 탑', 'Marble Gallery': '대리석 회랑', 'Dance of Gold': '황금의 춤',
    "Dracula's Castle": '드라큘라 성', 'Prayer': '기도', 'Moonlight Nocturne': '월하의 야상곡',
    'Dance of Illusions': '환상의 춤', 'Prologue': '서곡', 'Metamorphosis': '변신',
}
SOUND_FIXED = [(_o(0x3005C), 'Now playing', '연주 중'), (_o(0x3006C), 'Play/Stop', '연주/정지'), (_o(0x30078), 'Back', '뒤로')]
# extra cells for Hangul once 0x60-0xDF are full: kanji / odd cells of the US sheet in the ASCII range
# ($ * ; < > @ \ ^ ` { | } DEL) - no SEL text draws those characters.
SMALL_EXTRA = [0x04, 0x0A, 0x1B, 0x1C, 0x1E, 0x20, 0x3C, 0x3E, 0x40, 0x5B, 0x5C, 0x5D, 0x5F]


def patch_sound(d, U):
    t0, t1 = SOUND_TABLE, SOUND_TABLE + SOUND_COUNT * 8
    p0, p1 = SOUND_POOL
    assert bytes(d[t0:t1]) == U[t0:t1] and bytes(d[p0:p1]) == U[p0:p1], 'sound-mode table/pool changed'
    for o in range(0, len(U) - 3, 4):            # only the table points into the pool
        if not (t0 <= o < t1):
            assert not (0x80180000 + p0 <= struct.unpack_from('<I', U, o)[0] < 0x80180000 + p1), hex(o)
    pool = bytearray()
    tab = bytearray(U[t0:t1])
    nko = 0
    for i in range(SOUND_COUNT):
        en = _small_us_at(U, struct.unpack_from('<I', U, t0 + 8 * i)[0])
        ko = SOUND_KO.get(en)
        nko += ko is not None
        struct.pack_into('<I', tab, 8 * i, 0x80180000 + p0 + len(pool))
        pool += small_enc(ko) if ko else small_us(en)
        pool += b'\0' * (-len(pool) % 4)
    assert len(pool) <= p1 - p0, len(pool)
    d[p0:p1] = bytes(pool) + bytes(p1 - p0 - len(pool))
    d[t0:t1] = tab
    for off, en, ko in SOUND_FIXED:
        orig = small_us(en)
        new = small_enc(ko)
        cap = _small_cap(U, off, len(orig))
        assert len(new) <= cap, (en, ko)
        _put(d, off, U[off:off + cap], new + bytes(cap - len(new)), 'sound ' + en)
    LOG.append(('SEL', 'sound mode: %d of %d track names Korean, pool %d of %d bytes' % (nko, SOUND_COUNT, len(pool), p1 - p0)))


def _small_us_at(U, va):
    o = va - 0x80180000
    e = U.index(255, o)
    return ''.join(chr(c + 0x20) for c in U[o:e])


def patch_areas(d, U):
    t0, t1 = AREA_TABLE, AREA_TABLE + AREA_COUNT * 8
    p0, p1 = AREA_POOL
    assert bytes(d[t0:t1]) == U[t0:t1], 'area pointer table changed'
    assert bytes(d[p0:p1]) == U[p0:p1], 'area string pool changed'
    for o in range(0, len(U) - 3, 4):            # nothing outside the table points into the pool
        if not (t0 <= o < t1):
            assert not (0x80180000 + p0 <= struct.unpack_from('<I', U, o)[0] < 0x80180000 + p1), hex(o)
    pool = bytearray()
    at = {}

    def put(ko):
        if ko not in at:
            at[ko] = 0x80180000 + p0 + len(pool)
            pool.extend(small_enc(ko))
        return at[ko]
    put('')
    tab = bytearray()
    for i in range(AREA_COUNT):
        a, b = struct.unpack_from('<II', U, t0 + 8 * i)
        en = (_small_us_at(U, a), _small_us_at(U, b))
        ko = AREA_KO[en] if en != ('', '') else ('', '')
        tab += struct.pack('<II', put(ko[0]), put(ko[1]))
    assert len(pool) <= p1 - p0, len(pool)
    d[p0:p1] = bytes(pool) + bytes(p1 - p0 - len(pool))
    d[t0:t1] = tab
    LOG.append(('SEL', 'area names: %d strings, %d of %d pool bytes' % (len(at), len(pool), p1 - p0)))


def _small_syllables():
    out = []
    texts = [ko for _, _, ko in SMALL_STRINGS] + [k for v in AREA_KO.values() for k in v]
    texts += list(SOUND_KO.values()) + [ko for _, _, ko in SOUND_FIXED]     # appended: older cells keep their codes
    for ko in texts:
        for ch in ko:
            if 0xAC00 <= ord(ch) <= 0xD7A3 and ch not in out:
                out.append(ch)
    return out


SMALL_CODES = list(range(SMALL_FIRST, SMALL_LAST + 1)) + SMALL_EXTRA
SMALL_CELLS = dict(zip(_small_syllables(), SMALL_CODES))
assert len(SMALL_CELLS) == len(_small_syllables()), ('8x8 cells full', len(_small_syllables()), len(SMALL_CODES))


def small_us(text):
    return bytes(ord(c) - 0x20 for c in text) + b'\xff'


def small_enc(text):
    out = bytearray()
    for ch in text:
        if ch in SMALL_CELLS:
            out.append(SMALL_CELLS[ch])
        else:
            c = ord(ch) - 0x20
            assert 0 <= c < 0x60 and c not in SMALL_CELLS.values(), ch   # cell taken by a Hangul syllable
            out.append(c)
    return bytes(out) + b'\xff'


def _small_cap(U, off, n):
    """bytes available: the US string + its FF + the zero padding after it (up to the next string)."""
    e = off + n
    while e < len(U) and U[e] == 0 and (e % 4):
        e += 1
    return e - off


def patch_small_strings(d, U):
    for off, en, ko in SMALL_STRINGS:
        orig = small_us(en)
        new = small_enc(ko)
        cap = _small_cap(U, off, len(orig))
        assert len(new) <= cap, (en, ko, len(new), cap)
        _put(d, off, U[off:off + cap], new + bytes(cap - len(new)), 'small ' + en)


def small_cells_image():
    """the 8x8 cells for SMALL_CELLS, colour 6 like the US sheet (glyph rows 0-6, cols 0-6)."""
    cells = {}
    G = gfx.bdf(7)
    for ch, code in SMALL_CELLS.items():
        w, h, xo, yo, dw, rows = G[ord(ch)]
        c = np.zeros((8, 8), np.uint8)
        top = 7 - h - yo
        c[top:top + h, xo:xo + w][rows.astype(bool)] = 6
        cells[code] = c
    return cells


def patch_title1(d, name):
    U = gfx._u(name)
    a = SMALL_SHEET
    assert bytes(d[a:a + 0x2000]) == U[a:a + 0x2000], 'F_TITLE1 8x8 sheet is not the US one'
    img = gfx.blk_get(d, a)
    for code, c in small_cells_image().items():
        r, k = code >> 4, code & 15
        img[r * 8:r * 8 + 8, k * 8:k * 8 + 8] = c
    gfx.blk_put(d, a, img)
    LOG.append((name, '8x8 sheet: %d Hangul cells 0x%02X-0x%02X' % (len(SMALL_CELLS), SMALL_FIRST,
                                                                    SMALL_FIRST + len(SMALL_CELLS) - 1)))


# ------------------------------------------------------------------ 2. tiled player-select header + name plates
TILE_BANK = 0x2D518             # 0x801AD518, 8x8 4bpp tiles, 32 bytes, index 1-based (0 = blank)
TILE_COUNT = 232
TILE_LISTS = {'header': (0x2F218, 18, 4), 'frame': (0x2F260, 11, 15),
              'alucard': (0x2F308, 11, 3), 'richter': (0x2F32C, 11, 3), 'maria': (0x2F350, 11, 3)}
PLATE_KO = {'alucard': '알카드', 'richter': '리히터', 'maria': '마리아'}


def _tile(d, i):
    if i == 0:
        return np.zeros((8, 8), np.uint8)
    b = np.frombuffer(bytes(d[TILE_BANK + (i - 1) * 32:TILE_BANK + i * 32]), np.uint8).reshape(8, 4)
    o = np.zeros((8, 8), np.uint8)
    o[:, 0::2] = b & 15
    o[:, 1::2] = b >> 4
    return o


def tiled(d, name):
    o, c, r = TILE_LISTS[name]
    img = np.zeros((r * 8, c * 8), np.uint8)
    for y in range(r):
        for x in range(c):
            img[y * 8:y * 8 + 8, x * 8:x * 8 + 8] = _tile(d, d[o + y * c + x])
    return img


def _plate(img, ko):
    """88x24 name plate: keep the bar (rows 0-3), redraw the name (rows 4-19) in the plate's style
    (outline 2, fill 3/4/5)."""
    o = img.copy()
    o[4:] = 0
    cov = gfx.fit_noto(ko, 78, 14, weight=900, serif=True)
    ink = gfx.bold(cov >= 0.42)
    cov = np.maximum(cov, np.pad(cov, ((0, 0), (1, 0)))[:, :-1])
    H, W = ink.shape
    m = np.zeros((H + 2, W + 2), bool)
    m[1:-1, 1:-1] = ink
    c = np.zeros(m.shape, np.float32)
    c[1:-1, 1:-1] = cov
    g = np.zeros(m.shape, np.uint8)
    g[gfx.dilate(m)] = 2
    g[m] = 5
    g[m & (c < 0.62)] = 4
    top = np.zeros(m.shape, bool)
    top[:2] = True
    g[m & top & (c < 0.62)] = 3
    x = (88 - g.shape[1]) // 2
    y = 4 + (16 - g.shape[0]) // 2
    gfx.paste(o, g, x, y)
    return o


def _player_header(img):
    o = img.copy()
    gfx._header(o, 0, '플', '레이어|선택', width=144)
    return o


def patch_tiles(d, U):
    for n, (o, c, r) in TILE_LISTS.items():
        assert bytes(d[o:o + c * r]) == U[o:o + c * r], ('tile list changed', n)
    assert bytes(d[TILE_BANK:TILE_BANK + TILE_COUNT * 32]) == U[TILE_BANK:TILE_BANK + TILE_COUNT * 32]
    use = {}
    for n, (o, c, r) in TILE_LISTS.items():
        for k in range(c * r):
            use.setdefault(U[o + k], set()).add(n)
    targets = ['header', 'alucard', 'richter', 'maria']
    pool = sorted(i for i, s in use.items() if i and s <= set(targets))       # slots only these lists use
    assert all(i not in use or not (use[i] - set(targets)) for i in pool)
    imgs = {'header': _player_header(tiled(U, 'header'))}
    for n in ('alucard', 'richter', 'maria'):
        imgs[n] = _plate(tiled(U, n), PLATE_KO[n])
    slot_of = {}
    free = list(pool)
    lists = {}
    for n in targets:
        o, c, r = TILE_LISTS[n]
        idx = bytearray()
        im = imgs[n]
        for y in range(r):
            for x in range(c):
                t = im[y * 8:y * 8 + 8, x * 8:x * 8 + 8]
                if not t.any():
                    idx.append(0)
                    continue
                key = t.tobytes()
                if key not in slot_of:
                    assert free, 'not enough tile slots'
                    s = free.pop(0)
                    slot_of[key] = s
                    d[TILE_BANK + (s - 1) * 32:TILE_BANK + s * 32] = ((t[:, 0::2] & 15) | (t[:, 1::2] << 4)).astype(np.uint8).tobytes()
                idx.append(slot_of[key])
        d[o:o + c * r] = bytes(idx)
        lists[n] = idx
    LOG.append(('SEL', 'player-select header + 3 name plates re-tiled: %d of %d slots used' % (len(slot_of), len(pool))))
    return imgs


# ------------------------------------------------------------------ 3. gothic 16x16 strings
GOTHIC_DRAWER = _v(0x801BB7D0)         # unused 12x16-font drawer, 44 instructions -> new Korean gothic drawer
GOTHIC_DRAWER_END = _v(0x801BB880)
SEL_BASE = 0x80180000
SPRITE = _v(0x801BB6A4)                # (x, y, w, h, [u, v, clut, tpage, flag, colour] on the stack)
GOTHIC_TPAGE = 0xD                  # VRAM (832,0) 4bpp = F_SEL 0x28000-0x2FFFF
GOTHIC_CLUT = 0x200                 # same palette as the US gothic letters
# empty 16x16 cells of that page (checked against F_SEL and a VRAM dump of the SEL screen)
GOTHIC_FREE = [0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68] + \
              list(range(0xF0, 0xFF))
GOTHIC_BLANK = 0xFF                 # left empty: the space character

# string (SEL file offset, US bytes incl. NUL, Korean)
GOTHIC_STRINGS = [
    (_o(0x27EF8), b'select\0', '그대의'),
    (_o(0x27F00), b'your\0', '운명을'),
    (_o(0x27F08), b'destiny\0', '선택하라'),
    (_o(0x300CC), b'new game\0', '새 게임'),
    (_o(0x300D8), b'used\0', '사용 중'),
    (_o(0x300E0), b'no data\0', '데이터 없음'),
    (_o(0x300E8), b'no\0', '카드'),
    (_o(0x300EC), b'card\0', '없음'),
    (_o(0x30080), b'sound mode\0', '사운드 모드'),   # sound-mode screen title (own drawer 0x801B32EC, see SOUND_TITLE)
]
# call sites of the US drawer 0x801BB8BC that draw the strings above
GOTHIC_CALLS = [_v(x) for x in (0x801B3408, 0x801B3420, 0x801B3438, 0x801B70C0, 0x801B7188, 0x801B71A0)]
# x re-centring: (va, US instruction, new instruction)
GOTHIC_X = [
    (_v(0x801B3400), 0x340500F0, 0x34050108),   # 'select'  x 240 -> 264 (centre 288, 3 cells)
    (_v(0x801B3418), 0x34050100, 0x34050108),   # 'your'    x 256 -> 264
    (_v(0x801B3430), 0x340500E8, 0x34050100),   # 'destiny' x 232 -> 256 (4 cells)
    (_v(0x801B708C), 0x340500A0, 0x340500A0),   # 'used'    x 160 (4 cells, centre 192) unchanged
    (_v(0x801B709C), 0x34050088, 0x34050090),   # 'no data' x 136 -> 144 (6 cells)
    (_v(0x801B70B8), 0x34050080, 0x340500A0),   # 'new game' x 128 -> 160 (4 cells)
    (_v(0x801B7198), 0x02E02821, 0x26E50010),   # 'card' x = s7 -> s7 + 16 (2 cells under 'no')
]
# sound-mode title: 0x801B5DC4 draws 'sound mode' with the page-0xC a-z drawer 0x801B32EC (a3 = clut 0x200)
# -> the Korean gothic drawer (a3 = sprite flag 1 like its other callers), x 0x70 -> 0x90 (6 cells, centre 192)
SOUND_TITLE = [(_v(0x801B5DCC), 0x34050070, 0x34050090),
               (_v(0x801B5DD4), 0x0C000000 | ((_v(0x801B32EC) >> 2) & 0x3FFFFFF), 0x0C000000 | ((GOTHIC_DRAWER >> 2) & 0x3FFFFFF)),
               (_v(0x801B5DD8), 0x34070200, 0x34070001)]


def _gothic_syllables():
    out = []
    for _, _, ko in GOTHIC_STRINGS:
        for ch in ko:
            if ch != ' ' and ch not in out:
                out.append(ch)
    return out


GOTHIC_CELLS = dict(zip(_gothic_syllables(), GOTHIC_FREE))
assert len(GOTHIC_CELLS) == len(_gothic_syllables()) and GOTHIC_BLANK not in GOTHIC_CELLS.values()


def gothic_enc(text):
    return bytes(GOTHIC_BLANK if ch == ' ' else GOTHIC_CELLS[ch] for ch in text) + b'\0'


def _gothic_code_safe():
    """the stack slots 16..36 are the sprite arguments, so callee-saved registers live at 40+ only."""
    a = Asm(GOTHIC_DRAWER)
    a.addiu('sp', 'sp', -64)
    a.sw('ra', 60, 'sp'); a.sw('s0', 56, 'sp'); a.sw('s1', 52, 'sp'); a.sw('s2', 48, 'sp'); a.sw('s3', 44, 'sp')
    a.addu('s0', 'a0', 'zero'); a.addu('s1', 'a1', 'zero'); a.addu('s2', 'a2', 'zero'); a.addu('s3', 'a3', 'zero')
    a.label('loop')
    a.lbu('t0', 0, 's0')
    a.nop()                                     # R3000 load delay: t0 is not valid in the next slot
    a.beq('t0', 'zero', 'end')
    a.andi('t1', 't0', 0x0F)
    a.sll('t1', 't1', 4); a.sw('t1', 16, 'sp')                                  # u = (b & 15) * 16
    a.andi('t1', 't0', 0xF0); a.sw('t1', 20, 'sp')                              # v = b & 0xF0
    a.ori('t1', 'zero', GOTHIC_CLUT); a.sw('t1', 24, 'sp')
    a.ori('t1', 'zero', GOTHIC_TPAGE); a.sw('t1', 28, 'sp')
    a.sw('s3', 32, 'sp')
    a.ori('t1', 'zero', 0x40); a.sw('t1', 36, 'sp')
    a.addu('a0', 's1', 'zero'); a.addu('a1', 's2', 'zero')
    a.ori('a2', 'zero', 16)
    a.jal(SPRITE)
    a.ori('a3', 'zero', 16)
    a.addiu('s0', 's0', 1)
    a.b('loop')
    a.addiu('s1', 's1', 16)
    a.label('end')
    a.lw('ra', 60, 'sp'); a.lw('s0', 56, 'sp'); a.lw('s1', 52, 'sp'); a.lw('s2', 48, 'sp'); a.lw('s3', 44, 'sp')
    a.jr('ra')
    a.addiu('sp', 'sp', 64)
    code = a.assemble()
    assert len(code) <= GOTHIC_DRAWER_END - GOTHIC_DRAWER, len(code)
    return code


def patch_gothic(d, U):
    o = GOTHIC_DRAWER - SEL_BASE
    n = GOTHIC_DRAWER_END - GOTHIC_DRAWER
    code = _gothic_code_safe()
    _put(d, o, U[o:o + n], code + U[o + len(code):o + n], 'gothic drawer')
    old = jal_word(_v(0x801BB8BC))
    for va in GOTHIC_CALLS:
        _put(d, va - SEL_BASE, old, jal_word(GOTHIC_DRAWER), 'gothic call %08X' % va)
    for va, a, b in GOTHIC_X:
        _put(d, va - SEL_BASE, struct.pack('<I', a), struct.pack('<I', b), 'gothic x %08X' % va)
    for va, a, b in SOUND_TITLE:
        _put(d, va - SEL_BASE, struct.pack('<I', a), struct.pack('<I', b), 'sound title %08X' % va)
    for off, en, ko in GOTHIC_STRINGS:
        new = gothic_enc(ko)
        assert len(new) <= len(en), (ko, len(new), len(en))
        _put(d, off, en, new + bytes(len(en) - len(new)), 'gothic ' + en.decode())


# hand-drawn cells: Noto Serif 900's 모 at 13 px has serif ears on the ㅁ and a 1-px counter -> read as 보
GOTHIC_HAND = {
    '모': ['..##########..',
           '..##########..',
           '..##......##..',
           '..##......##..',
           '..##......##..',
           '..##......##..',
           '..##########..',
           '..##########..',
           '......##......',
           '......##......',
           '##############',
           '##############'],
}


def gothic_cell(ch):
    """16x16 cell in the US gothic style: outline 2, fill 5 with 4/3 on the lighter edges."""
    if ch in GOTHIC_HAND:
        ink = np.array([[c == '#' for c in r] for r in GOTHIC_HAND[ch]], bool)
        cov = ink.astype(np.float32)
    else:
        cov = gfx.fit_noto(ch, 13, 14, weight=900, serif=True)
        ink = gfx.bold(cov >= 0.42)
    cov = np.maximum(cov, np.pad(cov, ((0, 0), (1, 0)))[:, :-1])
    H, W = ink.shape
    m = np.zeros((16, 16), bool)
    c = np.zeros((16, 16), np.float32)
    y, x = (16 - H) // 2, (16 - W) // 2
    m[y:y + H, x:x + W] = ink
    c[y:y + H, x:x + W] = cov
    g = np.zeros((16, 16), np.uint8)
    g[gfx.dilate(m)] = 2
    g[m] = 5
    g[m & (c < 0.62)] = 4
    return g


FSEL_GOTHIC_BLOCKS = {(0, 0): 0x28000, (1, 0): 0x2A000, (0, 1): 0x2C000, (1, 1): 0x2E000}   # (u//128, v//128)


def patch_fsel(d, name):
    U = gfx._u(name)
    imgs = {}
    for k, off in FSEL_GOTHIC_BLOCKS.items():
        assert bytes(d[off:off + 0x2000]) == U[off:off + 0x2000], 'F_SEL page 0xD block changed'
        imgs[k] = gfx.blk_get(d, off)
    for ch, b in GOTHIC_CELLS.items():
        u, v = (b & 15) * 16, b & 0xF0
        im = imgs[(u // 128, v // 128)]
        cell = im[v % 128:v % 128 + 16, u % 128:u % 128 + 16]
        assert not cell.any(), ('gothic cell not empty', hex(b))
        cell[:] = gothic_cell(ch)
    for k, off in FSEL_GOTHIC_BLOCKS.items():
        gfx.blk_put(d, off, imgs[k])
    LOG.append((name, '%d gothic Hangul cells in texture page 0xD' % len(GOTHIC_CELLS)))
    patch_plates(d, name)


# 'CARD' (memory-card frame) and 'Name' (name-entry box) plates in F_SEL: white (5) Latin letters, 5 rows tall,
# on the gold plate (bg 7). (block, letter rows y0..y1, interior x0..x1, Korean). 0x2A000 is the slot-2 card plate.
PLATES = [(0x2000, 9, 14, 78, 98, '카드'), (0x22000, 9, 14, 78, 98, '카드'), (0x2A000, 9, 14, 46, 66, '카드'),
          (0x0000, 88, 95, 70, 90, '이름'), (0x20000, 88, 95, 70, 90, '이름')]


def patch_plates(d, name):
    U = gfx._u(name)
    for off, y0, y1, x0, x1, ko in PLATES:
        a = gfx.blk_get(U, off)
        im = gfx.blk_get(d, off)
        assert (im[y0 - 4:y1 + 2, x0 - 1:x1 + 1] == a[y0 - 4:y1 + 2, x0 - 1:x1 + 1]).all(), ('plate changed', hex(off))
        assert (a[y0:y1, x0:x1] == 5).sum() > 20, ('no plate letters', hex(off))
        r = im[y0:y1, x0:x1]
        r[r == 5] = 7                                           # remove the Latin letters (plate gold)
        m = gfx.galmuri(ko, 7).astype(bool)
        h, w = m.shape
        x = (x0 + x1 - w) // 2
        y = (y0 + y1 - 1) // 2 - h // 2
        sh = np.zeros((h + 1, w + 1), bool)
        sh[1:, 1:] = m
        sh[:h, :w] &= ~m
        im[y:y + h + 1, x:x + w + 1][sh] = 1                     # dark drop shadow (plate outline colour)
        im[y:y + h, x:x + w][m] = 5
        gfx.blk_put(d, off, im)
    LOG.append((name, "'CARD' / 'Name' plates -> 카드 / 이름 (%d plates)" % len(PLATES)))


# ------------------------------------------------------------------ entry
SEL_NAMES = ('ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN')


def patch_sel(d, name):
    U = gfx._u('ST/SEL/SEL.BIN') if name == 'BIN/SELRIC2.BIN' else gfx._u(name)
    UR = gfx._u(name)
    # SELRIC2 = SEL with a different ending cutscene (0xC71A-0xD5EE); everything used here is identical
    for a, b in ((0x27D00, 0x2F4F0), (_o(0x2F54C), _o(0x30110)), (0x2D518, 0x2F4F0), (_o(0x33000), _o(0x3C000)), (0x128, 0x3A8), AREA_POOL):
        assert UR[a:b] == U[a:b], (name, hex(a))
    patch_small_strings(d, UR)
    patch_sound(d, UR)
    patch_tiles(d, UR)
    patch_gothic(d, UR)
    patch_areas(d, UR)
    LOG.append((name, 'small strings %d, gothic strings %d' % (len(SMALL_STRINGS), len(GOTHIC_STRINGS))))


def patch(path, data):
    name = _base(path)
    d = bytearray(data)
    if name in SEL_NAMES:
        if bytes(d[GOTHIC_DRAWER - SEL_BASE:GOTHIC_DRAWER - SEL_BASE + 8]) == _gothic_code_safe()[:8]:
            return bytes(d)                     # already done
        patch_sel(d, name)
    elif name == 'BIN/F_TITLE1.BIN':
        a = SMALL_SHEET
        if bytes(d[a:a + 0x2000]) != gfx._u(name)[a:a + 0x2000]:
            return bytes(d)
        patch_title1(d, name)
    elif name == 'ST/SEL/F_SEL.BIN':
        if bytes(d[0x28000:0x30000]) != gfx._u(name)[0x28000:0x30000]:
            return bytes(d)
        patch_fsel(d, name)
    return bytes(d)


# ------------------------------------------------------------------ previews (python selui.py)
def _render_small(sheet, b, scale=3):
    cells = []
    for c in b:
        if c == 0xFF:
            break
        r, k = c >> 4, c & 15
        cells.append(sheet[r * 8:r * 8 + 8, k * 8:k * 8 + 8])
    return np.hstack(cells) if cells else np.zeros((8, 8), np.uint8)


def _render_gothic_us(fsel, s):
    sheet = gfx.blk_get(fsel, 0x26000)            # u 128-255, v 128-255 of page 0xC
    tab = {}
    t = gfx._u("ST/SEL/SEL.BIN")[0x46C:0x46C + 99]
    for i in range(32):
        tab[t[3 * i]] = (t[3 * i + 1], t[3 * i + 2])
    out = []
    for ch in s.rstrip(b'\0'):
        u, v = tab.get(ch, (t[3 * 32 + 1], t[3 * 32 + 2]))
        out.append(sheet[v - 128:v - 112, u - 128:u - 112])
    return np.hstack(out)


def _render_gothic_new(fsel, b):
    page = np.vstack([np.hstack([gfx.blk_get(fsel, 0x28000), gfx.blk_get(fsel, 0x2A000)]),
                      np.hstack([gfx.blk_get(fsel, 0x2C000), gfx.blk_get(fsel, 0x2E000)])])
    out = []
    for c in b:
        if c == 0:
            break
        u, v = (c & 15) * 16, c & 0xF0
        out.append(page[v:v + 16, u:u + 16])
    return np.hstack(out)


def _stack(rows, gap=4):
    W = max(r.shape[1] for r in rows)
    out = []
    for r in rows:
        p = np.zeros((r.shape[0] + gap, W), np.uint8)
        p[:r.shape[0], :r.shape[1]] = r
        out.append(p)
    return np.vstack(out)


def previews():
    os.makedirs(gfx.PREVIEW, exist_ok=True)
    sel_u = gfx._u('ST/SEL/SEL.BIN')
    sel_p = gfx.patch_file('ST/SEL/SEL.BIN', sel_u)
    t1_u = gfx._u('BIN/F_TITLE1.BIN')
    t1_p = gfx.patch_file('BIN/F_TITLE1.BIN', t1_u)
    fs_u = gfx._u('ST/SEL/F_SEL.BIN')
    fs_p = gfx.patch_file('ST/SEL/F_SEL.BIN', fs_u)
    # player-select header and name plates (tiles)
    b = _stack([tiled(sel_u, n) for n in ('header', 'alucard', 'richter', 'maria')])
    a = _stack([tiled(sel_p, n) for n in ('header', 'alucard', 'richter', 'maria')])
    gfx._pair(b, a, os.path.join(gfx.PREVIEW, 'sel_player_select_tiles.png'), 4)
    # small-font strings
    su, sp = gfx.blk_get(t1_u, SMALL_SHEET), gfx.blk_get(t1_p, SMALL_SHEET)
    b = _stack([_render_small(su, sel_u[o:o + 20]) for o, _, _ in SMALL_STRINGS])
    a = _stack([_render_small(sp, sel_p[o:o + 20]) for o, _, _ in SMALL_STRINGS])
    gfx._pair(b, a, os.path.join(gfx.PREVIEW, 'sel_small_strings.png'), 4)
    gfx._pair(su, sp, os.path.join(gfx.PREVIEW, 'f_title1_8x8_sheet.png'), 3)
    # save-location names (both lines of each area in the file-select box)
    rows_u, rows_p = [], []
    for i in range(AREA_COUNT):
        pu = struct.unpack_from('<II', sel_u, AREA_TABLE + 8 * i)
        pp = struct.unpack_from('<II', sel_p, AREA_TABLE + 8 * i)
        if sel_u[pu[0] - SEL_BASE] == 0xFF and sel_u[pu[1] - SEL_BASE] == 0xFF:
            continue
        for a, b, rows, sheet, data in ((pu, None, rows_u, su, sel_u), (pp, None, rows_p, sp, sel_p)):
            rows.append(_stack([_render_small(sheet, data[x - SEL_BASE:x - SEL_BASE + 20]) for x in a], gap=0))
    gfx._pair(_stack(rows_u), _stack(rows_p), os.path.join(gfx.PREVIEW, 'sel_area_names.png'), 3)
    # gothic strings
    b = _stack([_render_gothic_us(fs_u, en) for _, en, _ in GOTHIC_STRINGS])
    a = _stack([_render_gothic_new(fs_p, sel_p[o:o + 12]) for o, _, _ in GOTHIC_STRINGS])
    gfx._pair(b, a, os.path.join(gfx.PREVIEW, 'sel_gothic_strings.png'), 3)


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    previews()
    for l in LOG:
        print(*l)
