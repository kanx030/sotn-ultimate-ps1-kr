"""DRA engine-A (8x8 menu font) and engine-C (12x16 pre-rendered labels) Korean text.

  python draa.py extract  -> work/trans/DRA_A.json (keeps edited 'ko' by id)
  python draa.py check    -> encodability / refs / sizes report + work/draa_preview.png

Build use (after drabapply):
  import draa
  dra = draa.patch_dra_a(dra)                       # DRA.BIN
  data = draa.patch_fgame('BIN/F_GAME.BIN', data)   # also 'BIN/F_GAME2.BIN'

Engine A (MenuDrawStr 0x800F4494): 1 byte per 8x8 cell of the sheet at F_GAME.BIN 0x30000 (VRAM 896,256).
The Korean build (K, JP based) replaced lower case / kana / kanji cells by Hangul pieces:
  * a syllable is   <final cell> FF <initial+medial cell>   (the FF xx overlay draws xx over the previous
    cell; K moved the overlay from y-8 to y-2, so the CV cell sits 2 px up and the final shows below it);
  * no final -> final cell 00 (blank). Digits, A-Z and most symbols keep the US cell = ASCII-0x20.
  * strings end with FF 00.
The cell labels below were read off K's sheet and verified by decoding every K name (equipment, accessory,
menu, enemy tables): all of them decode to sensible Korean (see `python draa.py check`).

Engine C (label drawer 0x800F4364): index strings (FF end) into 12x16 cells pre-rendered by 0x800F76F4 from
2-byte set strings. K renders three 16-glyph sets (modes 0, 0x100, 1) and draws main menu, equipment
categories, slot names, list headers and ATT/DEF with it. Here: same three K sets; MenuDrawStr gets an
entry hook: a string starting FE dx dy is drawn with engine C (indices follow) at (x+dx, y+dy), so g_MenuStr
labels switch engine without touching the call sites. dx/dy copy K's positions for the same call.
"""
import os, sys, json, struct
from addrmap import dra as _R      # DRA address of the old base (v1.2) -> current base, signature-checked

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from asm import Asm, _i, jal_word

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
WORK = os.path.join(ROOT, 'work')
import base as _base
U_DRA = os.path.join(_base.U, 'DRA.BIN')
K_DRA = os.path.join(WORK, 'K', 'DRA.BIN')
K_EXE = os.path.join(WORK, 'K', 'SLPM_860.23')
U_FGAME = os.path.join(_base.U, 'BIN', 'F_GAME.BIN')
K_FGAME = os.path.join(WORK, 'K', 'BIN', 'F_GAME.BIN')
OUT = os.path.join(WORK, 'trans', 'DRA_A.json')
DRA_B = os.path.join(WORK, 'trans', 'DRA_B.json')
PREVIEW = os.path.join(WORK, 'draa_preview.png')
BASE = 0x800A0000

# (va, count, stride) US / K
TABLES = {
    'equip': ((0x800A499C, 228, 0x34), (0x800A4B70, 217, 0x34)),
    'acc':   ((0x800A77EC, 93, 0x20), (0x800A7784, 90, 0x20)),
    'menu':  ((0x800A838C, 110, 4), (0x800A82C4, 85, 4)),
    'enemy': ((0x800A8544, 426, 0x28), (0x800A8908, 400, 0x28)),
}
LIMIT = {'equip': 16, 'acc': 16, 'enemy': 16}   # inventory: 128 px (count at x+128); enemy: same width
HOLDER = _R(0x800DC064)            # "Holder" (button config 0x800F4CC8, status 0x800F5768): rewritten in place
FONT_RAM_K = (0x801F0000, 0x80200000, 0x243E8)   # K names live in K's font RAM block (K exe file offset)

FGAME_SHEET = (0x30000, 0x32000)

# ------------------------------------------------------------------ K 8x8 sheet labels
_CV_ROWS = {
    0x4: '가개갸거게겨고과교구궈규그기까?',
    0x5: '나너?노뇌뉴느니?대더데도되다두',
    0x6: '듀?????드디따뜨라래러레려로',
    0x7: '?뢰루르리마매머메며모묘무미바배',
    0x8: '버베벼보부브비빠빼뼈사새샤서세셔',
    0x9: '셰소쇼수슈스시쓰아애야어에여오와',
    0xA: '외요우워웨위유으의이자재저제져조',
    0xB: '주쥐쥬즈지쪼차처체초추츄츠치카캐',
    0xC: '커케코쿠퀴큐크키타태터테토투트티',
    0xD: '파패퍼페포푸프피하해허헤호화회효',
    0xE: '????????????후휴흐히',
}
CV = {}
for _r, _s in _CV_ROWS.items():
    for _k, _ch in enumerate(_s):
        if _ch != '?':
            CV[_r * 16 + _k] = _ch
CV.update({0xFD: '꼬', 0xFE: '네', 0x3B: '료', 0x6F: '로'})
# g7-only CV codes: K sheet cells 0xE0.. are unused ('?'); every 8x8 drawer goes through g7 CORE, which renders
# the whole syllable from its tables, so these codes need no sheet cell (g7.tables adds them).
EXT_CV = {0xE0: '켜', 0xE1: '끄', 0xE2: '또'}
# final (batchim) cells; 0x0C is a second ㅆ shape K never uses
FIN = {0x00: '', 0x0A: 'ㄱ', 0x1B: 'ㄲ', 0x1C: 'ㄴ', 0x1E: 'ㄷ', 0x20: 'ㄹ', 0x3C: 'ㅁ', 0x3E: 'ㅂ',
       0x61: 'ㅅ', 0xFC: 'ㅆ', 0x62: 'ㅇ', 0x63: 'ㅊ', 0x64: 'ㅌ'}
_FIN_ALT = {0x0C: 'ㅆ'}
# plain cells kept from the US sheet (US encoding = ASCII-0x20); K reused '*' ',' ';' '<' '>' '@' '[' '\' ']' '^' '_'
PLAIN = {c: chr(c + 0x20) for c in range(0x00, 0x40)
         if c not in (0x0A, 0x0C, 0x1B, 0x1C, 0x1E, 0x20, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F)}
PLAIN.update({0x65: '・', 0x70: 'ー'})
PLAIN_DEC = dict(PLAIN)
PLAIN_DEC.update({0x58: 'x', 0x4F: 'o', 0x52: 'r'})    # unchanged US cells, decode only
ARROWS = range(0xE0, 0xEC)                              # arrow / button icons (spell combos)

JONG = 'ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ'
_CV_ENC = {ch: c for c, ch in list(CV.items()) + list(EXT_CV.items())}
_FIN_ENC = {f: c for c, f in FIN.items()}
_PLAIN_ENC = {ch: c for c, ch in PLAIN.items()}
_PLAIN_ENC.update({'·': 0x65, '-': 0x0D})


def _split(ch):
    o = ord(ch) - 0xAC00
    if not 0 <= o < 11172:
        return None
    return chr(0xAC00 + o - o % 28), (JONG[o % 28 - 1] if o % 28 else '')


def encode_a(text):
    """Korean/ASCII text -> engine-A bytes (no terminator). Raises ValueError listing unencodable chars."""
    out, bad = bytearray(), []
    for ch in text:
        sp = _split(ch)
        if sp:
            cv, fin = sp
            if cv in _CV_ENC and fin in _FIN_ENC:
                out += bytes([_FIN_ENC[fin], 0xFF, _CV_ENC[cv]])
            else:
                bad.append(ch)
        elif ch in _PLAIN_ENC:
            out.append(_PLAIN_ENC[ch])
        else:
            bad.append(ch)
    if bad:
        raise ValueError('engine A cannot encode %r in %r' % (''.join(bad), text))
    import g7
    g7.USED.update(text)
    _assert_safe(bytes(out))
    return bytes(out)


def _assert_safe(b):
    # MenuDrawStr 0x800F44DC: a byte pair C0 D2 right after a char switches the combo-colour flag
    assert b'\xc0\xd2' not in b, b.hex()
    assert not b or b[0] != 0xFE, 'FE first byte = engine-C marker'
    i = 0
    while i < len(b):            # FF must be followed by a non-zero cell (FF 00 = end)
        if b[i] == 0xFF:
            assert i + 1 < len(b) and b[i + 1] not in (0, 0xFF), b.hex()
            i += 2
        else:
            i += 1


def decode_a(b):
    s, i = '', 0
    while i < len(b):
        if i + 2 < len(b) and b[i + 1] == 0xFF:
            f, c = b[i], b[i + 2]
            fin = FIN.get(f, _FIN_ALT.get(f))
            if fin is not None and (c in CV or c in EXT_CV):
                cv = CV[c] if c in CV else EXT_CV[c]
                s += chr(ord(cv) + JONG.index(fin) + 1) if fin else cv
            else:
                s += '{%02x^%02x}' % (f, c)
            i += 3
            continue
        c = b[i]
        if c == 0xFF:
            s += '{^%02x}' % b[i + 1]; i += 2; continue
        s += PLAIN_DEC.get(c, '{%02x}' % c)
        i += 1
    return s


def cells_a(b):
    """Screen width in 8 px cells."""
    n, i = 0, 0
    while i < len(b):
        if b[i] == 0xFF:
            i += 2
        else:
            n += 1; i += 1
    return n


# ------------------------------------------------------------------ binaries
_CACHE = {}
def _rd(p):
    if p not in _CACHE:
        _CACHE[p] = open(p, 'rb').read()
    return _CACHE[p]


def w32(d, o):
    return struct.unpack_from('<I', d, o)[0]


def a_str(d, o):
    """engine-A string at file offset o (FF xx overlays, FF 00 end) -> bytes without terminator."""
    e = o
    while True:
        if d[e] == 0xFF:
            if d[e + 1] == 0:
                return d[o:e]
            e += 2
        else:
            e += 1


def k_name(p):
    if FONT_RAM_K[0] <= p < FONT_RAM_K[1]:
        return a_str(_rd(K_EXE), FONT_RAM_K[2] + p - FONT_RAM_K[0])
    if BASE <= p < BASE + len(_rd(K_DRA)):
        return a_str(_rd(K_DRA), p - BASE)
    return None


def u_dec(b):
    """US English 8x8 string -> text."""
    s, i = '', 0
    while i < len(b):
        c = b[i]
        if c == 0xFF:
            s += '{^%02x}' % b[i + 1]; i += 2; continue
        s += chr(c + 0x20) if c < 0x60 else '{%02x}' % c
        i += 1
    return s


# ------------------------------------------------------------------ Korean for entries K lacks
NEW_KO = {
    # Ultimate-only equipment / accessories
    ('equip', 169): '상한 밥', ('equip', 170): '맛있는 식사', ('equip', 171): '사인 색지',
    ('equip', 172): '알카드 스피어', ('equip', 173): '우드랜드 실드', ('equip', 174): '아스트랄 대거',
    ('equip', 175): '더블 액스',
    ('acc', 61): '스타우로라이트',          # K kept "STAUROLITE"
    ('acc', 90): '빛나는 옷', ('acc', 91): '무지개 망토', ('acc', 92): '가사 카드',
    # status screen words (K keeps these English)
    ('menu', 1): '힘', ('menu', 2): '체력', ('menu', 3): '지력', ('menu', 4): '행운',
    ('menu', 5): '경험치', ('menu', 6): '다음', ('menu', 7): '골드', ('menu', 8): '레벨',
    ('menu', 9): '시간', ('menu', 10): '탐색', ('menu', 11): '처치', ('menu', 14): '하트',
    ('menu', 15): '상태', ('menu', 37): '정상', ('menu', 38): '중독', ('menu', 39): '석화',
    ('menu', 40): '저주',
    # Ultimate-only enemies
    ('enemy', 400): '가고일', ('enemy', 401): '코퍼 아머', ('enemy', 402): '이프리트',
    ('enemy', 404): '스켈레톤 리더', ('enemy', 405): '가드너', ('enemy', 406): '인면수',
    ('enemy', 408): '마리아', ('enemy', 413): '워터 리퍼', ('enemy', 414): '맨 이터',
    ('enemy', 415): '가고일', ('enemy', 416): '가고일', ('enemy', 417): '스펙터',
    ('enemy', 418): '윌 오 위스프', ('enemy', 420): '스켈레톤 브리더', ('enemy', 421): '스켈레톤 비스트',
    ('enemy', 423): '와이트', ('enemy', 424): '레이스', ('enemy', 425): '스켈레톤 가디언',
}
KEEP_EN = {('menu', 0), ('menu', 12), ('menu', 13), ('menu', 19), ('menu', 41), ('menu', 42)}
# ALUCARD, HP, MP, colour-bar dots, dashes, ALUCART: unchanged (upper case / symbols render on K's sheet)

# engine-C labels: g_MenuStr index -> (K index-string ptr, dx, dy). dx/dy = K call position - US call position.
#   slots (status 0x800F5770: US 8,0x28  K 0x18,0x28); main menu 0x800F644C (US x+18/14/14/14/2, y+4..68;
#   K x+12/6/6/0/6, y+0..64); familiar list 0x800F5C74 (US 0x78,0x28  K 0x88,0x24); special moves
#   0x800F5870 (US 0x68,0x28  K 0x88,0x24); categories 0x800F6550 (US y+8  K y+4).
ENGC = {85: (0x2DB8, 16, 0), 86: (0x2DBC, 16, 0), 87: (0x2DC0, 16, 0), 88: (0x2DC4, 16, 0),
        89: (0x2DC8, 16, 0), 90: (0x2DCC, 16, 0), 91: (0x2DD0, 16, 0),
        92: (0x2D7C, -6, -4), 93: (0x2D80, -8, -4), 94: (0x2D84, -8, -4), 95: (0x2D88, -14, -4),
        96: (0x2DD4, 4, -4), 97: (0x2DD8, 16, -4), 98: (0x2D78, 32, -4)}
for _n in range(11):
    ENGC[99 + _n] = (0x2D8C + 4 * _n, 0, -4)
K_SETS = (0x2D64, 0x2D68, 0x2D6C)        # K ptrs to the three 16-glyph set strings
K_ATT, K_DEF = 0x2D70, 0x2D74
U_SETPTR, U_ATT, U_DEF = (_R(0x800A2B30) - BASE, _R(0x800A2B34) - BASE, _R(0x800A2B38) - BASE)

# ------------------------------------------------------------------ code patch points (US file offsets)
OVL_Y = _R(0x800F4544)                       # addiu a2,a2,-8  -> -2 (K 0x800F6B48)
MDS = _R(0x800F4494)                         # MenuDrawStr entry
MDS_ORIG = bytes.fromhex('d8ffbd272000b4af1380143c')
LABEL = _R(0x800F4364)                       # 12x16 label drawer
SETR = _R(0x800F76F4)                        # 2-byte set renderer
SETCALL = _R(0x800F9DEC)                     # jal 0x800F76F4 (a0 = *0x800A2B30, a1 = 0)
FLAG = 0x8013784C                        # MenuDrawSprite grey/combo colour flag


def k_engc_set():
    """K's three set strings (2-byte font codes, same font as our build); trailing junk -> 0x8140."""
    K = _rd(K_DRA)
    out = []
    for p in K_SETS:
        o = w32(K, p) - BASE
        s = K[o:K.index(b'\0', o)]
        assert len(s) == 32, len(s)
        out.append(s)
    s = bytearray(out[2])
    s[28:32] = b'\x81\x40\x81\x40'       # "他い" leftovers (cells 0x2E/0x2F, unused)
    out[2] = bytes(s)
    return out


def k_index(p):
    K = _rd(K_DRA)
    o = w32(K, p) - BASE
    return K[o:K.index(b'\xff', o)]


def engc_cells():
    """cell index -> syllable (for decoding / encoding engine-C labels)."""
    import kmap
    sets = k_engc_set()
    cells = {}
    for si, (row, page) in enumerate(((0, 0), (0, 1), (1, 0))):
        s = sets[si]
        for k in range(16):
            ch = kmap.decode(s[2 * k:2 * k + 2])
            cells[(row << 5) | (page << 4) | k] = ch
    return cells


def decode_c(idx):
    c = engc_cells()
    return ''.join(c.get(x, '?') for x in idx)


def encode_c(text):
    c = engc_cells()
    inv = {}
    for k, ch in sorted(c.items()):
        inv.setdefault(ch, k)
    try:
        return bytes(inv[ch] for ch in text)
    except KeyError as e:
        raise ValueError('engine C has no cell for %s in %r' % (e, text))


# ------------------------------------------------------------------ entries
def _data_ptrs(d, lo, hi):
    """file offsets of aligned words pointing into [lo, hi)."""
    out = {}
    for o in range(0, len(d) - 3, 4):
        v = w32(d, o)
        if lo <= v < hi:
            out.setdefault(v, []).append(o)
    return out


def collect():
    U = _rd(U_DRA)
    K = _rd(K_DRA)
    items, order = {}, []
    for cat, ((ub, un, us), (kb, kn, ks)) in TABLES.items():
        for i in range(un):
            ro = ub - BASE + i * us
            p = w32(U, ro)
            if not (BASE <= p < BASE + len(U)):
                continue
            en_b = a_str(U, p - BASE)
            if not en_b:
                continue
            key = (cat, p, cat == 'menu' and i in ENGC)      # engine-C users get their own copy
            if key not in items:
                kb_ = None
                if i < kn:
                    kp = w32(K, kb - BASE + i * ks)
                    kb_ = k_name(kp)
                items[key] = {'id': '%s_%03d' % (cat, i), 'cat': cat, 'idx': [], 'va': p,
                              'len': len(en_b) + 2, 'en': u_dec(en_b), 'refs': [], 'k_hex': kb_}
                order.append(key)
            items[key]['idx'].append(i)
            items[key]['refs'].append(ro)
    return [items[k] for k in order]


def build_entries():
    ents = []
    for e in collect():
        cat, i = e['cat'], e['idx'][0]
        kb = e.pop('k_hex')
        e['engine'] = 'A'
        if cat == 'menu' and i in ENGC:
            kp, dx, dy = ENGC[i]
            idx = k_index(kp)
            e.update(engine='C', ko=decode_c(idx), k_ko=decode_c(idx), dx=dx, dy=dy)
        elif (cat, i) in KEEP_EN:
            e['ko'] = None
        elif (cat, i) in NEW_KO:
            e['ko'] = NEW_KO[(cat, i)]
            if kb:
                e['k_ko'] = decode_a(kb); e['k_hex'] = kb.hex()
        elif kb:
            e['ko'] = decode_a(kb); e['k_ko'] = e['ko']; e['k_hex'] = kb.hex()
        else:
            e['ko'] = None
        if cat in LIMIT:
            e['limit'] = LIMIT[cat]
        ents.append(e)
    ents.append({'id': 'holder', 'cat': 'holder', 'idx': [0], 'va': HOLDER, 'len': 8, 'en': 'Holder',
                 'refs': [], 'code_refs': [[_R(0x800F4CC4) - BASE, _R(0x800F4CC8) - BASE],
                                           [_R(0x800F5764) - BASE, _R(0x800F5768) - BASE]],
                 'engine': 'A', 'ko': '홀더', 'in_place': True})
    for nm, kp, up in (('att', K_ATT, U_ATT), ('def', K_DEF, U_DEF)):
        idx = k_index(kp)
        ents.append({'id': nm, 'cat': 'att_def', 'idx': [0], 'va': w32(_rd(U_DRA), up), 'len': 4,
                     'en': nm.upper(), 'refs': [up], 'engine': 'C', 'ko': decode_c(idx), 'k_ko': decode_c(idx)})
    return ents


def encode_entry(e):
    """-> bytes as stored (with terminator)."""
    if e['engine'] == 'C':
        if e.get('k_ko') == e['ko'] and e['cat'] == 'menu':
            idx = k_index(ENGC[e['idx'][0]][0])
        elif e.get('k_ko') == e['ko']:
            idx = k_index({'att': K_ATT, 'def': K_DEF}[e['id']])
        else:
            idx = encode_c(e['ko'])
        assert 0xFF not in idx
        if e['cat'] == 'menu':
            return bytes([0xFE, e['dx'] & 0xFF, e['dy'] & 0xFF]) + idx + b'\xff'
        return idx + b'\xff'
    if e.get('k_hex') and e.get('k_ko') == e['ko']:
        b = bytes.fromhex(e['k_hex'])
        _assert_safe(b)
    else:
        b = encode_a(e['ko'])
    return b + b'\xff\x00'


def load():
    return json.load(open(OUT, encoding='utf-8'))


def extract():
    old = {}
    if os.path.exists(OUT):
        old = {e['id']: e for e in load()}
    ents = build_entries()
    for e in ents:
        o = old.get(e['id'])
        e['k_ko_auto'] = e['ko']                   # auto value, recorded before a hand edit is copied over
        if o and o.get('ko') != o.get('k_ko_auto', o.get('ko')):
            e['ko'] = o['ko']                      # keep hand edits
        if e['ko'] is not None:
            b = encode_entry(e)
            e['hex'] = b.hex(' ')
            e['cells'] = cells_a(b[:-2]) if e['engine'] == 'A' else len(b) - (4 if e['cat'] == 'menu' else 1)
        e['va'] = '0x%08X' % e['va']
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(ents, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return ents


# ------------------------------------------------------------------ DRA patch
def _b_spans():
    spans = []
    for e in json.load(open(DRA_B, encoding='utf-8')):
        va = int(e['va'], 16) if isinstance(e['va'], str) else e['va']
        spans.append((va, va + e['len']))
    return spans


def _hook_code(base):
    a = Asm(base)
    a.lbu('t0', 0, 'a0')
    a.ori('t1', 'zero', 0xFE)
    a.beq('t0', 't1', 'engc'); a.nop()
    a.sw('s4', 32, 'sp')                   # displaced 2nd instruction of MenuDrawStr
    a.j(MDS + 8); a.nop()
    a.label('engc')                        # frame (40 bytes) already made by the delay slot at MDS
    a.sw('ra', 32, 'sp')
    a.w(_i(32, 'a0', 't0', 1))             # lb t0,1(a0)  dx
    a.w(_i(32, 'a0', 't1', 2))             # lb t1,2(a0)  dy
    a.addu('a1', 'a1', 't0')
    a.addu('a2', 'a2', 't1')
    a.lui('t2', FLAG >> 16)
    a.lw('t3', FLAG & 0xFFFF, 't2'); a.nop()
    a.sw('t3', 36, 'sp')
    a.sltiu('t4', 't3', 1)                 # arg5: 1 = normal, 0 = dimmed (grey flag set by the caller)
    a.sw('t4', 16, 'sp')
    a.sw('zero', FLAG & 0xFFFF, 't2')      # the flag would force CLUT 0x15E onto the label sprites
    a.jal(LABEL)
    a.addiu('a0', 'a0', 3)
    a.lw('t3', 36, 'sp')
    a.lui('t2', FLAG >> 16)
    a.sw('t3', FLAG & 0xFFFF, 't2')
    a.lw('ra', 32, 'sp'); a.nop()
    a.jr('ra')
    a.addiu('sp', 'sp', 40)
    return a.assemble()


def _set_code(base, sets_va):
    a = Asm(base)
    a.addiu('sp', 'sp', -24)
    a.sw('ra', 16, 'sp')
    for va, mode in zip(sets_va, (0, 0x100, 1)):           # as K 0x800FBDA0..0x800FBDC4
        a.lui('a0', ((va + 0x8000) >> 16) & 0xFFFF)
        a.w(_i(9, 'a0', 'a0', va & 0xFFFF))                # addiu a0,a0,lo
        a.jal(SETR)
        a.ori('a1', 'zero', mode)
    a.lw('ra', 16, 'sp'); a.nop()
    a.jr('ra')
    a.addiu('sp', 'sp', 24)
    return a.assemble()


def _check_refs(U, ents):
    """every English span is referenced only by the table words we rewrite (DRA and all other US files)."""
    lo = min(e['va'] for e in ents); hi = max(e['va'] + e['len'] for e in ents)
    ptrs = _data_ptrs(U, lo, hi)
    known = {}
    for e in ents:
        for r in e['refs']:
            known[r] = e['va']
    problems = []
    spans = sorted((e['va'], e['va'] + e['len'], e['id']) for e in ents)
    import bisect
    starts = [s[0] for s in spans]
    for v, offs in ptrs.items():
        k = bisect.bisect_right(starts, v) - 1
        if k < 0 or v >= spans[k][1]:
            continue
        for o in offs:
            if known.get(o) != spans[k][0] or v != spans[k][0]:
                problems.append('data word at %X -> %08X (%s)' % (o, v, spans[k][2]))
    # lui/addiu pairs
    for o in range(0x40000, len(U) - 4, 4):
        x = w32(U, o)
        if x >> 26 != 15:
            continue
        rt = (x >> 16) & 31; hv = (x & 0xFFFF) << 16
        for k in range(1, 12):
            y = w32(U, o + 4 * k)
            op, rs, rt2 = y >> 26, (y >> 21) & 31, (y >> 16) & 31
            if rs == rt and op in (9, 13, 32, 33, 35, 36, 37):
                imm = y & 0xFFFF
                if op != 13 and imm & 0x8000:
                    imm -= 0x10000
                t = (hv | (y & 0xFFFF)) if op == 13 else (hv + imm) & 0xFFFFFFFF
                j = bisect.bisect_right(starts, t) - 1
                if j >= 0 and t < spans[j][1]:
                    problems.append('code %08X -> %08X (%s)' % (BASE + o + 4 * k, t, spans[j][2]))
                if rt2 == rt:
                    break
            if (op == 15 and rt2 == rt) or op in (2, 3):
                break
    return problems


def _other_file_refs(lo, hi):
    """aligned words in other US files pointing into the English string area."""
    hits = []
    for root, _, files in os.walk(_base.U):
        for f in files:
            p = os.path.join(root, f)
            if os.path.samefile(p, U_DRA) or f.startswith('XA_') or f.endswith(('.VB', '.STR')):
                continue
            d = _rd(p)
            for o in range(0, len(d) - 3, 4):
                v = w32(d, o)
                if lo <= v < hi:
                    hits.append((os.path.relpath(p, WORK), o, v))
    return hits


EQUIP_ICON = (0x800A499C + 0x2C, 0x34, 228)
ACC_ICON = (0x800A77EC + 0x18, 0x20, 93)
RELIC_ICON = (_R(0x800DFC28) + 0x08, 0x10, 31)
ICON_BASE = 0x800C5324
ICON_FREE = (276, 320)


_REFD = None
def _referenced(U):
    """all addresses in the string/icon areas named by a data word or a lui/addiu|ori pair in US DRA."""
    global _REFD
    if _REFD is None:
        lo, hi = 0x800C0000, 0x800E2100
        r = set(_data_ptrs(U, lo, hi))
        for o in range(0x40000, len(U) - 4, 4):
            x = w32(U, o)
            if x >> 26 != 15:
                continue
            rt = (x >> 16) & 31; hv = (x & 0xFFFF) << 16
            for k in range(1, 12):
                y = w32(U, o + 4 * k)
                op, rs, rt2 = y >> 26, (y >> 21) & 31, (y >> 16) & 31
                if rs == rt and op in (9, 13, 32, 33, 35, 36, 37):
                    imm = y & 0xFFFF
                    if op != 13 and imm & 0x8000:
                        imm -= 0x10000
                    t = (hv | (y & 0xFFFF)) if op == 13 else (hv + imm) & 0xFFFFFFFF
                    if lo <= t < hi:
                        r.add(t)
                    if rt2 == rt:
                        break
                if (op == 15 and rt2 == rt) or op in (2, 3):
                    break
        _REFD = r
    return _REFD


def _alloc(free, n, align=1):
    best = None
    for s in free:
        a = (s[0] + align - 1) // align * align
        if s[1] - a >= n and (best is None or s[1] - s[0] < best[1] - best[0]):
            best = s
    if best is None:
        return None
    a = (best[0] + align - 1) // align * align
    if a > best[0]:
        free.append([best[0], a])
    best[0] = a + n
    return a


def patch_dra_a(dra, ents=None, report=None):
    U = _rd(U_DRA)
    dra = bytearray(dra)
    assert len(dra) == len(U)
    if ents is None:
        ents = load()
    ents = [dict(e) for e in ents]
    for e in ents:
        e['va'] = int(e['va'], 16) if isinstance(e['va'], str) else e['va']
    todo = [e for e in ents if e.get('ko')]
    # ---- original bytes
    for e in ents:
        o = e['va'] - BASE
        assert dra[o:o + e['len']] == U[o:o + e['len']], ('string area already modified', e['id'])
        for r in e['refs']:
            assert w32(dra, r) == e['va'], (e['id'], hex(r))
    def chk(va, orig):
        o = va - BASE
        assert bytes(dra[o:o + len(orig)]) == orig, (hex(va), bytes(dra[o:o + len(orig)]).hex(), orig.hex())
    chk(OVL_Y, bytes.fromhex('f8ffc624'))
    chk(MDS, MDS_ORIG)
    chk(LABEL, bytes.fromhex('b8ffbd27'))
    chk(SETR, bytes.fromhex('d0ffbd27'))
    chk(SETCALL - 8, bytes.fromhex('0a80043c302b848c') + jal_word(SETR) + bytes.fromhex('21280000'))
    chk(UTXT_COPY, UTXT_COPY_ORIG)
    assert w32(dra, U_SETPTR) == _R(0x800DC048)
    # ---- free pool: English spans of strings we replace (not shared with engine B, not in place)
    bsp = _b_spans()
    pool = [e for e in todo if not e.get('in_place')]
    for e in pool:
        a, b = e['va'], e['va'] + e['len']
        for x, y in bsp:
            assert b <= x or y <= a, ('overlaps engine-B span', e['id'])
    extra = []                                       # ATT/DEF set string 0x800DC048 (ＡＴＤＥＦ + NUL)
    so = _R(0x800DC048) - BASE
    setlen = U.index(b'\0', so) - so + 1
    extra.append({'id': 'set_en', 'va': _R(0x800DC048), 'len': setlen, 'refs': [U_SETPTR]})
    for x, y in bsp:
        assert _R(0x800DC048) + setlen <= x or y <= _R(0x800DC048)
    probs = _check_refs(U, pool + extra)
    assert not probs, probs[:10]
    free = []
    for e in pool + extra:
        o = e['va'] - BASE
        dra[o:o + e['len']] = bytes(e['len'])
        free.append([e['va'], e['va'] + e['len']])
    refd = _referenced(U)
    free.sort()
    merged = []
    for s in free:
        if merged and s[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], s[1])
        else:
            merged.append(list(s))
    free = merged
    pool_bytes = sum(b - a for a, b in free)
    # overflow area: unused equipment-icon slots 276..319 (16x16 4bpp, 128 bytes each, base 0x800C5324;
    # loader 0x800E9448 = base + icon*128). Highest icon used by the equip/accessory/relic tables: 275.
    used = [struct.unpack_from('<H', dra, EQUIP_ICON[0] - BASE + i * EQUIP_ICON[1])[0] for i in range(EQUIP_ICON[2])]
    used += [struct.unpack_from('<H', dra, ACC_ICON[0] - BASE + i * ACC_ICON[1])[0] for i in range(ACC_ICON[2])]
    used += [struct.unpack_from('<H', dra, RELIC_ICON[0] - BASE + i * RELIC_ICON[1])[0] for i in range(RELIC_ICON[2])]
    assert max(used) < ICON_FREE[0], max(used)
    lo, hi = ICON_BASE + ICON_FREE[0] * 128, ICON_BASE + ICON_FREE[1] * 128
    assert dra[lo - BASE:hi - BASE] == bytes(hi - lo) and not any(lo <= v < hi for v in refd)
    free.append([lo, hi])
    total = sum(b - a for a, b in free)
    # ---- code + engine-C data first (aligned)
    sets = k_engc_set()
    code = [[lo, hi]]                                # code + set strings live in the icon area
    hook_va = _alloc(code, 4 * 30, 4)
    hook = _hook_code(hook_va)
    setc_va = _alloc(code, 4 * 18, 4)
    set_va = [_alloc(code, 33) for _ in sets]
    free[-1][0] = (code[0][0] + 3) & ~3
    setc = _set_code(setc_va, set_va)
    for va, s in zip(set_va, sets):
        dra[va - BASE:va - BASE + 33] = s + b'\0'
    def put(va, b):
        o = va - BASE
        assert dra[o:o + len(b)] == b'\0' * len(b), hex(va)
        dra[o:o + len(b)] = b
    put(hook_va, hook)
    put(setc_va, setc)
    # ---- strings
    placed = 0
    blobs = sorted(((e, encode_entry(e)) for e in todo), key=lambda x: -len(x[1]))
    for e, b in blobs:
        if e.get('in_place'):
            assert len(b) <= e['len'], e['id']
            o = e['va'] - BASE
            dra[o:o + e['len']] = b + b'\0' * (e['len'] - len(b))
            placed += 1
            continue
        va = _alloc(free, len(b))
        if va is None:
            raise SystemExit('DRA_A: no room for %s (%d bytes)' % (e['id'], len(b)))
        put(va, b)
        for r in e['refs']:
            struct.pack_into('<I', dra, r, va)
        placed += 1
    # ---- code patches
    struct.pack_into('<I', dra, OVL_Y - BASE, 0x24C6FFFE)            # overlay y-2 (as K)
    o = MDS - BASE                                                    # MenuDrawStr: j hook ; addiu sp,sp,-40
    dra[o:o + 8] = struct.pack('<II', (2 << 26) | ((hook_va >> 2) & 0x3FFFFFF), 0x27BDFFD8)
    dra[SETCALL - BASE:SETCALL - BASE + 4] = jal_word(setc_va)        # 3-pass set render (K 0x800FBDA0)
    struct.pack_into('<I', dra, U_SETPTR, set_va[0])
    o = UTXT_COPY - BASE                                              # Ultimate's option text swapper: off
    dra[o:o + 8] = bytes.fromhex('0800e00300000000')                  # jr ra ; nop
    left = sum(b - a for a, b in free)
    global LAST_FREE
    LAST_FREE = free                       # zeroed spans still free (engfix places its status-name code here)
    if report is not None:
        report.update(placed=placed, pool=pool_bytes, icon=(lo, hi), total=total, left=left, hook=hook_va, setcode=setc_va, sets=set_va)
    return bytes(dra)


# ------------------------------------------------------------------ SEL (Ultimate's runtime text edits)
# SEL.BIN / BIN/SELRIC2.BIN (loaded at 0x80180000) function 0x801B37AC, called once at game start (0x801B3A30):
#  1) 23 entries at 0x801AF994 {tbl, keep, off, skip, add, adv}: compose a new string in the DRA buffer
#     0x80136B8C (prefix of the current string + English insert from 0x801AFA4C + rest) and repoint the
#     equip/acc/enemy/relic name or description field to it (typo fixes: "Natto", "handed", "Room", ...);
#  2) 9 "UTXT" entries at 0x801AFAE4 -> header at 0x80136904: dest = *(field) + k, two English variants copied
#     from 0x801AFB1C ("Empty hand"/"Unarmed", "----"/"NONE", Sprite/Fairy Card, Pixie/Fairy, N.Devil/Demon);
#     DRA 0x800E3D3C copies the variant picked by an option bit over dest every time it runs.
# Both write English into our Korean strings (dest follows the relocated pointers), so the whole function is
# made to return at once (it only does text). DRA's copier is disabled as well (patch_dra_a).
SEL_TABLES = {0: (0x800A499C, 0x34), 1: (0x800A77EC, 0x20), 2: (0x800A8544, 0x28), 3: (_R(0x800DFC28), 0x10)}


def sel_writes(dra, sel):
    """byte ranges of DRA RAM the SEL function writes, given the DRA as loaded (for the RAM-dump check)."""
    out = []
    def field(t, off):
        b = SEL_TABLES.get(t, (0x800A838C, 4))[0]
        return b + off
    for k in range(23):
        t, cl, off, skip, al, adv, _ = struct.unpack_from('<BBHBBBB', sel, SEL_TAB1 + 8 * k)
        out.append((field(t, off), 4))
    for k in range(9):
        b0, _, off, ln, _ = struct.unpack_from('<BBHBB', sel, SEL_TAB2 + 6 * k)
        f = field(b0 & 7, off)
        out.append((w32(dra, f - BASE) + (b0 >> 3), ln))
    return out


import addrmap as _am
SEL_FUNC_VA = _am.ovl('ST/SEL/SEL.BIN', 0x801B37AC)      # v1.2 0x801B37AC
SEL_FUNC = SEL_FUNC_VA - 0x80180000
SEL_CALL = _am.ovl('ST/SEL/SEL.BIN', 0x801B3A30) - 0x80180000   # v1.2 0x801B3A30: jal SEL_FUNC
SEL_TAB1 = _am.ovl('ST/SEL/SEL.BIN', 0x801AF994) - 0x80180000
SEL_TAB2 = _am.ovl('ST/SEL/SEL.BIN', 0x801AFAE4) - 0x80180000
SEL_FUNC_ORIG = bytes.fromhex('c0ffbd273400b5af1380153c')
UTXT_COPY = _R(0x800E3D3C)
UTXT_COPY_ORIG = bytes.fromhex('5854033c1380083c')


def patch_sel(name, data):
    base = name.replace(chr(92), '/').split('/')[-1].split(';')[0].upper()
    if base not in ('SEL.BIN', 'SELRIC2.BIN'):
        return data
    o = SEL_FUNC
    assert data[o:o + len(SEL_FUNC_ORIG)] == SEL_FUNC_ORIG, (name, data[o:o + 12].hex())
    j = struct.pack('<I', (3 << 26) | ((SEL_FUNC_VA >> 2) & 0x3FFFFFF))
    assert data[SEL_CALL:SEL_CALL + 4] == j, name
    return data[:o] + bytes.fromhex('0800e00300000000') + data[o + 8:]


# ------------------------------------------------------------------ F_GAME
def patch_fgame(name, data):
    """Copy K's 8x8 menu sheet (128x128 4bpp block at 0x30000) over the US one. F_GAME and F_GAME2 share it."""
    base = name.replace('\\', '/').split('/')[-1].split(';')[0].upper()
    if base not in ('F_GAME.BIN', 'F_GAME2.BIN'):
        return data
    a, b = FGAME_SHEET
    U, K = _rd(U_FGAME), _rd(K_FGAME)
    assert len(data) == len(U) == len(K), (name, len(data))
    assert data[a:b] == U[a:b], (name, 'US 8x8 sheet block not found at 0x30000')
    # layout check: K and US differ only in the logo (0x2C000-0x2FFFF), this sheet and 0x41A00-0x41BFF
    for o in range(0, len(U), 0x2000):
        if U[o:o + 0x2000] != K[o:o + 0x2000]:
            assert o in (0x2C000, 0x2E000, 0x30000, 0x40000), hex(o)
    return data[:a] + K[a:b] + data[b:]


# ------------------------------------------------------------------ preview / check
def _sheet():
    d = _rd(K_FGAME)[FGAME_SHEET[0]:FGAME_SHEET[1]]
    return [[(d[y * 64 + x // 2] >> (4 * (x & 1))) & 15 for x in range(128)] for y in range(128)]


def render_a(img, sheet, b, x, y, col=(230, 230, 230)):
    """MenuDrawStr emulation (patched): 8 px advance, FF xx overlay at (x-8, y-2)."""
    px = img.load()
    def cell(c, cx, cy):
        for yy in range(8):
            for xx in range(8):
                if sheet[(c >> 4) * 8 + yy][(c & 15) * 8 + xx]:
                    if 0 <= cx + xx < img.width and 0 <= cy + yy < img.height:
                        px[cx + xx, cy + yy] = col
    i = 0
    while i < len(b):
        c = b[i]; i += 1
        if c == 0xFF:
            c = b[i]; i += 1
            if c == 0:
                break
            if c != 0xFF:
                x -= 8
                cell(c, x, y - 2)
                x += 8
                continue
        cell(c, x, y)
        x += 8


def render_c(img, idx, x, y, col=(255, 220, 140)):
    """engine C: 12x16 cells, each the 16x15 glyph squeezed to 12 px (approximation of 0x80104EDC)."""
    import kmap
    font = kmap.load_font()
    sets = k_engc_set()
    px = img.load()
    for c in idx:
        row, page, k = c >> 5, (c >> 4) & 1, c & 15
        si = {(0, 0): 0, (0, 1): 1, (1, 0): 2}[(row, page)]
        code = (sets[si][2 * k] << 8) | sets[si][2 * k + 1]
        g = font[kmap.code_to_index(code)] if code != 0x8140 else None
        if g is not None:
            for yy in range(15):
                for xx in range(12):
                    if g[yy][xx * 16 // 12] or g[yy][min(15, (xx * 16 + 15) // 12)]:
                        px[x + xx, y + yy] = col
        x += 12


def _ranges(ix):
    out, s, p = [], None, None
    for i in sorted(ix):
        if s is None:
            s = p = i
        elif i > p + 1:
            out.append('%X(%d)' % (BASE + s, p - s + 1)); s = p = i
        else:
            p = i
    if s is not None:
        out.append('%X(%d)' % (BASE + s, p - s + 1))
    return ' '.join(out)


def check():
    from PIL import Image, ImageDraw
    ents = extract()
    for e in ents:
        e['va'] = int(e['va'], 16)
    bad = []
    # 1. every K string decodes cleanly
    nk = 0
    for e in ents:
        if e.get('k_hex'):
            nk += 1
            if '{' in e['k_ko']:
                bad.append('K decode %s: %s' % (e['id'], e['k_ko']))
    # 2. encodable + limits
    for e in ents:
        if not e.get('ko'):
            continue
        try:
            b = encode_entry(e)
        except (ValueError, KeyError, AssertionError) as x:
            bad.append('%s: %s' % (e['id'], x)); continue
        if e['engine'] == 'A':
            n = cells_a(b[:-2])
            lim = e.get('limit', len(e['en']))
            if e['cat'] == 'menu' and e['idx'][0] >= 53:      # time-attack list: free width
                lim = 30
            if n > lim:
                bad.append('%s too wide: %d cells > %d (%s)' % (e['id'], n, lim, e['ko']))
            if decode_a(b[:-2]) != e['ko']:
                bad.append('%s roundtrip %s != %s' % (e['id'], decode_a(b[:-2]), e['ko']))
    # 3. patch a copy (after engine B) and verify the table refs
    import drabapply
    d0 = _rd(U_DRA)
    try:
        db, _, _ = drabapply.apply(d0)
    except Exception as x:          # engine-B step needs its own deps; fall back to the plain US file
        print('note: drabapply failed (%s); checking on the US file' % x)
        db = d0
    rep = {}
    d1 = patch_dra_a(db, ents, rep)
    for e in ents:
        if not e.get('ko'):
            continue
        b = encode_entry(e)
        if e.get('in_place'):
            o = e['va'] - BASE
            assert d1[o:o + len(b)] == b
            continue
        for r in e['refs']:
            p = w32(d1, r)
            assert d1[p - BASE:p - BASE + len(b)] == b, (e['id'], hex(p))
    # engine-B area untouched
    for a, b in _b_spans():
        assert d1[a - BASE:b - BASE] == db[a - BASE:b - BASE], hex(a)
    diff = [o for o in range(len(d1)) if d1[o] != db[o]]
    print('DRA_A: %d strings (%d from K); English pool %d bytes + icon area %08X-%08X; %d of %d bytes left;'
          ' hook %08X, set code %08X, sets %s'
          % (rep['placed'], nk, rep['pool'], rep['icon'][0], rep['icon'][1], rep['left'], rep['total'], rep['hook'], rep['setcode'],
             ' '.join('%08X' % v for v in rep['sets'])))
    print('changed bytes: %d (range %X..%X)' % (len(diff), diff[0], diff[-1]))
    starts = {e['va'] for e in ents if e.get('ko') and not e.get('in_place')}
    hits = [h for h in _other_file_refs(min(starts), max(starts) + 1) if h[2] in starts]
    print('words in other US files equal to a moved string address:', hits if hits else 'none')
    ram, disc = os.path.join(WORK, 'ram_dra_menu_testK.bin'), os.path.join(WORK, 'testK_DRA.BIN')
    if os.path.exists(ram) and os.path.exists(disc):
        R, T = _rd(ram), _rd(disc)
        sel = _rd(os.path.join(_base.U, 'ST', 'SEL', 'SEL.BIN'))
        expl = set()
        for a, n in sel_writes(T, sel):
            expl.update(range(a - BASE, a - BASE + n))
        dirty = [i for i in range(min(len(R), len(T))) if R[i] != T[i]]
        une = [i for i in dirty if i not in expl and 0x25000 <= i < 0x42000]
        mine = {i for i in range(len(d1)) if d1[i] != db[i]}
        hit = sorted(mine & set(dirty))
        print('RAM dump: %d bytes changed at runtime, %d explained by SEL; unexplained in string/icon areas: %s'
              % (len(dirty), len([i for i in dirty if i in expl]), _ranges(une) or 'none'))
        print('  new placements touching runtime-changed bytes:', _ranges(hit) or 'none',
              '(all SEL-caused; SEL text patch now disabled)' if hit and all(i in expl for i in hit) else '')
        bad += ['placement on unexplained runtime byte %X' % (BASE + i) for i in hit if i not in expl]
    eng = [e for e in ents if not e.get('ko')]
    print('left English (%d): %s' % (len(eng), ', '.join(sorted(set(e['en'] for e in eng)))))
    if bad:
        print('PROBLEMS (%d):' % len(bad)); print('\n'.join('  ' + x for x in bad))
    else:
        print('all strings encodable, within limits')
    # 4. preview
    sheet = _sheet()
    sample = [e for e in ents if e.get('ko')]
    pick = [e for e in sample if e['cat'] in ('menu', 'att_def', 'holder')]
    pick += [e for e in sample if e['cat'] == 'equip'][:40:3] + [e for e in sample if e['cat'] == 'acc'][:93:6]
    pick += [e for e in sample if e['cat'] == 'enemy'][::25] + [e for e in sample if e['cat'] in ('equip', 'acc', 'enemy') and e['id'] in
             ('equip_169', 'equip_170', 'equip_171', 'equip_172', 'equip_173', 'equip_174', 'equip_175', 'acc_090', 'acc_091', 'acc_092', 'enemy_400', 'enemy_418')]
    rows = (len(pick) + 1) // 2
    S = 2
    img = Image.new('RGB', (2 * 300, rows * 18 + 8), (16, 16, 40))
    dr = ImageDraw.Draw(img)
    for n, e in enumerate(pick):
        x0 = 4 + (n % 2) * 300; y0 = 6 + (n // 2) * 18
        dr.text((x0, y0), e['en'][:18], fill=(120, 120, 160))
        b = encode_entry(e)
        if e['engine'] == 'A':
            render_a(img, sheet, b, x0 + 120, y0 + 4)
        else:
            idx = b[3:-1] if e['cat'] == 'menu' else b[:-1]
            render_c(img, idx, x0 + 120, y0)
    img = img.resize((img.width * S, img.height * S), Image.NEAREST)
    img.save(PREVIEW)
    print('preview ->', PREVIEW)
    for f in ('ST/SEL/SEL.BIN', 'BIN/SELRIC2.BIN'):
        x = _rd(os.path.join(_base.U, *f.split('/')))
        import seltext
        y = patch_sel(f, seltext.patch(x) if f.startswith('ST') else x)
        print('patch_sel', f, 'ok')
    return not bad


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'check'
    if cmd == 'extract':
        print(len(extract()), 'entries ->', OUT)
    else:
        sys.exit(0 if check() else 1)
